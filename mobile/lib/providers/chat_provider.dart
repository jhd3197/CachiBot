import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/chat.dart';
import '../models/usage.dart';
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
    this.usageInfo,
    this.pendingApproval,
    this.instructionDeltaContent = '',
    this.modelFallbackMessage,
    this.isOffline = false,
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
  final UsageInfo? usageInfo;
  final ApprovalRequest? pendingApproval;
  final String instructionDeltaContent;
  final String? modelFallbackMessage;
  final bool isOffline;

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
    UsageInfo? usageInfo,
    ApprovalRequest? pendingApproval,
    String? instructionDeltaContent,
    String? modelFallbackMessage,
    bool clearError = false,
    bool clearActiveChatId = false,
    bool clearStreamingMessageId = false,
    bool clearUsageInfo = false,
    bool clearPendingApproval = false,
    bool clearModelFallback = false,
    bool? isOffline,
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
      usageInfo: clearUsageInfo ? null : (usageInfo ?? this.usageInfo),
      pendingApproval: clearPendingApproval
          ? null
          : (pendingApproval ?? this.pendingApproval),
      instructionDeltaContent:
          instructionDeltaContent ?? this.instructionDeltaContent,
      modelFallbackMessage: clearModelFallback
          ? null
          : (modelFallbackMessage ?? this.modelFallbackMessage),
      isOffline: isOffline ?? this.isOffline,
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
      state = state.copyWith(messages: messages, isLoading: false, isOffline: false);

      // Cache to local DB
      _cacheMessages(botId, chatId, messages);
    } catch (e) {
      // Try offline fallback
      final cached = await _loadCachedMessages(botId, chatId);
      if (cached != null && cached.isNotEmpty) {
        state = state.copyWith(
          messages: cached,
          isLoading: false,
          isOffline: true,
        );
      } else {
        state = state.copyWith(
          isLoading: false,
          errorMessage: 'Failed to load messages',
        );
      }
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

    // Check if WS is connected
    final ws = _ref.read(wsServiceProvider);
    if (!ws.isConnected) {
      // Queue for later sending
      final pendingMsg = ChatMessage(
        id: 'pending-${DateTime.now().millisecondsSinceEpoch}',
        chatId: state.activeChatId ?? '',
        role: 'user',
        content: text,
        timestamp: DateTime.now(),
        metadata: const {'pending': true},
      );
      state = state.copyWith(
        messages: [...state.messages, pendingMsg],
        clearError: true,
      );
      _queuePendingMessage(botId, state.activeChatId ?? '', text);
      return;
    }

    state = state.copyWith(
      messages: [...state.messages, userMsg],
      isLoading: true,
      thinkingContent: '',
      streamingContent: '',
      activeToolCalls: [],
      instructionDeltaContent: '',
      clearError: true,
      clearUsageInfo: true,
      clearPendingApproval: true,
      clearModelFallback: true,
    );

    ws.sendChat(
      text,
      botId: botId,
      chatId: state.activeChatId,
    );
  }

  /// Flush pending messages after reconnection.
  Future<void> flushPendingQueue() async {
    try {
      final dao = await _ref.read(chatDaoProvider.future);
      final pending = await dao.getPendingMessages();
      if (pending.isEmpty) return;

      final ws = _ref.read(wsServiceProvider);
      if (!ws.isConnected) return;

      for (final msg in pending) {
        ws.sendChat(
          msg.content,
          botId: msg.botId,
          chatId: msg.chatId,
        );
        await dao.markPendingSent(msg.id);
      }

      // Remove pending indicators from displayed messages
      final updated = state.messages.map((m) {
        if (m.metadata.containsKey('pending')) {
          return ChatMessage(
            id: m.id,
            chatId: m.chatId,
            role: m.role,
            content: m.content,
            timestamp: m.timestamp,
          );
        }
        return m;
      }).toList();
      state = state.copyWith(messages: updated);
    } catch (_) {}
  }

  void cancelRequest() {
    final ws = _ref.read(wsServiceProvider);
    ws.sendCancel();
    state = state.copyWith(isLoading: false);
  }

  void sendApproval(String id, bool approved) {
    final ws = _ref.read(wsServiceProvider);
    ws.sendApproval(id, approved);
    state = state.copyWith(clearPendingApproval: true);
  }

  /// Clear the model fallback message after it has been shown.
  void clearModelFallback() {
    state = state.copyWith(clearModelFallback: true);
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
      case WSEvent.instructionDelta:
        _onInstructionDelta(event.payload);
      case WSEvent.usage:
        _onUsage(event.payload);
      case WSEvent.approvalNeeded:
        _onApprovalNeeded(event.payload);
      case WSEvent.modelFallback:
        _onModelFallback(event.payload);
      case WSEvent.reconnected:
        flushPendingQueue();
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

    // Clear instruction delta on tool end
    state = state.copyWith(
      activeToolCalls: updatedCalls,
      instructionDeltaContent: '',
    );
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
      final metadata = <String, dynamic>{};
      if (state.usageInfo != null) {
        metadata['usage'] = state.usageInfo!.toJson();
      }

      final finalMsg = ChatMessage(
        id: state.streamingMessageId ??
            'msg-${DateTime.now().millisecondsSinceEpoch}',
        chatId: state.activeChatId ?? '',
        role: 'assistant',
        content: state.streamingContent,
        timestamp: DateTime.now(),
        metadata: metadata,
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
        instructionDeltaContent: '',
        clearStreamingMessageId: true,
        clearPendingApproval: true,
        activeChatId: replyToId != null && state.activeChatId == null
            ? null // keep null; chatId comes from message events
            : state.activeChatId,
      );

      // Cache the finalized message to local DB
      _cacheMessage(finalMsg);
    } else {
      state = state.copyWith(
        isLoading: false,
        thinkingContent: '',
        streamingContent: '',
        activeToolCalls: [],
        instructionDeltaContent: '',
        clearStreamingMessageId: true,
        clearPendingApproval: true,
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

  void _onInstructionDelta(Map<String, dynamic> payload) {
    final text = payload['text'] as String? ?? '';
    state = state.copyWith(
      instructionDeltaContent: state.instructionDeltaContent + text,
    );
  }

  void _onUsage(Map<String, dynamic> payload) {
    final usage = UsageInfo.fromJson(payload);
    state = state.copyWith(usageInfo: usage);
  }

  void _onApprovalNeeded(Map<String, dynamic> payload) {
    final request = ApprovalRequest.fromPayload(payload);
    state = state.copyWith(pendingApproval: request);
  }

  void _onModelFallback(Map<String, dynamic> payload) {
    final oldModel = payload['oldModel'] as String? ?? '';
    final newModel = payload['newModel'] as String? ?? '';
    final reason = payload['reason'] as String? ?? '';
    final message = 'Model switched: $oldModel → $newModel'
        '${reason.isNotEmpty ? ' ($reason)' : ''}';
    state = state.copyWith(modelFallbackMessage: message);
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

  // ---- Local cache helpers ----

  Future<void> _cacheMessages(
    String botId,
    String chatId,
    List<ChatMessage> messages,
  ) async {
    try {
      final dao = await _ref.read(chatDaoProvider.future);
      await dao.upsertMessages(botId, chatId, messages);
    } catch (_) {}
  }

  Future<void> _cacheMessage(ChatMessage message) async {
    final botId = state.activeBotId;
    final chatId = state.activeChatId;
    if (botId == null || chatId == null) return;

    try {
      final dao = await _ref.read(chatDaoProvider.future);
      await dao.upsertMessages(botId, chatId, [message]);
    } catch (_) {}
  }

  Future<List<ChatMessage>?> _loadCachedMessages(
    String botId,
    String chatId,
  ) async {
    try {
      final dao = await _ref.read(chatDaoProvider.future);
      return dao.getCachedMessages(botId, chatId);
    } catch (_) {
      return null;
    }
  }

  Future<void> _queuePendingMessage(
    String botId,
    String chatId,
    String content,
  ) async {
    try {
      final dao = await _ref.read(chatDaoProvider.future);
      await dao.addPendingMessage(botId, chatId, content);
    } catch (_) {}
  }
}

final chatProvider = StateNotifierProvider<ChatNotifier, ChatState>((ref) {
  return ChatNotifier(ref);
});
