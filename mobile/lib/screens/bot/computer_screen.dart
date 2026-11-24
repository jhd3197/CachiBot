import 'dart:async';
import 'dart:typed_data';
import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../models/bot.dart';
import '../../models/computer.dart';
import '../../providers/auth_provider.dart';
import '../../providers/bots_provider.dart';
import '../../providers/computer_provider.dart';
import '../../providers/service_providers.dart';

/// Watch heartbeats keep the computer awake (~30 s server TTL); the frame
/// poll follows the selected window at ~1 fps (Vela's watching rate) and the
/// desktop preview at ~3 s, refetched at once when a `computer_update`
/// reports a new preview revision. The ETag keeps unchanged frames at a
/// cheap 304.
const _heartbeatInterval = Duration(seconds: 15);
const _previewPollInterval = Duration(seconds: 3);
const _viewPollInterval = Duration(seconds: 1);
const _scrollFlushInterval = Duration(milliseconds: 120);

/// Named keys the input API accepts (mirrors the web surface).
const _namedKeys = <String, String>{
  'Enter': 'enter',
  'Tab': 'tab',
  'Esc': 'escape',
  'Backspace': 'backspace',
  '←': 'arrowleft',
  '→': 'arrowright',
  '↑': 'arrowup',
  '↓': 'arrowdown',
};

/// The bot's computer, full screen (design 05, mobile decision 6): the live
/// desktop preview, or one selected window's frame full size, with a window
/// switcher from the real views list, pinch-zoom and pan, and — only while
/// this user holds the take-over — touch input: tap = click, long-press =
/// right click, drag = scroll, keyboard toggle = type/key.
///
/// Nothing is faked: every surface gates on the Docker probe, frames come
/// from the preview/frame endpoints (which never wake the computer), and an
/// off/asleep computer shows its real state with the real Wake/Turn on
/// action instead of an invented frame.
class ComputerScreen extends ConsumerStatefulWidget {
  const ComputerScreen({required this.botId, super.key});

  final String botId;

  @override
  ConsumerState<ComputerScreen> createState() => _ComputerScreenState();
}

