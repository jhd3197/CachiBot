import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/computer.dart';
import '../models/ws_message.dart';
import '../services/api/computer_service.dart';
import 'service_providers.dart';

/// Live computer state for the app, mirroring the web `computer` store.
///
/// Holds the Docker probe summary ([ComputerState.status]) and, per bot,
/// the computer record fed by GET /api/bots/{id}/computer and kept live by
/// `computer_update` WebSocket events (activity, windows count, watchers,
/// driver, the needs-you reason and the preview revision). The probe
/// decides whether any computer UI may appear at all. Deliberately not
/// persisted — the server owns the state.
class ComputerState {
  const ComputerState({
    this.status,
    this.statusLoaded = false,
    this.byBot = const {},
    this.windowsByBot = const {},
    this.controlDenied = const {},
  });

  /// Docker probe summary; null until the first fetch.
  final DockerProbeStatus? status;

  /// Whether the probe was fetched at least once (even if it failed).
  final bool statusLoaded;

  /// botId -> latest computer state (REST response or WS event).
  final Map<String, BotComputerStatus> byBot;

  /// botId -> open windows (app + title), from GET .../computer/views.
  final Map<String, List<ComputerWindow>> windowsByBot;

  /// botIds where a control call already answered 403 — the controls that
  /// failed stay hidden rather than failing again.
  final Set<String> controlDenied;

  ComputerState copyWith({
    DockerProbeStatus? status,
    bool? statusLoaded,
    Map<String, BotComputerStatus>? byBot,
    Map<String, List<ComputerWindow>>? windowsByBot,
    Set<String>? controlDenied,
  }) {
    return ComputerState(
      status: status ?? this.status,
      statusLoaded: statusLoaded ?? this.statusLoaded,
      byBot: byBot ?? this.byBot,
      windowsByBot: windowsByBot ?? this.windowsByBot,
      controlDenied: controlDenied ?? this.controlDenied,
    );
  }
}

class ComputerNotifier extends StateNotifier<ComputerState> {
  ComputerNotifier(this._ref) : super(const ComputerState()) {
    _wsSubscription =
        _ref.read(wsServiceProvider).events.listen(_handleEvent);
  }

  final Ref _ref;
  StreamSubscription<WSEvent>? _wsSubscription;
  final Set<String> _loadingFor = {};

  ComputerService get _service => _ref.read(computerServiceProvider);

  @override
  void dispose() {
    _wsSubscription?.cancel();
    super.dispose();
  }

  void _handleEvent(WSEvent event) {
    if (event.type == WSEvent.computerUpdate) {
      applyUpdate(event.payload);
    } else if (event.type == WSEvent.reconnected) {
      // Catch up after a dropped socket: the probe and every bot we hold.
      unawaited(fetchStatus());
      for (final botId in state.byBot.keys.toList()) {
        unawaited(_refreshBot(botId));
      }
    }
  }

  /// Fetch the Docker probe summary. An unreachable probe reads as
  /// "no computer": every computer surface stays hidden.
  Future<void> fetchStatus({bool force = false}) async {
    if (state.statusLoaded && !force) return;
    try {
      final status = await _service.getStatus();
      state = state.copyWith(status: status, statusLoaded: true);
    } catch (_) {
      state = state.copyWith(
        status: DockerProbeStatus.unavailable,
        statusLoaded: true,
      );
    }
  }

  /// Load one bot's computer state once (call where a computer view mounts).
  Future<void> ensureForBot(String botId) async {
    if (state.byBot.containsKey(botId) || _loadingFor.contains(botId)) return;
    await _refreshBot(botId);
  }

  Future<void> _refreshBot(String botId) async {
    if (_loadingFor.contains(botId)) return;
    _loadingFor.add(botId);
    try {
      final computer = await _service.getBotComputer(botId);
      state = state.copyWith(byBot: {...state.byBot, botId: computer});
    } catch (_) {
      // Unreachable: keep the last real record; never invent one.
    } finally {
      _loadingFor.remove(botId);
    }
  }

  /// Load one bot's open windows + activity. Asleep or unreachable keeps
  /// the last real list; nothing is invented.
  Future<void> fetchViews(String botId) async {
    try {
      final views = await _service.getViews(botId);
      state = state.copyWith(
        windowsByBot: {...state.windowsByBot, botId: views.windows},
      );
    } catch (_) {}
  }

  /// Insert or replace one record (from the API or a `computer_update`).
  void applyUpdate(Map<String, dynamic> payload) {
    final botId = payload['botId'] as String?;
    if (botId == null) return;
    state = state.copyWith(
      byBot: {...state.byBot, botId: BotComputerStatus.fromUpdatePayload(payload)},
    );
  }

  /// Turn the computer on. Returns an error message to show, or null.
  Future<String?> wake(String botId) {
    return _control(botId, () => _service.wakeComputer(botId));
  }

  /// Take over the computer (operator+): the bot waits while you drive.
  Future<String?> takeover(String botId) {
    return _control(botId, () => _service.takeover(botId));
  }

  /// Hand the computer back (operator+): releases the control lease.
  Future<String?> handback(String botId) {
    return _control(botId, () => _service.handback(botId));
  }

  /// Answer a needs-you: `takeover`, or `skip` (the documented closest
  /// refusal — an approval is denied; a needs-person pause stops the run).
  Future<String?> respondNeedsYou(String botId, String action) {
    return _control(botId, () => _service.respondNeedsYou(botId, action));
  }

  /// Send one piece of person input (operator+, only while this user holds
  /// the take-over): click (left/right), scroll, type, key.
  Future<String?> sendInput(String botId, Map<String, dynamic> input) async {
    try {
      await _service.sendInput(botId, input);
      return null;
    } catch (e) {
      return _controlError(botId, e);
    }
  }

  Future<String?> _control(
    String botId,
    Future<BotComputerStatus> Function() call,
  ) async {
    try {
      final computer = await call();
      state = state.copyWith(byBot: {...state.byBot, botId: computer});
      return null;
    } catch (e) {
      return _controlError(botId, e);
    }
  }

  /// A 403 hides the control that already failed; other errors are just
  /// reported. Returns the message to show.
  String _controlError(String botId, Object error) {
    if (error is ComputerApiException) {
      if (error.isForbidden) {
        state = state.copyWith(
          controlDenied: {...state.controlDenied, botId},
        );
      }
      return error.message;
    }
    if (error is DioException) {
      if (error.response?.statusCode == 403) {
        state = state.copyWith(
          controlDenied: {...state.controlDenied, botId},
        );
      }
      final data = error.response?.data;
      if (data is Map<String, dynamic> && data['detail'] is String) {
        return data['detail'] as String;
      }
      return error.message ?? 'The computer refused that';
    }
    return error.toString();
  }
}

final computerServiceProvider = Provider<ComputerService>((ref) {
  final client = ref.watch(apiClientProvider);
  return ComputerService(client);
});

final computerProvider =
    StateNotifierProvider<ComputerNotifier, ComputerState>((ref) {
  return ComputerNotifier(ref);
});
