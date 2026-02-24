import 'package:flutter/material.dart';

import '../../models/ws_message.dart';

/// Shows the approval bottom sheet and returns the user's decision.
Future<bool?> showApprovalDialog(
  BuildContext context,
  ApprovalRequest request,
) {
  return showModalBottomSheet<bool>(
    context: context,
    isScrollControlled: true,
    shape: const RoundedRectangleBorder(
      borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
    ),
    builder: (context) => _ApprovalSheet(request: request),
  );
}

class _ApprovalSheet extends StatelessWidget {
  const _ApprovalSheet({required this.request});

  final ApprovalRequest request;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isHighRisk =
        request.riskLevel == 'CRITICAL' || request.riskLevel == 'HIGH';

    return SafeArea(
      child: Padding(
        padding: EdgeInsets.only(
          bottom: MediaQuery.of(context).viewInsets.bottom,
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // Handle bar
            Center(
              child: Container(
                margin: const EdgeInsets.only(top: 12),
                width: 40,
                height: 4,
                decoration: BoxDecoration(
                  color: theme.colorScheme.onSurface.withValues(alpha: 0.3),
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
            ),

            // Header
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 16, 20, 0),
              child: Row(
                children: [
                  Icon(
                    Icons.shield,
                    color: isHighRisk
                        ? theme.colorScheme.error
                        : Colors.amber.shade700,
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Text(
                      'Approval Required',
                      style: theme.textTheme.titleLarge?.copyWith(
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ),
                ],
              ),
            ),

            const SizedBox(height: 16),

            // Content (scrollable)
            Flexible(
              child: SingleChildScrollView(
                padding: const EdgeInsets.symmetric(horizontal: 20),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // Risk level badge
                    _RiskBadge(riskLevel: request.riskLevel),
                    const SizedBox(height: 16),

                    // Tool + action
                    Text(
                      'Tool',
                      style: theme.textTheme.labelMedium?.copyWith(
                        color: theme.colorScheme.onSurface
                            .withValues(alpha: 0.6),
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      request.tool,
                      style: theme.textTheme.bodyLarge?.copyWith(
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                    const SizedBox(height: 12),
                    Text(
                      'Action',
                      style: theme.textTheme.labelMedium?.copyWith(
                        color: theme.colorScheme.onSurface
                            .withValues(alpha: 0.6),
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(request.action, style: theme.textTheme.bodyMedium),
                    const SizedBox(height: 16),

                    // Risk reasons
                    if (request.reasons.isNotEmpty) ...[
                      Text(
                        'Risk Factors',
                        style: theme.textTheme.labelMedium?.copyWith(
                          color: theme.colorScheme.onSurface
                              .withValues(alpha: 0.6),
                        ),
                      ),
                      const SizedBox(height: 8),
                      ...request.reasons.map(
                        (reason) => Padding(
                          padding: const EdgeInsets.only(bottom: 4),
                          child: Row(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Container(
                                margin: const EdgeInsets.only(top: 7),
                                width: 6,
                                height: 6,
                                decoration: BoxDecoration(
                                  shape: BoxShape.circle,
                                  color: Colors.amber.shade600,
                                ),
                              ),
                              const SizedBox(width: 8),
                              Expanded(
                                child: Text(
                                  reason,
                                  style: theme.textTheme.bodySmall,
                                ),
                              ),
                            ],
                          ),
                        ),
                      ),
                      const SizedBox(height: 16),
                    ],

                    // Code preview
                    if (request.code != null) ...[
                      Row(
                        children: [
                          Icon(
                            Icons.code,
                            size: 16,
                            color: theme.colorScheme.onSurface
                                .withValues(alpha: 0.6),
                          ),
                          const SizedBox(width: 6),
                          Text(
                            'Code to Execute',
                            style: theme.textTheme.labelMedium?.copyWith(
                              color: theme.colorScheme.onSurface
                                  .withValues(alpha: 0.6),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 8),
                      Container(
                        constraints: const BoxConstraints(maxHeight: 200),
                        width: double.infinity,
                        decoration: BoxDecoration(
                          color: theme.colorScheme.surfaceContainerHighest,
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: SingleChildScrollView(
                          padding: const EdgeInsets.all(12),
                          child: Text(
                            request.code!,
                            style: theme.textTheme.bodySmall?.copyWith(
                              fontFamily: 'monospace',
                            ),
                          ),
                        ),
                      ),
                      const SizedBox(height: 16),
                    ],
                  ],
                ),
              ),
            ),

            // Action buttons
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 8, 20, 16),
              child: Row(
                children: [
                  Expanded(
                    child: OutlinedButton(
                      onPressed: () => Navigator.of(context).pop(false),
                      child: const Text('Deny'),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: FilledButton(
                      style: isHighRisk
                          ? FilledButton.styleFrom(
                              backgroundColor: theme.colorScheme.error,
                            )
                          : null,
                      onPressed: () => Navigator.of(context).pop(true),
                      child: Text(isHighRisk ? 'Allow Anyway' : 'Approve'),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _RiskBadge extends StatelessWidget {
  const _RiskBadge({required this.riskLevel});

  final String riskLevel;

  @override
  Widget build(BuildContext context) {
    final (Color bg, Color fg) = switch (riskLevel) {
      'CRITICAL' => (Colors.red.shade100, Colors.red.shade800),
      'HIGH' => (Colors.orange.shade100, Colors.orange.shade800),
      'MEDIUM' => (Colors.amber.shade100, Colors.amber.shade800),
      'LOW' => (Colors.green.shade100, Colors.green.shade800),
      _ => (Colors.grey.shade100, Colors.grey.shade800),
    };

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.warning_amber_rounded, size: 14, color: fg),
          const SizedBox(width: 4),
          Text(
            riskLevel,
            style: TextStyle(
              color: fg,
              fontSize: 12,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }
}