class _ComputerScreenState extends ConsumerState<ComputerScreen>
    with WidgetsBindingObserver {
  final _frameKey = GlobalKey();
  final _transformController = TransformationController();
  final _typeController = TextEditingController();

  Timer? _heartbeatTimer;
  Timer? _pollTimer;
  Timer? _scrollFlushTimer;

  Uint8List? _frameBytes;
  String? _etag;
  int? _frameAt;
  Size? _naturalSize;
  int _decodeToken = 0;

  /// The window whose frame is on screen (null = the desktop preview).
  String? _frameTarget;
  String? _selectedViewId;

  Offset _scrollAccum = Offset.zero;
  bool _zoomed = false;
  bool _keyboardOpen = false;
  bool _appActive = true;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _transformController.addListener(_onTransform);
    Future.microtask(() async {
      final computer = ref.read(computerProvider.notifier);
      unawaited(computer.fetchStatus());
      if (ref.read(botsProvider).bots.isEmpty) {
        unawaited(ref.read(botsProvider.notifier).loadBots());
      }
      // computer_update events arrive on the app socket; connect if needed.
      final ws = ref.read(wsServiceProvider);
      if (!ws.isConnected) unawaited(ws.connect());
      await computer.ensureForBot(widget.botId);
      await computer.fetchViews(widget.botId);
      _syncTimers();
    });
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _stopTimers();
    _scrollFlushTimer?.cancel();
    _transformController.removeListener(_onTransform);
    _transformController.dispose();
    _typeController.dispose();
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    // Mounted and visible only: hidden (backgrounded) stops the heartbeats
    // and the poll; resumed restarts them while the computer is live.
    _appActive = state == AppLifecycleState.resumed;
    if (_appActive) {
      _syncTimers();
    } else {
      _stopTimers();
    }
  }

  // -------------------------------------------------------------------------
  // Live plumbing: heartbeats + frame polling (a preview never wakes the
  // computer; 409/404 keep the last real frame)
  // -------------------------------------------------------------------------

  bool get _isLive =>
      ref.read(computerProvider).byBot[widget.botId]?.isLive ?? false;

  void _syncTimers() {
    if (_isLive && _appActive) {
      if (_heartbeatTimer != null) return;
      _heartbeat();
      _pollFrame();
      _heartbeatTimer = Timer.periodic(_heartbeatInterval, (_) => _heartbeat());
      _restartPollTimer();
    } else {
      _stopTimers();
    }
  }

  void _stopTimers() {
    _heartbeatTimer?.cancel();
    _heartbeatTimer = null;
    _pollTimer?.cancel();
    _pollTimer = null;
  }

  void _restartPollTimer() {
    _pollTimer?.cancel();
    final interval = _selectedViewId == null ? _previewPollInterval : _viewPollInterval;
    _pollTimer = Timer.periodic(interval, (_) => _pollFrame());
  }

  void _heartbeat() {
    if (!_isLive) return;
    // Asleep/unreachable: the next beat retries; nothing is faked.
    unawaited(
      ref.read(computerServiceProvider).watch(widget.botId).catchError((_) {}),
    );
  }

  /// The selected window while it is still open; a window that went away
  /// falls back to the desktop preview instead of polling a gone frame.
  String? get _activeViewId {
    final windows = ref.read(computerProvider).windowsByBot[widget.botId];
    final selected = _selectedViewId;
    if (selected == null || windows == null) return null;
    return windows.any((w) => w.id == selected) ? selected : null;
  }

  Future<void> _pollFrame() async {
    if (!_isLive) return;
    final target = _activeViewId;
    if (target != _frameTarget) {
      // New target: its frames are named by their own ETag.
      _frameTarget = target;
      _etag = null;
      _frameBytes = null;
      _naturalSize = null;
    }
    try {
      final service = ref.read(computerServiceProvider);
      final frame = target == null
          ? await service.getPreview(widget.botId, etag: _etag)
          : await service.getViewFrame(widget.botId, target, etag: _etag);
      if (!mounted || frame == null) return; // 304: the frame on screen is current
      _etag = frame.etag;
      _frameAt = DateTime.now().millisecondsSinceEpoch;
      _frameBytes = frame.bytes;
      unawaited(_decodeNaturalSize(frame.bytes));
      setState(() {});
    } catch (_) {
      // 409 (asleep) / 404 (nothing to show): keep the last real frame.
    }
  }

  Future<void> _decodeNaturalSize(Uint8List bytes) async {
    final token = ++_decodeToken;
    try {
      final codec = await ui.instantiateImageCodec(bytes);
      final frame = await codec.getNextFrame();
      final size = Size(
        frame.image.width.toDouble(),
        frame.image.height.toDouble(),
      );
      frame.image.dispose();
      codec.dispose();
      if (!mounted || token != _decodeToken) return;
      setState(() => _naturalSize = size);
    } catch (_) {}
  }

  // -------------------------------------------------------------------------
  // Take-over input (only while this user holds the lease, and only on a
  // selected window — the desktop preview is watch-only, as on the web)
  // -------------------------------------------------------------------------

  bool get _drivingMe {
    final computer = ref.read(computerProvider).byBot[widget.botId];
    final user = ref.read(authProvider).user;
    return computer?.driver != null && computer!.driver!.userId == user?.id;
  }

  Future<void> _sendInput(Map<String, dynamic> input) async {
    if (!_drivingMe) return;
    final viewId = _activeViewId;
    if (viewId == null) return;
    final error = await ref.read(computerProvider.notifier).sendInput(
      widget.botId,
      {'viewId': viewId, 'frameAt': _frameAt, ...input},
    );
    if (error != null && mounted) {
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(error)));
    }
  }

  /// Map a touch on the displayed frame into the frame's own pixel space
  /// (the image's natural size), the way the web surface does; a zero size
  /// means there is no honest mapping and the input is skipped.
  Offset? _pointFor(Offset local) {
    final box = _frameKey.currentContext?.findRenderObject() as RenderBox?;
    final size = box?.size;
    final natural = _naturalSize;
    if (size == null || natural == null) return null;
    if (size.width == 0 || size.height == 0) return null;
    if (natural.width == 0 || natural.height == 0) return null;
    final x = (local.dx / size.width * natural.width).round();
    final y = (local.dy / size.height * natural.height).round();
    if (x < 0 || y < 0) return null;
    return Offset(x.toDouble(), y.toDouble());
  }

  void _onTapUp(TapUpDetails details) {
    final point = _pointFor(details.localPosition);
    if (point == null) return;
    unawaited(_sendInput({
      'kind': 'click',
      'point': {'x': point.dx, 'y': point.dy},
      'button': 'left',
    }));
  }

  void _onLongPressStart(LongPressStartDetails details) {
    final point = _pointFor(details.localPosition);
    if (point == null) return;
    unawaited(_sendInput({
      'kind': 'click',
      'point': {'x': point.dx, 'y': point.dy},
      'button': 'right',
    }));
  }

  void _onPanUpdate(DragUpdateDetails details) {
    _scrollAccum += details.delta;
    _scrollFlushTimer ??= Timer(_scrollFlushInterval, _flushScroll);
  }

  void _onPanEnd(DragEndDetails details) => _flushScroll();

  /// Drag = scroll, with the natural touch direction (drag up scrolls down):
  /// the finger's delta goes out negated as wheel deltas, throttled.
  void _flushScroll() {
    _scrollFlushTimer?.cancel();
    _scrollFlushTimer = null;
    final dx = _scrollAccum.dx.round();
    final dy = _scrollAccum.dy.round();
    _scrollAccum = Offset.zero;
    if (dx == 0 && dy == 0) return;
    unawaited(_sendInput({'kind': 'scroll', 'dx': -dx, 'dy': -dy}));
  }

  void _sendTypedText() {
    final text = _typeController.text;
    if (text.trim().isEmpty) return;
    _typeController.clear();
    unawaited(_sendInput({'kind': 'type', 'text': text}));
  }

  void _sendNamedKey(String key) {
    unawaited(_sendInput({'kind': 'key', 'key': key}));
  }

  // -------------------------------------------------------------------------
  // Build
  // -------------------------------------------------------------------------

  void _onTransform() {
    final zoomed = _transformController.value.getMaxScaleOnAxis() > 1.02;
    if (zoomed != _zoomed) setState(() => _zoomed = zoomed);
  }

  void _selectView(String? viewId) {
    if (viewId == _selectedViewId) viewId = null; // tap again = desktop
    setState(() {
      _selectedViewId = viewId;
      _keyboardOpen = false;
    });
    _transformController.value = Matrix4.identity();
    _restartPollTimer();
    unawaited(_pollFrame());
  }

  Future<void> _runControl(Future<String?> Function() action) async {
    final error = await action();
    if (error != null && mounted) {
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(error)));
    }
  }

  @override
  Widget build(BuildContext context) {
    final computerState = ref.watch(computerProvider);
    final computer = computerState.byBot[widget.botId];
    final bot = ref
        .watch(botsProvider)
        .bots
        .where((b) => b.id == widget.botId)
        .firstOrNull;
    final user = ref.watch(authProvider).user;
    final windows = computerState.windowsByBot[widget.botId] ?? const <ComputerWindow>[];

    // Live plumbing reacts to state pushed over the socket.
    ref.listen<ComputerState>(computerProvider, (prev, next) {
      final before = prev?.byBot[widget.botId];
      final after = next.byBot[widget.botId];
      if (after == null) return;
      if (before?.state != after.state) _syncTimers();
      if (after.isLive && after.windowsCount != before?.windowsCount) {
        unawaited(ref.read(computerProvider.notifier).fetchViews(widget.botId));
      }
      // Refetch the desktop preview as soon as its revision changes; the
      // slow poll is the fallback for a missed event.
      if (_selectedViewId == null &&
          after.previewRevision != before?.previewRevision) {
        unawaited(_pollFrame());
      }
    });

    final status = computerState.status;
    final available = status?.available == true;
    final canOperate = (user?.role == 'admin' || (bot?.canOperate ?? false)) &&
        !computerState.controlDenied.contains(widget.botId);
    final drivingMe = computer?.driver != null &&
        computer!.driver!.userId == user?.id;
    final needsYou = computer?.state == ComputerStates.needsYou;
    final live = computer?.isLive ?? false;
    final activeViewId = _activeViewId;

    return Scaffold(
      backgroundColor: Colors.black,
      appBar: AppBar(
        backgroundColor: Colors.black,
        foregroundColor: Colors.white,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () => context.pop(),
        ),
        title: Text(
          bot != null ? '${bot.name}’s computer' : 'Computer',
          overflow: TextOverflow.ellipsis,
        ),
        actions: [
          if (available) ...[
            _StateChip(
              computer: computer,
              bot: bot,
              drivingMe: drivingMe,
              needsYou: needsYou,
            ),
            if (canOperate && live)
              drivingMe
                  ? _BarAction(
                      label: 'Hand back',
                      onPressed: () => _runControl(
                        () => ref.read(computerProvider.notifier).handback(widget.botId),
                      ),
                    )
                  : _BarAction(
                      label: 'Take over',
                      onPressed: () => _runControl(
                        () => needsYou
                            ? ref.read(computerProvider.notifier).respondNeedsYou(widget.botId, 'takeover')
                            : ref.read(computerProvider.notifier).takeover(widget.botId),
                      ),
                    ),
            if (drivingMe && activeViewId != null)
              IconButton(
                icon: Icon(_keyboardOpen ? Icons.keyboard_hide : Icons.keyboard),
                tooltip: 'Type on the computer',
                onPressed: () => setState(() => _keyboardOpen = !_keyboardOpen),
              ),
          ],
          const SizedBox(width: 4),
        ],
      ),
      body: !available
          // The entry points hide this screen while the probe is
          // unavailable; a direct navigation shows nothing either.
          ? const SizedBox.shrink()
          : Column(
              children: [
                if (needsYou && computer?.needsYou != null)
                  _NeedsYouBanner(
                    reason: computer!.needsYou!,
                    canOperate: canOperate,
                    onTakeover: () => _runControl(
                      () => ref.read(computerProvider.notifier).respondNeedsYou(widget.botId, 'takeover'),
                    ),
                    onSkip: () => _runControl(
                      () => ref.read(computerProvider.notifier).respondNeedsYou(widget.botId, 'skip'),
                    ),
                  ),
                if (live && computer?.activity != null)
                  _ActivityLine(text: computer!.activity!.text),
                Expanded(
                  child: _buildStage(
                    computer,
                    live: live,
                    activeViewId: activeViewId,
                    drivingMe: drivingMe,
                    canOperate: canOperate,
                  ),
                ),
                if (live && windows.isNotEmpty)
                  _WindowSwitcher(
                    windows: windows,
                    selectedId: activeViewId,
                    onSelect: _selectView,
                  ),
                if (_keyboardOpen && drivingMe && activeViewId != null)
                  _KeyboardBar(
                    controller: _typeController,
                    onSendText: _sendTypedText,
                    onSendKey: _sendNamedKey,
                  ),
              ],
            ),
    );
  }

  Widget _buildStage(
    BotComputerStatus? computer, {
    required bool live,
    required String? activeViewId,
    required bool drivingMe,
    required bool canOperate,
  }) {
    if (live && _frameBytes != null) {
      return _buildFrame(drivingMe: drivingMe, activeViewId: activeViewId);
    }
    if (live) {
      return const _StageMessage(
        pending: true,
        message: 'Waiting for the first frame…',
      );
    }
    switch (computer?.state) {
      case ComputerStates.building:
        return _BuildProgress(build: computer?.build, lastError: computer?.lastError);
      case ComputerStates.starting:
        return const _StageMessage(pending: true, message: 'Starting the computer…');
      case ComputerStates.asleep:
        return _StageMessage(
          message: 'The computer is asleep.',
          actionLabel: canOperate ? 'Wake' : null,
          onAction: () => _runControl(
            () => ref.read(computerProvider.notifier).wake(widget.botId),
          ),
        );
      case ComputerStates.off:
        return _StageMessage(
          message: 'The computer is off.',
          actionLabel: canOperate ? 'Turn on' : null,
          onAction: () => _runControl(
            () => ref.read(computerProvider.notifier).wake(widget.botId),
          ),
        );
      default:
        return _StageMessage(
          message: computer?.lastError ?? 'The computer is unavailable.',
        );
    }
  }

  Widget _buildFrame({required bool drivingMe, required String? activeViewId}) {
    final inputTarget = drivingMe && activeViewId != null;
    return LayoutBuilder(
      builder: (context, constraints) {
        final fitted = _fittedSize(constraints.biggest);
        return Stack(
          children: [
            InteractiveViewer(
              transformationController: _transformController,
              minScale: 1,
              maxScale: 8,
              // While driving at fit-scale a drag scrolls the window; zoomed
              // in, a drag pans the picture. Pinch-zoom always works.
              panEnabled: !inputTarget || _zoomed,
              child: SizedBox.expand(
                child: Center(
                  child: SizedBox(
                    width: fitted.width,
                    height: fitted.height,
                    child: GestureDetector(
                      key: _frameKey,
                      onTapUp: inputTarget ? _onTapUp : null,
                      onLongPressStart: inputTarget ? _onLongPressStart : null,
                      onPanUpdate: inputTarget && !_zoomed ? _onPanUpdate : null,
                      onPanEnd: inputTarget && !_zoomed ? _onPanEnd : null,
                      child: Image.memory(
                        _frameBytes!,
                        fit: BoxFit.fill,
                        gaplessPlayback: true,
                        filterQuality: FilterQuality.medium,
                      ),
                    ),
                  ),
                ),
              ),
            ),
            if (drivingMe && activeViewId == null)
              const Positioned(
                left: 0,
                right: 0,
                bottom: 12,
                child: IgnorePointer(
                  child: Center(
                    child: _HintPill(
                      'Pick a window below to click, scroll and type.',
                    ),
                  ),
                ),
              ),
          ],
        );
      },
    );
  }

  /// The frame's natural aspect fitted into the viewport, so the widget the
  /// gestures land on is exactly the displayed image (no letterbox offset).
  Size _fittedSize(Size viewport) {
    final natural = _naturalSize;
    if (natural == null || natural.width <= 0 || natural.height <= 0) {
      return viewport;
    }
    final scale = (viewport.width / natural.width) < (viewport.height / natural.height)
        ? viewport.width / natural.width
        : viewport.height / natural.height;
    return Size(natural.width * scale, natural.height * scale);
  }
}

