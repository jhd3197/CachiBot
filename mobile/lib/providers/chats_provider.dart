import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/chat.dart';
import 'service_providers.dart';

class ChatsState {
  const ChatsState({
    this.chats = const [],
    this.isLoading = false,
    this.errorMessage,
    this.isOffline = false,
  });

  final List<Chat> chats;
  final bool isLoading;
  final String? errorMessage;
  final bool isOffline;

  ChatsState copyWith({
    List<Chat>? chats,
    bool? isLoading,
    String? errorMessage,
    bool clearError = false,
    bool? isOffline,
  }) {
    return ChatsState(
      chats: chats ?? this.chats,
      isLoading: isLoading ?? this.isLoading,
      errorMessage: clearError ? null : (errorMessage ?? this.errorMessage),
      isOffline: isOffline ?? this.isOffline,
    );
  }
}

class ChatsNotifier extends StateNotifier<ChatsState> {
  ChatsNotifier(this._ref) : super(const ChatsState());

  final Ref _ref;

  Future<void> loadChats(String botId) async {
    state = state.copyWith(isLoading: true, clearError: true);
    try {
      final botService = _ref.read(botServiceProvider);
      final chats = await botService.listChats(botId);
      // Sort by updatedAt descending
      chats.sort((a, b) => b.updatedAt.compareTo(a.updatedAt));
      state = state.copyWith(chats: chats, isLoading: false, isOffline: false);

      // Cache to local DB
      _cacheChats(botId, chats);
    } catch (e) {
      // Try offline fallback
      final cached = await _loadCachedChats(botId);
      if (cached != null && cached.isNotEmpty) {
        state = state.copyWith(
          chats: cached,
          isLoading: false,
          isOffline: true,
        );
      } else {
        state = state.copyWith(
          isLoading: false,
          errorMessage: 'Failed to load chats',
        );
      }
    }
  }

  Future<void> deleteChat(String botId, String chatId) async {
    try {
      final botService = _ref.read(botServiceProvider);
      await botService.deleteChat(botId, chatId);
      state = state.copyWith(
        chats: state.chats.where((c) => c.id != chatId).toList(),
      );

      // Remove from local cache
      _deleteCachedChat(chatId);
    } catch (e) {
      state = state.copyWith(errorMessage: 'Failed to delete chat');
    }
  }

  Future<void> archiveChat(String botId, String chatId) async {
    try {
      final botService = _ref.read(botServiceProvider);
      await botService.archiveChat(botId, chatId);
      state = state.copyWith(
        chats: state.chats.where((c) => c.id != chatId).toList(),
      );
    } catch (e) {
      state = state.copyWith(errorMessage: 'Failed to archive chat');
    }
  }

  Future<void> unarchiveChat(String botId, String chatId) async {
    try {
      final botService = _ref.read(botServiceProvider);
      await botService.unarchiveChat(botId, chatId);
      // Reload to get the unarchived chat in the list
      await loadChats(botId);
    } catch (e) {
      state = state.copyWith(errorMessage: 'Failed to unarchive chat');
    }
  }

  Future<void> clearMessages(String botId, String chatId) async {
    try {
      final botService = _ref.read(botServiceProvider);
      await botService.clearChatMessages(botId, chatId);
    } catch (e) {
      state = state.copyWith(errorMessage: 'Failed to clear messages');
    }
  }

  void clear() {
    state = const ChatsState();
  }

  // ---- Local cache helpers ----

  Future<void> _cacheChats(String botId, List<Chat> chats) async {
    try {
      final dao = await _ref.read(chatDaoProvider.future);
      await dao.upsertChats(botId, chats);
    } catch (_) {}
  }

  Future<List<Chat>?> _loadCachedChats(String botId) async {
    try {
      final dao = await _ref.read(chatDaoProvider.future);
      return dao.getCachedChats(botId);
    } catch (_) {
      return null;
    }
  }

  Future<void> _deleteCachedChat(String chatId) async {
    try {
      final dao = await _ref.read(chatDaoProvider.future);
      await dao.deleteCachedChat(chatId);
    } catch (_) {}
  }
}

final chatsProvider = StateNotifierProvider<ChatsNotifier, ChatsState>((ref) {
  return ChatsNotifier(ref);
});
