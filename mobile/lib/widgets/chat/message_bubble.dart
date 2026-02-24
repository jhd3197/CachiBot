import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_markdown/flutter_markdown.dart';

import '../../core/theme/code_theme.dart';
import '../../core/utils/time_utils.dart';
import '../../models/chat.dart';
import '../../models/usage.dart';
import '../../models/ws_message.dart';

class MessageBubble extends StatelessWidget {
  const MessageBubble({
    required this.message,
    this.isStreaming = false,
    super.key,
  });

  final ChatMessage message;
  final bool isStreaming;

  bool get _isUser => message.role == 'user';

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
      child: Column(
        crossAxisAlignment:
            _isUser ? CrossAxisAlignment.end : CrossAxisAlignment.start,
        children: [
          // Thinking expansion
          if (!_isUser &&
              message.thinking != null &&
              message.thinking!.isNotEmpty)
            _ThinkingExpansion(thinking: message.thinking!),

          // Tool calls with result preview
          if (!_isUser && message.toolCalls.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(bottom: 4),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: message.toolCalls.map((call) {
                  return Padding(
                    padding: const EdgeInsets.only(bottom: 2),
                    child: _ToolChipWithResult(call: call),
                  );
                }).toList(),
              ),
            ),

          // Message bubble with long-press copy for assistant
          GestureDetector(
            onLongPress:
                !_isUser && message.content.isNotEmpty && !isStreaming
                    ? () => _showCopyMenu(context)
                    : null,
            child: Container(
              constraints: BoxConstraints(
                maxWidth: MediaQuery.of(context).size.width * 0.85,
              ),
              decoration: BoxDecoration(
                color: _isUser
                    ? theme.colorScheme.primary
                    : theme.colorScheme.surfaceContainerHigh,
                borderRadius: BorderRadius.only(
                  topLeft: const Radius.circular(16),
                  topRight: const Radius.circular(16),
                  bottomLeft: Radius.circular(_isUser ? 16 : 4),
                  bottomRight: Radius.circular(_isUser ? 4 : 16),
                ),
              ),
              padding:
                  const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
              child: message.content.isEmpty && isStreaming
                  ? _StreamingDots(color: theme.colorScheme.onSurface)
                  : _isUser
                      ? Text(
                          message.content,
                          style: theme.textTheme.bodyMedium?.copyWith(
                            color: theme.colorScheme.onPrimary,
                          ),
                        )
                      : MarkdownBody(
                          data: message.content,
                          selectable: true,
                          styleSheet: MarkdownStyleSheet(
                            p: theme.textTheme.bodyMedium?.copyWith(
                              color: theme.colorScheme.onSurface,
                            ),
                            code: CodeTheme.inlineCode(
                              color: theme.colorScheme.primary,
                            ),
                            codeblockDecoration: BoxDecoration(
                              color:
                                  theme.colorScheme.surfaceContainerHighest,
                              borderRadius: BorderRadius.circular(8),
                            ),
                          ),
                        ),
            ),
          ),

          // Timestamp + usage badge row
          if (!isStreaming)
            Padding(
              padding: const EdgeInsets.only(top: 2),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(
                    formatMessageTime(message.timestamp),
                    style: theme.textTheme.labelSmall?.copyWith(
                      color: theme.colorScheme.onSurface
                          .withValues(alpha: 0.4),
                      fontSize: 10,
                    ),
                  ),
                  if (!_isUser && _hasUsage) ...[
                    const SizedBox(width: 6),
                    _UsageBadge(
                      usage: UsageInfo.fromJson(
                        message.metadata['usage'] as Map<String, dynamic>,
                      ),
                    ),
                  ],
                ],
              ),
            ),
        ],
      ),
    );
  }

  bool get _hasUsage =>
      message.metadata.containsKey('usage') &&
      message.metadata['usage'] is Map<String, dynamic>;

  void _showCopyMenu(BuildContext context) {
    Clipboard.setData(ClipboardData(text: message.content));
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text('Copied to clipboard'),
        duration: Duration(seconds: 2),
      ),
    );
  }
}

class _ToolChipWithResult extends StatelessWidget {
  const _ToolChipWithResult({required this.call});

  final ToolCall call;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isDone = !call.isRunning;
    final isSuccess = call.success ?? true;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Chip(
          avatar: isDone
              ? Icon(
                  isSuccess ? Icons.check_circle : Icons.error,
                  size: 16,
                  color: isSuccess
                      ? theme.colorScheme.primary
                      : theme.colorScheme.error,
                )
              : SizedBox(
                  width: 14,
                  height: 14,
                  child: CircularProgressIndicator(
                    strokeWidth: 2,
                    color: theme.colorScheme.primary,
                  ),
                ),
          label: Text(
            call.tool,
            style: theme.textTheme.labelSmall,
          ),
          visualDensity: VisualDensity.compact,
          materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
        ),
        // Brief result text for completed tools
        if (isDone && call.result != null)
          Padding(
            padding: const EdgeInsets.only(left: 8, bottom: 2),
            child: Text(
              _truncateResult(call.result),
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: theme.textTheme.bodySmall?.copyWith(
                color:
                    theme.colorScheme.onSurface.withValues(alpha: 0.5),
                fontSize: 11,
              ),
            ),
          ),
      ],
    );
  }

  String _truncateResult(dynamic result) {
    final text = result.toString();
    if (text.length > 100) return '${text.substring(0, 100)}...';
    return text;
  }
}