/// Who is driving, or the computer's state when nobody is.
class _StateChip extends StatelessWidget {
  const _StateChip({
    required this.computer,
    required this.bot,
    required this.drivingMe,
    required this.needsYou,
  });

  final BotComputerStatus? computer;
  final Bot? bot;
  final bool drivingMe;
  final bool needsYou;

  @override
  Widget build(BuildContext context) {
    final String label;
    final bool amber;
    if (needsYou) {
      label = 'Needs you';
      amber = true;
    } else if (drivingMe) {
      label = 'You’re driving · ${bot?.name ?? 'the bot'} waits';
      amber = true;
    } else if (computer?.driver != null) {
      label = '${computer!.driver!.name} is driving';
      amber = false;
    } else if (computer?.state == ComputerStates.awake) {
      label = '${bot?.name ?? 'The bot'} is driving';
      amber = false;
    } else {
      label = switch (computer?.state) {
        ComputerStates.asleep => 'Asleep',
        ComputerStates.building => 'Building…',
        ComputerStates.starting => 'Starting…',
        _ => 'Off',
      };
      amber = false;
    }
    return Center(
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
        decoration: BoxDecoration(
          color: amber ? Colors.amber.shade800 : Colors.white24,
          borderRadius: BorderRadius.circular(999),
        ),
        child: Text(
          label,
          style: const TextStyle(color: Colors.white, fontSize: 12),
          overflow: TextOverflow.ellipsis,
        ),
      ),
    );
  }
}

