import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:speech_to_text/speech_to_text.dart' as stt;

import '../../models/chat.dart';
import '../../providers/chat_provider.dart';
import '../../providers/service_providers.dart';
import '../../widgets/chat/approval_dialog.dart';
import '../../widgets/chat/message_bubble.dart';
import '../../widgets/common/connection_indicator.dart';

class ChatScreen extends ConsumerStatefulWidget {
  const ChatScreen({
    required this.botId,
    this.chatId,
    super.key,
  });

  final String botId;
  final String? chatId;

  @override
  ConsumerState<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends ConsumerState<ChatScreen> {
  final _inputController = TextEditingController();
  final _scrollController = ScrollController();
  final stt.SpeechToText _speech = stt.SpeechToText();
  bool _isListening = false;
  bool _speechAvailable = false;
  String? _sharedText;

  @override
  void initState() {
    super.initState();
    Future.microtask(() {
      ref.read(chatProvider.notifier).openChat(widget.botId, widget.chatId);
    });
    _initSpeech();

    // Handle shared text if passed via extra
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_sharedText != null && _sharedText!.isNotEmpty) {
        _inputController.text = _sharedText!;
        _sharedText = null;
      }
    });
  }

  Future<void> _initSpeech() async {
    try {
      _speechAvailable = await _speech.initialize();
      if (mounted) setState(() {});
    } catch (_) {}
  }

  @override
  void dispose() {
    _speech.stop();
    _inputController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  void _sendMessage() {
    final text = _inputController.text.trim();
    if (text.isEmpty) return;

    ref.read(chatProvider.notifier).sendMessage(text);
    _inputController.clear();
    _scrollToBottom();
  }

  void _toggleListening() async {
    if (_isListening) {
      await _speech.stop();
      setState(() => _isListening = false);
    } else {
      setState(() => _isListening = true);
      await _speech.listen(
        onResult: (result) {
          setState(() {
            _inputController.text = result.recognizedWords;
            _inputController.selection = TextSelection.fromPosition(
              TextPosition(offset: _inputController.text.length),
            );
          });
          if (result.finalResult) {
            setState(() => _isListening = false);
          }
        },
        listenOptions: stt.SpeechListenOptions(
          listenMode: stt.ListenMode.dictation,
        ),
      );
    }
  }

  void _scrollToBottom() {
    Future.delayed(const Duration(milliseconds: 100), () {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 200),
          curve: Curves.easeOut,
        );
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final state = ref.watch(chatProvider);

    // Auto-scroll when new content arrives
    ref.listen<ChatState>(chatProvider, (prev, next) {
      if (next.messages.length != (prev?.messages.length ?? 0) ||
          next.streamingContent != (prev?.streamingContent ?? '')) {
        _scrollToBottom();
      }
    });

    // Approval dialog listener
    ref.listen<ChatState>(chatProvider, (prev, next) {
      if (next.pendingApproval != null && prev?.pendingApproval == null) {
        _showApproval(next.pendingApproval!);
      }
    });

    // Model fallback snackbar listener
    ref.listen<ChatState>(chatProvider, (prev, next) {
      if (next.modelFallbackMessage != null &&
          prev?.modelFallbackMessage == null) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(next.modelFallbackMessage!),
            duration: const Duration(seconds: 4),
          ),
        );
        ref.read(chatProvider.notifier).clearModelFallback();
      }
    });

    return Scaffold(
      appBar: AppBar(
        title: const Text('Chat'),
        actions: const [
          Padding(
            padding: EdgeInsets.only(right: 12),
            child: ConnectionIndicator(),
          ),
        ],
      ),
      body: Column(
        children: [
          // Offline / reconnecting banner
          _OfflineBanner(),

          // Message list
          Expanded(
            child: state.messages.isEmpty &&
                    !state.isLoading &&
                    state.streamingContent.isEmpty
                ? _EmptyChat(theme: theme)
                : _buildMessageList(state, theme),
          ),

          // Input area
          _ChatInput(
            controller: _inputController,
            isLoading: state.isLoading,
            isListening: _isListening,
            speechAvailable: _speechAvailable,
            onSend: _sendMessage,
            onCancel: () => ref.read(chatProvider.notifier).cancelRequest(),
            onMicPressed: _toggleListening,
          ),
        ],
      ),
    );
  }

  Future<void> _showApproval(approval) async {
    final approved = await showApprovalDialog(context, approval);
    if (approved != null) {
      ref.read(chatProvider.notifier).sendApproval(approval.id, approved);
    }
  }

  Widget _buildMessageList(ChatState state, ThemeData theme) {
    return ListView.builder(
      controller: _scrollController,
      padding: const EdgeInsets.symmetric(vertical: 8),
      itemCount: state.messages.length + (state.isLoading ? 1 : 0),
      itemBuilder: (context, index) {
        // Streaming/active message at the bottom
        if (index == state.messages.length && state.isLoading) {
          return _buildStreamingBubble(state, theme);
        }

        return MessageBubble(message: state.messages[index]);
      },
    );
  }

  Widget _buildStreamingBubble(ChatState state, ThemeData theme) {
    final children = <Widget>[];

    // Thinking indicator
    if (state.thinkingContent.isNotEmpty) {
      children.add(
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              SizedBox(
                width: 14,
                height: 14,
                child: CircularProgressIndicator(
                  strokeWidth: 2,
                  color:
                      theme.colorScheme.onSurface.withValues(alpha: 0.4),
                ),
              ),
              const SizedBox(width: 8),
              Text(
                'Thinking...',
                style: theme.textTheme.labelSmall?.copyWith(
                  color:
                      theme.colorScheme.onSurface.withValues(alpha: 0.5),
                  fontStyle: FontStyle.italic,
                ),
              ),
            ],
          ),
        ),
      );
    }

    // Active tool calls
    if (state.activeToolCalls.isNotEmpty) {
      children.add(
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Wrap(
                spacing: 6,
                runSpacing: 4,
                children: state.activeToolCalls.map((call) {
                  return Chip(
                    avatar: call.isRunning
                        ? SizedBox(
                            width: 14,
                            height: 14,
                            child: CircularProgressIndicator(
                              strokeWidth: 2,
                              color: theme.colorScheme.primary,
                            ),
                          )
                        : Icon(
                            (call.success ?? true)
                                ? Icons.check_circle
                                : Icons.error,
                            size: 16,
                            color: (call.success ?? true)
                                ? theme.colorScheme.primary
                                : theme.colorScheme.error,
                          ),
                    label: Text(
                      call.tool,
                      style: theme.textTheme.labelSmall,
                    ),
                    visualDensity: VisualDensity.compact,
                    materialTapTargetSize:
                        MaterialTapTargetSize.shrinkWrap,
                  );
                }).toList(),
              ),
              // Instruction delta text during tool execution
              if (state.instructionDeltaContent.isNotEmpty)
                Padding(
                  padding: const EdgeInsets.only(top: 4, left: 4),
                  child: Text(
                    state.instructionDeltaContent,
                    maxLines: 3,
                    overflow: TextOverflow.ellipsis,
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: theme.colorScheme.onSurface
                          .withValues(alpha: 0.5),
                      fontStyle: FontStyle.italic,
                    ),
                  ),
                ),
            ],
          ),
        ),
      );
    }

    // Streaming content
    if (state.streamingContent.isNotEmpty) {
      children.add(
        MessageBubble(
          message: ChatMessage(
            id: 'streaming',
            chatId: '',
            role: 'assistant',
            content: state.streamingContent,
            timestamp: DateTime.now(),
          ),
          isStreaming: true,
        ),
      );
    } else if (state.thinkingContent.isEmpty &&
        state.activeToolCalls.isEmpty) {
      // Show typing indicator when waiting for first token
      children.add(
        MessageBubble(
          message: ChatMessage(
            id: 'streaming',
            chatId: '',
            role: 'assistant',
            content: '',
            timestamp: DateTime.now(),
          ),
          isStreaming: true,
        ),
      );
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: children,
    );
  }
}

