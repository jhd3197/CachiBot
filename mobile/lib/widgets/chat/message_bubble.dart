import 'package:flutter/material.dart';
import 'package:flutter_markdown/flutter_markdown.dart';

import '../../core/theme/code_theme.dart';
import '../../models/chat.dart';
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
          // Thinking indicator
          if (!_isUser && message.thinking != null && message.thinking!.isNotEmpty)
            _ThinkingChip(thinking: message.thinking!),

          // Tool calls
          if (!_isUser && message.toolCalls.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(bottom: 4),
              child: Wrap(
                spacing: 6,
                runSpacing: 4,
                children: message.toolCalls.map(_buildToolChip).toList(),
              ),
            ),

          // Message bubble
          Container(
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
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
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
                            color: theme.colorScheme.surfaceContainerHighest,
                            borderRadius: BorderRadius.circular(8),
                          ),
                        ),
                      ),
          ),
        ],
      ),
    );
  }

  Widget _buildToolChip(ToolCall call) {
    return Builder(builder: (context) {
      final theme = Theme.of(context);
      final isDone = !call.isRunning;
      final isSuccess = call.success ?? true;

      return Chip(
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
      );
    });
  }
}

class _ThinkingChip extends StatelessWidget {
  const _ThinkingChip({required this.thinking});

  final String thinking;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Padding(
      padding: const EdgeInsets.only(bottom: 4),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            Icons.psychology,
            size: 14,
            color: theme.colorScheme.onSurface.withValues(alpha: 0.5),
          ),
          const SizedBox(width: 4),
          Text(
            'Thinking...',
            style: theme.textTheme.labelSmall?.copyWith(
              color: theme.colorScheme.onSurface.withValues(alpha: 0.5),
              fontStyle: FontStyle.italic,
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