class _BarAction extends StatelessWidget {
  const _BarAction({required this.label, required this.onPressed});

  final String label;
  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.only(left: 4),
        child: OutlinedButton(
          onPressed: onPressed,
          style: OutlinedButton.styleFrom(
            foregroundColor: Colors.white,
            side: const BorderSide(color: Colors.white54),
            padding: const EdgeInsets.symmetric(horizontal: 12),
            minimumSize: const Size(0, 32),
          ),
          child: Text(label, style: const TextStyle(fontSize: 13)),
        ),
      ),
    );
  }
}

class _NeedsYouBanner extends StatelessWidget {
  const _NeedsYouBanner({
    required this.reason,
    required this.canOperate,
    required this.onTakeover,
    required this.onSkip,
  });

  final String reason;
  final bool canOperate;
  final VoidCallback onTakeover;
  final VoidCallback onSkip;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      color: Colors.amber.shade900,
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      child: Row(
        children: [
          const Icon(Icons.front_hand_outlined, color: Colors.white, size: 18),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              reason,
              style: const TextStyle(color: Colors.white, fontSize: 13),
            ),
          ),
          if (canOperate) ...[
            TextButton(
              onPressed: onTakeover,
              child: const Text('Take over', style: TextStyle(color: Colors.white)),
            ),
            TextButton(
              onPressed: onSkip,
              child: const Text('Skip this step', style: TextStyle(color: Colors.white70)),
            ),
          ],
        ],
      ),
    );
  }
}

