import 'dart:convert';

import 'package:drift/drift.dart';

import '../../models/chat.dart' as model;
import 'app_database.dart';

/// Data access object for cached chats and messages.
class ChatDao {
  ChatDao(this._db);

  final AppDatabase _db;

  // ---- Chats ----

  /// Insert or replace cached chats for a bot.
  Future<void> upsertChats(String botId, List<model.Chat> chats) async {
    await _db.batch((batch) {
      batch.insertAllOnConflictUpdate(
        _db.cachedChats,
        chats
            .map((c) => CachedChatsCompanion.insert(
                  id: c.id,
                  botId: c.botId,
                  title: c.title,
                  platform: Value(c.platform),
                  pinned: Value(c.pinned),
                  archived: Value(c.archived),
                  createdAt: c.createdAt,
                  updatedAt: c.updatedAt,
                ))
            .toList(),
      );
    });
  }

  /// Get all cached chats for a bot, sorted by updatedAt descending.
  Future<List<model.Chat>> getCachedChats(String botId) async {
    final query = _db.select(_db.cachedChats)
      ..where((t) => t.botId.equals(botId))
      ..orderBy([(t) => OrderingTerm.desc(t.updatedAt)]);

    final rows = await query.get();
    return rows.map(_rowToChat).toList();
  }

  /// Get all cached chats across all bots, sorted by updatedAt descending.
  Future<List<model.Chat>> getAllCachedChats() async {
    final query = _db.select(_db.cachedChats)
      ..orderBy([(t) => OrderingTerm.desc(t.updatedAt)]);

    final rows = await query.get();
    return rows.map(_rowToChat).toList();
  }

  /// Delete a cached chat and its messages.
  Future<void> deleteCachedChat(String chatId) async {
    await (_db.delete(_db.cachedMessages)
          ..where((t) => t.chatId.equals(chatId)))
        .go();
    await (_db.delete(_db.cachedChats)..where((t) => t.id.equals(chatId)))
        .go();
  }

  // ---- Messages ----

  /// Insert or replace cached messages for a chat.
  Future<void> upsertMessages(
    String botId,
    String chatId,
    List<model.ChatMessage> messages,
  ) async {
    await _db.batch((batch) {
      batch.insertAllOnConflictUpdate(
        _db.cachedMessages,
        messages
            .map((m) => CachedMessagesCompanion.insert(
                  id: m.id,
                  chatId: m.chatId,
                  botId: botId,
                  role: m.role,
                  content: m.content,
                  timestamp: m.timestamp,
                  metadata: Value(jsonEncode(m.metadata)),
                  replyToId: Value(m.replyToId),
                ))
            .toList(),
      );
    });
  }

  /// Get cached messages for a chat, sorted by timestamp ascending.
  Future<List<model.ChatMessage>> getCachedMessages(
    String botId,
    String chatId,
  ) async {
    final query = _db.select(_db.cachedMessages)
      ..where(
          (t) => t.botId.equals(botId) & t.chatId.equals(chatId))
      ..orderBy([(t) => OrderingTerm.asc(t.timestamp)]);

    final rows = await query.get();
    return rows.map(_rowToMessage).toList();
  }

  // ---- Pending messages (offline queue) ----

  /// Queue a message for sending when reconnected.
  Future<int> addPendingMessage(
    String botId,
    String chatId,
    String content,
  ) async {
    return _db.into(_db.pendingMessages).insert(
          PendingMessagesCompanion.insert(
            botId: botId,
            chatId: chatId,
            content: content,
            createdAt: DateTime.now(),
          ),
        );
  }

  /// Get all unsent pending messages.
  Future<List<PendingMessage>> getPendingMessages() async {
    final query = _db.select(_db.pendingMessages)
      ..where((t) => t.sent.equals(false))
      ..orderBy([(t) => OrderingTerm.asc(t.createdAt)]);
    return query.get();
  }

  /// Mark a pending message as sent.
  Future<void> markPendingSent(int id) async {
    await (_db.update(_db.pendingMessages)..where((t) => t.id.equals(id)))
        .write(const PendingMessagesCompanion(sent: Value(true)));
  }

  // ---- Cleanup ----

  /// Clear all cached data (for logout / clear cache).
  Future<void> clearAllData() async {
    await _db.delete(_db.pendingMessages).go();
    await _db.delete(_db.cachedMessages).go();
    await _db.delete(_db.cachedChats).go();
  }

  /// Count total cached messages (for cache size display).
  Future<int> countCachedMessages() async {
    final count = _db.cachedMessages.id.count();
    final query = _db.selectOnly(_db.cachedMessages)..addColumns([count]);
    final row = await query.getSingle();
    return row.read(count) ?? 0;
  }

  // ---- Row mappers ----

  model.Chat _rowToChat(CachedChat row) {
    return model.Chat(
      id: row.id,
      botId: row.botId,
      title: row.title,
      platform: row.platform,
      pinned: row.pinned,
      archived: row.archived,
      createdAt: row.createdAt,
      updatedAt: row.updatedAt,
    );
  }

  model.ChatMessage _rowToMessage(CachedMessage row) {
    Map<String, dynamic> metadata = {};
    try {
      metadata = jsonDecode(row.metadata) as Map<String, dynamic>;
    } catch (_) {}

    return model.ChatMessage(
      id: row.id,
      chatId: row.chatId,
      role: row.role,
      content: row.content,
      timestamp: row.timestamp,
      metadata: metadata,
      replyToId: row.replyToId,
    );
  }
}
