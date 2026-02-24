import 'dart:io';

import 'package:drift/drift.dart';
import 'package:drift/native.dart';
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';

part 'app_database.g.dart';

/// Cached chats table — mirrors the Chat model from the server.
class CachedChats extends Table {
  TextColumn get id => text()();
  TextColumn get botId => text()();
  TextColumn get title => text()();
  TextColumn get platform => text().nullable()();
  BoolColumn get pinned => boolean().withDefault(const Constant(false))();
  BoolColumn get archived => boolean().withDefault(const Constant(false))();
  DateTimeColumn get createdAt => dateTime()();
  DateTimeColumn get updatedAt => dateTime()();

  @override
  Set<Column> get primaryKey => {id};
}

/// Cached messages table — mirrors the ChatMessage model from the server.
class CachedMessages extends Table {
  TextColumn get id => text()();
  TextColumn get chatId => text()();
  TextColumn get botId => text()();
  TextColumn get role => text()();
  TextColumn get content => text()();
  DateTimeColumn get timestamp => dateTime()();
  TextColumn get metadata => text().withDefault(const Constant('{}'))();
  TextColumn get replyToId => text().nullable()();

  @override
  Set<Column> get primaryKey => {id};
}

/// Pending messages table — offline queue for messages sent while disconnected.
class PendingMessages extends Table {
  IntColumn get id => integer().autoIncrement()();
  TextColumn get botId => text()();
  TextColumn get chatId => text()();
  TextColumn get content => text()();
  DateTimeColumn get createdAt => dateTime()();
  BoolColumn get sent => boolean().withDefault(const Constant(false))();
}

@DriftDatabase(tables: [CachedChats, CachedMessages, PendingMessages])
class AppDatabase extends _$AppDatabase {
  AppDatabase._internal(super.e);

  static AppDatabase? _instance;

  /// Singleton factory — opens database at application documents directory.
  static Future<AppDatabase> open() async {
    if (_instance != null) return _instance!;

    final dir = await getApplicationDocumentsDirectory();
    final file = File(p.join(dir.path, 'cachibot.db'));
    _instance = AppDatabase._internal(NativeDatabase.createInBackground(file));
    return _instance!;
  }

  /// Close and reset the singleton (used on logout / forget server).
  static Future<void> reset() async {
    await _instance?.close();
    _instance = null;
  }

  @override
  int get schemaVersion => 1;
}