class _ActivityLine extends StatelessWidget {
  const _ActivityLine({required this.text});

  final String text;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      color: Colors.white10,
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      child: Text(
        text,
        style: const TextStyle(color: Colors.white70, fontSize: 12),
        overflow: TextOverflow.ellipsis,
        maxLines: 1,
      ),
    );
  }
}

class _StageMessage extends StatelessWidget {
  const _StageMessage({required this.message, this.pending = false, this.actionLabel, this.onAction});

  final String message;
  final bool pending;
  final String? actionLabel;
  final VoidCallback? onAction;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (pending)
            const SizedBox(
              width: 22,
              height: 22,
              child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white70),
            )
          else
            const Icon(Icons.desktop_windows_outlined, color: Colors.white38, size: 40),
          const SizedBox(height: 12),
          Text(message, style: const TextStyle(color: Colors.white70)),
          if (actionLabel != null && onAction != null) ...[
            const SizedBox(height: 16),
            FilledButton(onPressed: onAction, child: Text(actionLabel!)),
          ],
        ],
      ),
    );
  }
}

/// First-wake build progress — only the real build fields, when present.
class _BuildProgress extends StatelessWidget {
  const _BuildProgress({required this.build, required this.lastError});

  final ComputerBuild? build;
  final String? lastError;

