import 'dart:async';
import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../../core/theme/app_colors.dart';

/// v2 spinner sizes (docs/design/UI_V2_PLAN.md "L1: v2 loading primitives").
enum CachiSpinnerSize { sm, md, lg }

extension on CachiSpinnerSize {
  double get diameter {
    switch (this) {
      case CachiSpinnerSize.sm:
        return 12;
      case CachiSpinnerSize.md:
        return 14;
      case CachiSpinnerSize.lg:
        return 18;
    }
  }

  double get strokeWidth {
    switch (this) {
      case CachiSpinnerSize.sm:
        return 1.5;
      case CachiSpinnerSize.md:
      case CachiSpinnerSize.lg:
        return 2;
    }
  }
}

/// One thin ring spinner in the muted tertiary text tone.
///
/// - Sizes sm/md/lg = 12/14/18 px, ~2px stroke, 0.75s linear spin.
/// - [color] overrides the default; when null the ring uses the AppColors
///   tertiary text tone for the current brightness.
/// - [delayMs] keeps the ring hidden (but holding its layout space) until
///   the delay has passed, so spinners on fast actions do not flash.
/// - With animations disabled (MediaQuery.disableAnimations) the ring holds
///   still as a static arc instead of spinning.
class CachiSpinner extends StatefulWidget {
  const CachiSpinner({
    super.key,
    this.size = CachiSpinnerSize.md,
    this.color,
    this.delayMs,
    this.semanticLabel = 'Loading',
  });

  final CachiSpinnerSize size;
  final Color? color;
  final int? delayMs;
  final String? semanticLabel;

  @override
  State<CachiSpinner> createState() => _CachiSpinnerState();
}

class _CachiSpinnerState extends State<CachiSpinner>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;
  Timer? _delayTimer;
  bool _visible = false;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 750),
    )..repeat();
    final delayMs = widget.delayMs;
    if (delayMs == null) {
      _visible = true;
    } else {
      _delayTimer = Timer(Duration(milliseconds: delayMs), () {
        if (mounted) setState(() => _visible = true);
      });
    }
  }

  @override
  void dispose() {
    _delayTimer?.cancel();
    _controller.dispose();
    super.dispose();
  }

  Color _defaultColor(Brightness brightness) {
    return brightness == Brightness.light
        ? AppColors.lightTextTertiary
        : AppColors.darkTextTertiary;
  }

  @override
  Widget build(BuildContext context) {
    final diameter = widget.size.diameter;
    final color =
        widget.color ?? _defaultColor(Theme.of(context).brightness);

    if (!_visible) {
      // Hidden until the delay passes, but still holding its layout space.
      return ExcludeSemantics(
        child: SizedBox(width: diameter, height: diameter),
      );
    }

    final Widget ring;
    if (MediaQuery.disableAnimationsOf(context)) {
      ring = CustomPaint(
        size: Size.square(diameter),
        painter: _CachiRingPainter(
          color: color,
          strokeWidth: widget.size.strokeWidth,
        ),
      );
    } else {
      ring = AnimatedBuilder(
        animation: _controller,
        builder: (context, child) {
          return Transform.rotate(
            angle: _controller.value * 2 * math.pi,
            child: child,
          );
        },
        child: CustomPaint(
          size: Size.square(diameter),
          painter: _CachiRingPainter(
            color: color,
            strokeWidth: widget.size.strokeWidth,
          ),
        ),
      );
    }

    return Semantics(
      label: widget.semanticLabel,
      child: SizedBox(width: diameter, height: diameter, child: ring),
    );
  }
}

class _CachiRingPainter extends CustomPainter {
  const _CachiRingPainter({required this.color, required this.strokeWidth});

  final Color color;
  final double strokeWidth;

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = color
      ..style = PaintingStyle.stroke
      ..strokeWidth = strokeWidth
      ..strokeCap = StrokeCap.round;
    final inset = strokeWidth / 2;
    final rect = Offset(inset, inset) &
        Size(size.width - strokeWidth, size.height - strokeWidth);
    // Leave a gap at the top, like the v2 CSS ring.
    canvas.drawArc(rect, -math.pi / 2, math.pi * 1.5, false, paint);
  }

  @override
  bool shouldRepaint(_CachiRingPainter oldDelegate) =>
      oldDelegate.color != color || oldDelegate.strokeWidth != strokeWidth;
}

