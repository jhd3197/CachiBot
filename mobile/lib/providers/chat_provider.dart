import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/chat.dart';
import '../models/ws_message.dart';
import 'service_providers.dart';

class ChatState {
  const ChatState({
    this.activeBotId,
    this.activeChatId,
    this.messages = const [],
    this.isLoading = false,
    this.thinkingContent = '',
    this.activeToolCalls = const [],
    this.streamingContent = '',
    this.streamingMessageId,
    this.errorMessage,
  });

  final String? activeBotId;
  final String? activeChatId;
  final List<ChatMessage> messages;
  final bool isLoading;
  final String thinkingContent;
  final List<ToolCall> activeToolCalls;
  final String streamingContent;
  final String? streamingMessageId;
  final String? errorMessage;

  ChatState copyWith({
    String? activeBotId,
    String? activeChatId,
    List<ChatMessage>? messages,
    bool? isLoading,
    String? thinkingContent,
    List<ToolCall>? activeToolCalls,
    String? streamingContent,
    String? streamingMessageId,
    String? errorMessage,
    bool clearError = false,
    bool clearActiveChatId = false,
    bool clearStreamingMessageId = false,
  }) {
    return ChatState(
      activeBotId: activeBotId ?? this.activeBotId,
      activeChatId:
          clearActiveChatId ? null : (activeChatId ?? this.activeChatId),
      messages: messages ?? this.messages,
      isLoading: isLoading ?? this.isLoading,
      thinkingContent: thinkingContent ?? this.thinkingContent,
      activeToolCalls: activeToolCalls ?? this.activeToolCalls,
      streamingContent: streamingContent ?? this.streamingContent,
      streamingMessageId: clearStreamingMessageId
          ? null
          : (streamingMessageId ?? this.streamingMessageId),
      errorMessage: clearError ? null : (errorMessage ?? this.errorMessage),
    );
  }
}

class ChatNotifier extends StateNotifier<ChatState> {
  ChatNotifier(this._ref) : super(const ChatState());

  final Ref _ref;
  StreamSubscription<WSEvent>? _wsSubscription;

  /// Open a chat: connect WS, optionally load history.
  Future<void> openChat(String botId, [String? chatId]) async {
    state = ChatState(activeBotId: botId, activeChatId: chatId);

    // Connect WebSocket
    final ws = _ref.read(wsServiceProvider);
    if (!ws.isConnected) await ws.connect();

    // Subscribe to events
    _wsSubscription?.cancel();
    _wsSubscription = ws.events.listen(_handleEvent);

    // Load existing messages if resuming a chat
    if (chatId != null) {
      await loadMessages();
    }
  }

  Future<void> loadMessages() async {
    final botId = state.activeBotId;
    final chatId = state.activeChatId;
    if (botId == null || chatId == null) return;

    state = state.copyWith(isLoading: true);

    try {
      final botService = _ref.read(botServiceProvider);
      final messages = await botService.getChatMessages(botId, chatId);
      state = state.copyWith(messages: messages, isLoading: false);
    } catch (e) {
      state = state.copyWith(
        isLoading: false,
        errorMessage: 'Failed to load messages',
      );
    }
  }

  void sendMessage(String text) {
    if (text.trim().isEmpty) return;

    final botId = state.activeBotId;
    if (botId == null) return;

    // Add optimistic user message
    final userMsg = ChatMessage(
      id: 'local-${DateTime.now().millisecondsSinceEpoch}',
      chatId: state.activeChatId ?? '',
      role: 'user',
      content: text,
      timestamp: DateTime.now(),
    );

    state = state.copyWith(
      messages: [...state.messages, userMsg],
      isLoading: true,
      thinkingContent: '',
      streamingContent: '',
      activeToolCalls: [],
      clearError: true,
    );

    final ws = _ref.read(wsServiceProvider);
    ws.sendChat(
      text,
      botId: botId,
      chatId: state.activeChatId,
    );
  }

  void cancelRequest() {
    final ws = _ref.read(wsServiceProvider);
    ws.sendCancel();
    state = state.copyWith(isLoading: false);
  }