  @override
  Widget build(BuildContext context) {
    final step = build?.step;
    final total = build?.total;
    final line = build?.line ?? '';
    final error = build?.error ?? lastError;
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const SizedBox(
              width: 22,
              height: 22,
              child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white70),
            ),
            const SizedBox(height: 12),
            const Text('Building the computer…', style: TextStyle(color: Colors.white70)),
            if (step != null && total != null) ...[
              const SizedBox(height: 6),
              Text(
                'Step $step of $total',
                style: const TextStyle(color: Colors.white54, fontSize: 12),
              ),
            ],
            if (line.isNotEmpty) ...[
              const SizedBox(height: 6),
              Text(
                line,
                style: const TextStyle(color: Colors.white38, fontSize: 11),
                overflow: TextOverflow.ellipsis,
                maxLines: 1,
              ),
            ],
            if (error != null && error.isNotEmpty) ...[
              const SizedBox(height: 10),
              Text(
                error,
                style: TextStyle(color: Colors.red.shade300, fontSize: 12),
                textAlign: TextAlign.center,
              ),
            ],
          ],
        ),
      ),
    );
  }
}

/// The open windows, from the real views list. "Desktop" returns to the
/// full-desktop preview; tapping the selected window does the same.
class _WindowSwitcher extends StatelessWidget {
  const _WindowSwitcher({
    required this.windows,
    required this.selectedId,
    required this.onSelect,
  });

  final List<ComputerWindow> windows;
  final String? selectedId;
  final ValueChanged<String?> onSelect;