class _EmptyChat extends StatelessWidget {
  const _EmptyChat({required this.theme});

  final ThemeData theme;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            Icons.chat_bubble_outline,
            size: 64,
            color: theme.colorScheme.onSurface.withValues(alpha: 0.3),
          ),
          const SizedBox(height: 16),
          Text(
            'Start a conversation',
            style: theme.textTheme.bodyLarge?.copyWith(
              color: theme.colorScheme.onSurface.withValues(alpha: 0.5),
            ),
          ),
        ],
      ),
    );
  }
}

class _ChatInput extends StatelessWidget {
  const _ChatInput({
    required this.controller,
    required this.isLoading,
    required this.isListening,
    required this.speechAvailable,
    required this.onSend,
    required this.onCancel,
    required this.onMicPressed,
  });

  final TextEditingController controller;
  final bool isLoading;
  final bool isListening;
  final bool speechAvailable;
  final VoidCallback onSend;
  final VoidCallback onCancel;
  final VoidCallback onMicPressed;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Container(
      padding: const EdgeInsets.fromLTRB(16, 8, 8, 8),
      decoration: BoxDecoration(
        border: Border(
          top: BorderSide(color: theme.colorScheme.outlineVariant),
        ),
      ),
      child: SafeArea(
        top: false,
        child: Row(
          children: [
            // Mic button
            if (speechAvailable && !isLoading)
              IconButton(
                onPressed: onMicPressed,
                icon: Icon(
                  isListening ? Icons.mic : Icons.mic_none,
                  color: isListening
                      ? theme.colorScheme.error
                      : theme.colorScheme.onSurface.withValues(alpha: 0.6),
                ),
              ),
            Expanded(
              child: TextField(
                controller: controller,
                decoration: InputDecoration(
                  hintText: isListening
                      ? 'Listening...'
                      : 'Type a message...',
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(24),
                  ),
                  contentPadding: const EdgeInsets.symmetric(
                    horizontal: 20,
                    vertical: 12,
                  ),
                ),
                minLines: 1,
                maxLines: 4,
                textInputAction: TextInputAction.send,
                enabled: !isLoading,
                onSubmitted: (_) => onSend(),
              ),
            ),
            const SizedBox(width: 8),
            isLoading
                ? IconButton.filled(
                    onPressed: onCancel,
                    icon: const Icon(Icons.stop),
                  )
                : IconButton.filled(
                    onPressed: onSend,
                    icon: const Icon(Icons.send),
                  ),
          ],
        ),
      ),
    );
  }
}

class _OfflineBanner extends ConsumerWidget {
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final isConnected = ref.watch(wsConnectionProvider);

    if (isConnected) return const SizedBox.shrink();

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      color: Colors.amber.shade700,
      child: Row(
        children: [
          SizedBox(
            width: 14,
            height: 14,
            child: CircularProgressIndicator(
              strokeWidth: 2,
              color: Colors.white.withValues(alpha: 0.9),
            ),
          ),
          const SizedBox(width: 10),
          Text(
            'Reconnecting... Cached messages shown',
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  color: Colors.white,
                  fontWeight: FontWeight.w500,
                ),
          ),
        ],
      ),
    );
  }
}