class _ThinkingExpansion extends StatefulWidget {
  const _ThinkingExpansion({required this.thinking});

  final String thinking;

  @override
  State<_ThinkingExpansion> createState() => _ThinkingExpansionState();
}

class _ThinkingExpansionState extends State<_ThinkingExpansion> {
  bool _expanded = false;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Padding(
      padding: const EdgeInsets.only(bottom: 4),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          GestureDetector(
            onTap: () => setState(() => _expanded = !_expanded),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(
                  Icons.psychology,
                  size: 14,
                  color: theme.colorScheme.onSurface
                      .withValues(alpha: 0.5),
                ),
                const SizedBox(width: 4),
                Text(
                  'Thinking...',
                  style: theme.textTheme.labelSmall?.copyWith(
                    color: theme.colorScheme.onSurface
                        .withValues(alpha: 0.5),
                    fontStyle: FontStyle.italic,
                  ),
                ),
                const SizedBox(width: 4),
                Icon(
                  _expanded
                      ? Icons.expand_less
                      : Icons.expand_more,
                  size: 14,
                  color: theme.colorScheme.onSurface
                      .withValues(alpha: 0.5),
                ),
              ],
            ),
          ),
          if (_expanded)
            Container(
              margin: const EdgeInsets.only(top: 4),
              padding: const EdgeInsets.all(8),
              constraints: const BoxConstraints(maxHeight: 200),
              decoration: BoxDecoration(
                color: theme.colorScheme.surfaceContainerHighest
                    .withValues(alpha: 0.5),
                borderRadius: BorderRadius.circular(8),
              ),
              child: SingleChildScrollView(
                child: Text(
                  widget.thinking,
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: theme.colorScheme.onSurface
                        .withValues(alpha: 0.6),
                    fontStyle: FontStyle.italic,
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }
}

class _UsageBadge extends StatelessWidget {
  const _UsageBadge({required this.usage});

  final UsageInfo usage;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return GestureDetector(
      onTap: () => _showUsageSheet(context),
      child: Icon(
        Icons.info_outline,
        size: 14,
        color: theme.colorScheme.onSurface.withValues(alpha: 0.4),
      ),
    );
  }

  void _showUsageSheet(BuildContext context) {
    final theme = Theme.of(context);

    showModalBottomSheet(
      context: context,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (context) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Usage',
                style: theme.textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.w600,
                ),
              ),
              const SizedBox(height: 16),
              _UsageRow(
                icon: Icons.bolt,
                label: 'Tokens',
                value: usage.formattedTokens,
              ),
              _UsageRow(
                icon: Icons.attach_money,
                label: 'Cost',
                value: usage.formattedCost,
              ),
              _UsageRow(
                icon: Icons.timer_outlined,
                label: 'Time',
                value: usage.formattedElapsed,
              ),
              _UsageRow(
                icon: Icons.loop,
                label: 'Iterations',
                value: '${usage.iterations}',
              ),
              if (usage.tokensPerSecond > 0)
                _UsageRow(
                  icon: Icons.speed,
                  label: 'Speed',
                  value:
                      '${usage.tokensPerSecond.toStringAsFixed(0)} tok/s',
                ),
            ],
          ),
        ),
      ),
    );
  }
}

class _UsageRow extends StatelessWidget {
  const _UsageRow({
    required this.icon,
    required this.label,
    required this.value,
  });

  final IconData icon;
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        children: [
          Icon(
            icon,
            size: 16,
            color: theme.colorScheme.onSurface.withValues(alpha: 0.5),
          ),
          const SizedBox(width: 8),
          Text(
            label,
            style: theme.textTheme.bodyMedium?.copyWith(
              color:
                  theme.colorScheme.onSurface.withValues(alpha: 0.6),
            ),
          ),
          const Spacer(),
          Text(
            value,
            style: theme.textTheme.bodyMedium?.copyWith(
              fontWeight: FontWeight.w500,
            ),
          ),
        ],
      ),
    );
  }
}

class _StreamingDots extends StatefulWidget {
  const _StreamingDots({required this.color});

  final Color color;

  @override
  State<_StreamingDots> createState() => _StreamingDotsState();
}

class _StreamingDotsState extends State<_StreamingDots>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 800),
    )..repeat();
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _controller,
      builder: (context, _) {
        final dots = '.' * ((_controller.value * 3).floor() + 1);
        return Text(
          dots,
          style: TextStyle(
            color: widget.color.withValues(alpha: 0.5),
            fontSize: 18,
            letterSpacing: 2,
          ),
        );
      },
    );
  }
}
