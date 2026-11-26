import 'package:flutter/material.dart';

import '../../core/theme/app_colors.dart';
import 'loading.dart';

/// Quiet v2 boot screen, shown while the saved session is being restored on
/// cold start. Wordmark with a green "Bot", a small ring, and an optional
/// status line, on the v2 boot background for the current brightness.
class BootScreen extends StatelessWidget {
  const BootScreen({super.key, this.status});

  /// Optional quiet status line (real state only, e.g. "Restoring session...").
  final String? status;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isLight = theme.brightness == Brightness.light;
    final backgroundColor = isLight
        ? AppColors.v2BootBackgroundLight
        : AppColors.v2BootBackgroundDark;
    final accentGreen = isLight
        ? AppColors.v2BootGreenLight
        : AppColors.v2BootGreenDark;
    final textColor = isLight
        ? AppColors.lightTextPrimary
        : AppColors.darkTextPrimary;
    final statusColor = isLight
        ? AppColors.lightTextTertiary
        : AppColors.darkTextTertiary;

    final wordmarkStyle = theme.textTheme.headlineSmall?.copyWith(
      fontWeight: FontWeight.w600,
    );

    return Scaffold(
      backgroundColor: backgroundColor,
      body: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text('Cachi', style: wordmarkStyle?.copyWith(color: textColor)),
                Text(
                  'Bot',
                  style: wordmarkStyle?.copyWith(color: accentGreen),
                ),
              ],
            ),
            const SizedBox(height: 24),
            const CachiSpinner(size: CachiSpinnerSize.lg),
            if (status != null) ...[
              const SizedBox(height: 16),
              Text(
                status!,
                style: theme.textTheme.bodySmall?.copyWith(color: statusColor),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