  void sendApproval(String id, bool approved) {
    final ws = _ref.read(wsServiceProvider);
    ws.sendApproval(id, approved);
  }

  void _handleEvent(WSEvent event) {
    switch (event.type) {
      case WSEvent.thinking:
        _onThinking(event.payload);
      case WSEvent.toolStart:
        _onToolStart(event.payload);
      case WSEvent.toolEnd:
        _onToolEnd(event.payload);
      case WSEvent.message:
        _onMessage(event.payload);
      case WSEvent.done:
        _onDone(event.payload);
      case WSEvent.error:
        _onError(event.payload);
    }
  }

  void _onThinking(Map<String, dynamic> payload) {
    final content = payload['content'] as String? ?? '';
    state = state.copyWith(
      thinkingContent: state.thinkingContent + content,
    );
  }

  void _onToolStart(Map<String, dynamic> payload) {
    final call = ToolCall(
      id: payload['id'] as String,
      tool: payload['tool'] as String,
      args: (payload['args'] as Map<String, dynamic>?) ?? {},
      startTime: DateTime.now(),
    );
    state = state.copyWith(
      activeToolCalls: [...state.activeToolCalls, call],
    );
  }

  void _onToolEnd(Map<String, dynamic> payload) {
    final id = payload['id'] as String;
    final updatedCalls = state.activeToolCalls.map((tc) {
      if (tc.id == id) {
        return tc.copyWith(
          result: payload['result'],
          success: payload['success'] as bool?,
          endTime: DateTime.now(),
        );
      }
      return tc;
    }).toList();

    state = state.copyWith(activeToolCalls: updatedCalls);
  }

  void _onMessage(Map<String, dynamic> payload) {
    final content = payload['content'] as String? ?? '';
    final messageId = payload['messageId'] as String?;
    final role = payload['role'] as String? ?? 'assistant';

    if (role == 'user') {
      // Server echo of user message — update chatId if we didn't have one
      final chatId = state.activeChatId;
      if (chatId == null && messageId != null) {
        // The server may have created a chat
      }
      return;
    }

    // Accumulate assistant content by messageId
    if (messageId != null && messageId == state.streamingMessageId) {
      state = state.copyWith(
        streamingContent: state.streamingContent + content,
      );
    } else {
      state = state.copyWith(
        streamingContent: content,
        streamingMessageId: messageId,
      );
    }
  }

  void _onDone(Map<String, dynamic> payload) {
    // Finalize the streamed message
    if (state.streamingContent.isNotEmpty || state.activeToolCalls.isNotEmpty) {
      final finalMsg = ChatMessage(
        id: state.streamingMessageId ??
            'msg-${DateTime.now().millisecondsSinceEpoch}',
        chatId: state.activeChatId ?? '',
        role: 'assistant',
        content: state.streamingContent,
        timestamp: DateTime.now(),
        toolCalls: List.of(state.activeToolCalls),
        thinking: state.thinkingContent.isNotEmpty
            ? state.thinkingContent
            : null,
      );

      // Update activeChatId if server provided replyToId
      final replyToId = payload['replyToId'] as String?;

      state = state.copyWith(
        messages: [...state.messages, finalMsg],
        isLoading: false,
        thinkingContent: '',
        streamingContent: '',
        activeToolCalls: [],
        clearStreamingMessageId: true,
        activeChatId: replyToId != null && state.activeChatId == null
            ? null // keep null; chatId comes from message events
            : state.activeChatId,
      );
    } else {
      state = state.copyWith(
        isLoading: false,
        thinkingContent: '',
        streamingContent: '',
        activeToolCalls: [],
        clearStreamingMessageId: true,
      );
    }
  }

  void _onError(Map<String, dynamic> payload) {
    final message = payload['message'] as String? ?? 'An error occurred';
    state = state.copyWith(
      isLoading: false,
      errorMessage: message,
    );
  }

  void clear() {
    _wsSubscription?.cancel();
    state = const ChatState();
  }

  @override
  void dispose() {
    _wsSubscription?.cancel();
    super.dispose();
  }
}

final chatProvider = StateNotifierProvider<ChatNotifier, ChatState>((ref) {
  return ChatNotifier(ref);
});