/// In-panel page-level wait: a centered [CachiSpinner] (lg) with a 200ms
/// delay by default, so fast loads do not flash. [label] renders a muted
/// status line under the spinner (and becomes the Semantics label).
class CachiPageLoading extends StatelessWidget {
  const CachiPageLoading({
    super.key,
    this.label,
    this.delayMs = 200,
    this.size = CachiSpinnerSize.lg,
  });

  final String? label;
  final int delayMs;
  final CachiSpinnerSize size;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isLight = theme.brightness == Brightness.light;
    final textColor = isLight
        ? AppColors.lightTextTertiary
        : AppColors.darkTextTertiary;

    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          CachiSpinner(
            size: size,
            delayMs: delayMs,
            semanticLabel: label ?? 'Loading',
          ),
          if (label != null) ...[
            const SizedBox(height: 12),
            Text(
              label!,
              style: theme.textTheme.bodySmall?.copyWith(color: textColor),
            ),
          ],
        ],
      ),
    );
  }
}

/// A rounded gray placeholder block that gently pulses between the AppColors
/// hover and inset tones. Purely visual (excluded from semantics) — pair it
/// with a real status label when the wait needs announcing. Generic shapes
/// only; holds still when animations are disabled.
class CachiSkeleton extends StatefulWidget {
  const CachiSkeleton({
    super.key,
    this.width = double.infinity,
    this.height = 12,
    this.borderRadius = 12,
  });

  final double width;
  final double height;
  final double borderRadius;

  @override
  State<CachiSkeleton> createState() => _CachiSkeletonState();
}

class _CachiSkeletonState extends State<CachiSkeleton>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1800),
    )..repeat(reverse: true);
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  Widget _block(Color? color) {
    return Container(
      width: widget.width,
      height: widget.height,
      decoration: BoxDecoration(
        color: color,
        borderRadius: BorderRadius.circular(widget.borderRadius),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final isLight = Theme.of(context).brightness == Brightness.light;
    final from = isLight ? AppColors.lightHoverBg : AppColors.darkHoverBg;
    final to = isLight ? AppColors.lightBgInset : AppColors.darkBgInset;

    if (MediaQuery.disableAnimationsOf(context)) {
      return ExcludeSemantics(child: _block(from));
    }

    return ExcludeSemantics(
      child: AnimatedBuilder(
        animation: _controller,
        builder: (context, _) => _block(Color.lerp(from, to, _controller.value)),
      ),
    );
  }
}

/// Generic skeleton rows for list layouts while the first page loads:
/// an avatar block plus two lines per row, no fake counts or labels.
class CachiSkeletonList extends StatelessWidget {
  const CachiSkeletonList({
    super.key,
    this.itemCount = 6,
    this.padding = const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
  });

  final int itemCount;
  final EdgeInsetsGeometry padding;

  @override
  Widget build(BuildContext context) {
    return ListView.builder(
      padding: padding,
      itemCount: itemCount,
      itemBuilder: (context, index) => const Padding(
        padding: EdgeInsets.only(bottom: 14),
        child: _CachiSkeletonRow(),
      ),
    );
  }
}

class _CachiSkeletonRow extends StatelessWidget {
  const _CachiSkeletonRow();

  @override
  Widget build(BuildContext context) {
    return const Row(
      children: [
        CachiSkeleton(width: 40, height: 40),
        SizedBox(width: 12),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              CachiSkeleton(height: 12),
              SizedBox(height: 8),
              FractionallySizedBox(
                widthFactor: 0.55,
                child: CachiSkeleton(height: 12),
              ),
            ],
          ),
        ),
      ],
    );
  }
}

/// Thin, rounded, real-value progress bar for the places that used to show
/// determinate [LinearProgressIndicator]s (work progress). Green accent from
/// the existing palette (the v2 boot greens): shade600 in light mode,
/// shade400 in dark mode.
class CachiProgressBar extends StatelessWidget {
  const CachiProgressBar({
    super.key,
    required this.value,
    this.height = 4,
    this.color,
  });

  final double value;
  final double height;
  final Color? color;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isLight = theme.brightness == Brightness.light;
    final accent = color ??
        (isLight
            ? accentColors[PresetColor.green]!.shade600
            : accentColors[PresetColor.green]!.shade400);

    return ClipRRect(
      borderRadius: BorderRadius.circular(height / 2),
      child: LinearProgressIndicator(
        value: value,
        minHeight: height,
        backgroundColor: theme.colorScheme.surfaceContainerHigh,
        valueColor: AlwaysStoppedAnimation<Color>(accent),
      ),
    );
  }
}