  IconData _iconFor(String kind) {
    switch (kind) {
      case 'web':
        return Icons.public;
      case 'terminal':
        return Icons.terminal;
      case 'editor':
        return Icons.description_outlined;
      default:
        return Icons.widgets_outlined;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 52,
      color: Colors.black,
      child: ListView(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
        children: [
          _WindowChip(
            icon: Icons.desktop_windows_outlined,
            label: 'Desktop',
            selected: selectedId == null,
            onTap: () => onSelect(null),
          ),
          for (final window in windows)
            _WindowChip(
              icon: _iconFor(window.kind),
              label: window.title.isNotEmpty ? window.title : window.app,
              detail: window.app,
              selected: window.id == selectedId,
              onTap: () => onSelect(window.id),
            ),
        ],
      ),
    );
  }
}

class _WindowChip extends StatelessWidget {
  const _WindowChip({
    required this.icon,
    required this.label,
    required this.selected,
    required this.onTap,
    this.detail,
  });

  final IconData icon;
  final String label;
  final String? detail;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 4),
      child: Material(
        color: selected ? Colors.white24 : Colors.white10,
        borderRadius: BorderRadius.circular(8),
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(8),
          child: Container(
            constraints: const BoxConstraints(maxWidth: 180),
            padding: const EdgeInsets.symmetric(horizontal: 10),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(icon, size: 15, color: Colors.white70),
                const SizedBox(width: 6),
                Flexible(
                  child: Text.rich(
                    TextSpan(
                      children: [
                        TextSpan(
                          text: label,
                          style: const TextStyle(color: Colors.white, fontSize: 12),
                        ),
                        if (detail != null && detail!.isNotEmpty && detail != label)
                          TextSpan(
                            text: ' · $detail',
                            style: const TextStyle(color: Colors.white54, fontSize: 11),
                          ),
                      ],
                    ),
                    overflow: TextOverflow.ellipsis,
                    maxLines: 1,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

/// The keyboard toggle's bar: free text goes out as a `type` input; the
/// named keys go out as `key` inputs.
class _KeyboardBar extends StatelessWidget {
  const _KeyboardBar({
    required this.controller,
    required this.onSendText,
    required this.onSendKey,
  });

  final TextEditingController controller;
  final VoidCallback onSendText;
  final ValueChanged<String> onSendKey;

  @override
  Widget build(BuildContext context) {
    return Container(
      color: Colors.black,
      padding: EdgeInsets.only(
        left: 8,
        right: 8,
        top: 6,
        bottom: 6 + MediaQuery.of(context).viewInsets.bottom,
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Row(
            children: [
              Expanded(
                child: TextField(
                  controller: controller,
                  style: const TextStyle(color: Colors.white),
                  decoration: InputDecoration(
                    hintText: 'Type on the computer · Enter sends',
                    hintStyle: const TextStyle(color: Colors.white38),
                    isDense: true,
                    filled: true,
                    fillColor: Colors.white10,
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(8),
                      borderSide: BorderSide.none,
                    ),
                  ),
                  textInputAction: TextInputAction.send,
                  onSubmitted: (_) => onSendText(),
                ),
              ),
              IconButton(
                icon: const Icon(Icons.send, color: Colors.white70, size: 20),
                onPressed: onSendText,
              ),
            ],
          ),
          const SizedBox(height: 4),
          SizedBox(
            height: 34,
            child: ListView(
              scrollDirection: Axis.horizontal,
              children: [
                for (final entry in _namedKeys.entries)
                  Padding(
                    padding: const EdgeInsets.only(right: 6),
                    child: OutlinedButton(
                      onPressed: () => onSendKey(entry.value),
                      style: OutlinedButton.styleFrom(
                        foregroundColor: Colors.white70,
                        side: const BorderSide(color: Colors.white24),
                        padding: const EdgeInsets.symmetric(horizontal: 10),
                        minimumSize: const Size(0, 30),
                      ),
                      child: Text(entry.key, style: const TextStyle(fontSize: 12)),
                    ),
                  ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _HintPill extends StatelessWidget {
  const _HintPill(this.text);

  final String text;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(
        color: Colors.black87,
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: Colors.white24),
      ),
      child: Text(
        text,
        style: const TextStyle(color: Colors.white70, fontSize: 12),
      ),
    );
  }
}
