// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'app_database.dart';

// ignore_for_file: type=lint
class $CachedChatsTable extends CachedChats
    with TableInfo<$CachedChatsTable, CachedChat> {
  @override
  final GeneratedDatabase attachedDatabase;
  final String? _alias;
  $CachedChatsTable(this.attachedDatabase, [this._alias]);
  static const VerificationMeta _idMeta = const VerificationMeta('id');
  @override
  late final GeneratedColumn<String> id = GeneratedColumn<String>(
    'id',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _botIdMeta = const VerificationMeta('botId');
  @override
  late final GeneratedColumn<String> botId = GeneratedColumn<String>(
    'bot_id',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _titleMeta = const VerificationMeta('title');
  @override
  late final GeneratedColumn<String> title = GeneratedColumn<String>(
    'title',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _platformMeta = const VerificationMeta(
    'platform',
  );
  @override
  late final GeneratedColumn<String> platform = GeneratedColumn<String>(
    'platform',
    aliasedName,
    true,
    type: DriftSqlType.string,
    requiredDuringInsert: false,
  );
  static const VerificationMeta _pinnedMeta = const VerificationMeta('pinned');
  @override
  late final GeneratedColumn<bool> pinned = GeneratedColumn<bool>(
    'pinned',
    aliasedName,
    false,
    type: DriftSqlType.bool,
    requiredDuringInsert: false,
    defaultConstraints: GeneratedColumn.constraintIsAlways(
      'CHECK ("pinned" IN (0, 1))',
    ),
    defaultValue: const Constant(false),
  );
  static const VerificationMeta _archivedMeta = const VerificationMeta(
    'archived',
  );
  @override
  late final GeneratedColumn<bool> archived = GeneratedColumn<bool>(
    'archived',
    aliasedName,
    false,
    type: DriftSqlType.bool,
    requiredDuringInsert: false,
    defaultConstraints: GeneratedColumn.constraintIsAlways(
      'CHECK ("archived" IN (0, 1))',
    ),
    defaultValue: const Constant(false),
  );
  static const VerificationMeta _createdAtMeta = const VerificationMeta(
    'createdAt',
  );
  @override
  late final GeneratedColumn<DateTime> createdAt = GeneratedColumn<DateTime>(
    'created_at',
    aliasedName,
    false,
    type: DriftSqlType.dateTime,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _updatedAtMeta = const VerificationMeta(
    'updatedAt',
  );
  @override
  late final GeneratedColumn<DateTime> updatedAt = GeneratedColumn<DateTime>(
    'updated_at',
    aliasedName,
    false,
    type: DriftSqlType.dateTime,
    requiredDuringInsert: true,
  );
  @override
  List<GeneratedColumn> get $columns => [
    id,
    botId,
    title,
    platform,
    pinned,
    archived,
    createdAt,
    updatedAt,
  ];
  @override
  String get aliasedName => _alias ?? actualTableName;
  @override
  String get actualTableName => $name;
  static const String $name = 'cached_chats';
  @override
  VerificationContext validateIntegrity(
    Insertable<CachedChat> instance, {
    bool isInserting = false,
  }) {
    final context = VerificationContext();
    final data = instance.toColumns(true);
    if (data.containsKey('id')) {
      context.handle(_idMeta, id.isAcceptableOrUnknown(data['id']!, _idMeta));
    } else if (isInserting) {
      context.missing(_idMeta);
    }
    if (data.containsKey('bot_id')) {
      context.handle(
        _botIdMeta,
        botId.isAcceptableOrUnknown(data['bot_id']!, _botIdMeta),
      );
    } else if (isInserting) {
      context.missing(_botIdMeta);
    }
    if (data.containsKey('title')) {
      context.handle(
        _titleMeta,
        title.isAcceptableOrUnknown(data['title']!, _titleMeta),
      );
    } else if (isInserting) {
      context.missing(_titleMeta);
    }
    if (data.containsKey('platform')) {
      context.handle(
        _platformMeta,
        platform.isAcceptableOrUnknown(data['platform']!, _platformMeta),
      );
    }
    if (data.containsKey('pinned')) {
      context.handle(
        _pinnedMeta,
        pinned.isAcceptableOrUnknown(data['pinned']!, _pinnedMeta),
      );
    }
    if (data.containsKey('archived')) {
      context.handle(
        _archivedMeta,
        archived.isAcceptableOrUnknown(data['archived']!, _archivedMeta),
      );
    }
    if (data.containsKey('created_at')) {
      context.handle(
        _createdAtMeta,
        createdAt.isAcceptableOrUnknown(data['created_at']!, _createdAtMeta),
      );
    } else if (isInserting) {
      context.missing(_createdAtMeta);
    }
    if (data.containsKey('updated_at')) {
      context.handle(
        _updatedAtMeta,
        updatedAt.isAcceptableOrUnknown(data['updated_at']!, _updatedAtMeta),
      );
    } else if (isInserting) {
      context.missing(_updatedAtMeta);
    }
    return context;
  }

  @override
  Set<GeneratedColumn> get $primaryKey => {id};
  @override
  CachedChat map(Map<String, dynamic> data, {String? tablePrefix}) {
    final effectivePrefix = tablePrefix != null ? '$tablePrefix.' : '';
    return CachedChat(
      id:
          attachedDatabase.typeMapping.read(
            DriftSqlType.string,
            data['${effectivePrefix}id'],
          )!,
      botId:
          attachedDatabase.typeMapping.read(
            DriftSqlType.string,
            data['${effectivePrefix}bot_id'],
          )!,
      title:
          attachedDatabase.typeMapping.read(
            DriftSqlType.string,
            data['${effectivePrefix}title'],
          )!,
      platform: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}platform'],
      ),
      pinned:
          attachedDatabase.typeMapping.read(
            DriftSqlType.bool,
            data['${effectivePrefix}pinned'],
          )!,
      archived:
          attachedDatabase.typeMapping.read(
            DriftSqlType.bool,
            data['${effectivePrefix}archived'],
          )!,
      createdAt:
          attachedDatabase.typeMapping.read(
            DriftSqlType.dateTime,
            data['${effectivePrefix}created_at'],
          )!,
      updatedAt:
          attachedDatabase.typeMapping.read(
            DriftSqlType.dateTime,
            data['${effectivePrefix}updated_at'],
          )!,
    );
  }

  @override
  $CachedChatsTable createAlias(String alias) {
    return $CachedChatsTable(attachedDatabase, alias);
  }
}

class CachedChat extends DataClass implements Insertable<CachedChat> {
  final String id;
  final String botId;
  final String title;
  final String? platform;
  final bool pinned;
  final bool archived;
  final DateTime createdAt;
  final DateTime updatedAt;
  const CachedChat({
    required this.id,
    required this.botId,
    required this.title,
    this.platform,
    required this.pinned,
    required this.archived,
    required this.createdAt,
    required this.updatedAt,
  });
  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    map['id'] = Variable<String>(id);
    map['bot_id'] = Variable<String>(botId);
    map['title'] = Variable<String>(title);
    if (!nullToAbsent || platform != null) {
      map['platform'] = Variable<String>(platform);
    }
    map['pinned'] = Variable<bool>(pinned);
    map['archived'] = Variable<bool>(archived);
    map['created_at'] = Variable<DateTime>(createdAt);
    map['updated_at'] = Variable<DateTime>(updatedAt);
    return map;
  }

  CachedChatsCompanion toCompanion(bool nullToAbsent) {
    return CachedChatsCompanion(
      id: Value(id),
      botId: Value(botId),
      title: Value(title),
      platform:
          platform == null && nullToAbsent
              ? const Value.absent()
              : Value(platform),
      pinned: Value(pinned),
      archived: Value(archived),
      createdAt: Value(createdAt),
      updatedAt: Value(updatedAt),
    );
  }

  factory CachedChat.fromJson(
    Map<String, dynamic> json, {
    ValueSerializer? serializer,
  }) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return CachedChat(
      id: serializer.fromJson<String>(json['id']),
      botId: serializer.fromJson<String>(json['botId']),
      title: serializer.fromJson<String>(json['title']),
      platform: serializer.fromJson<String?>(json['platform']),
      pinned: serializer.fromJson<bool>(json['pinned']),
      archived: serializer.fromJson<bool>(json['archived']),
      createdAt: serializer.fromJson<DateTime>(json['createdAt']),
      updatedAt: serializer.fromJson<DateTime>(json['updatedAt']),
    );
  }
  @override
  Map<String, dynamic> toJson({ValueSerializer? serializer}) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return <String, dynamic>{
      'id': serializer.toJson<String>(id),
      'botId': serializer.toJson<String>(botId),
      'title': serializer.toJson<String>(title),
      'platform': serializer.toJson<String?>(platform),
      'pinned': serializer.toJson<bool>(pinned),
      'archived': serializer.toJson<bool>(archived),
      'createdAt': serializer.toJson<DateTime>(createdAt),
      'updatedAt': serializer.toJson<DateTime>(updatedAt),
    };
  }

  CachedChat copyWith({
    String? id,
    String? botId,
    String? title,
    Value<String?> platform = const Value.absent(),
    bool? pinned,
    bool? archived,
    DateTime? createdAt,
    DateTime? updatedAt,
  }) => CachedChat(
    id: id ?? this.id,
    botId: botId ?? this.botId,
    title: title ?? this.title,
    platform: platform.present ? platform.value : this.platform,
    pinned: pinned ?? this.pinned,
    archived: archived ?? this.archived,
    createdAt: createdAt ?? this.createdAt,
    updatedAt: updatedAt ?? this.updatedAt,
  );
  CachedChat copyWithCompanion(CachedChatsCompanion data) {
    return CachedChat(
      id: data.id.present ? data.id.value : this.id,
      botId: data.botId.present ? data.botId.value : this.botId,
      title: data.title.present ? data.title.value : this.title,
      platform: data.platform.present ? data.platform.value : this.platform,
      pinned: data.pinned.present ? data.pinned.value : this.pinned,
      archived: data.archived.present ? data.archived.value : this.archived,
      createdAt: data.createdAt.present ? data.createdAt.value : this.createdAt,
      updatedAt: data.updatedAt.present ? data.updatedAt.value : this.updatedAt,
    );
  }

  @override
  String toString() {
    return (StringBuffer('CachedChat(')
          ..write('id: $id, ')
          ..write('botId: $botId, ')
          ..write('title: $title, ')
          ..write('platform: $platform, ')
          ..write('pinned: $pinned, ')
          ..write('archived: $archived, ')
          ..write('createdAt: $createdAt, ')
          ..write('updatedAt: $updatedAt')
          ..write(')'))
        .toString();
  }

  @override
  int get hashCode => Object.hash(
    id,
    botId,
    title,
    platform,
    pinned,
    archived,
    createdAt,
    updatedAt,
  );
  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      (other is CachedChat &&
          other.id == this.id &&
          other.botId == this.botId &&
          other.title == this.title &&
          other.platform == this.platform &&
          other.pinned == this.pinned &&
          other.archived == this.archived &&
          other.createdAt == this.createdAt &&
          other.updatedAt == this.updatedAt);
}

class CachedChatsCompanion extends UpdateCompanion<CachedChat> {
  final Value<String> id;
  final Value<String> botId;
  final Value<String> title;
  final Value<String?> platform;
  final Value<bool> pinned;
  final Value<bool> archived;
  final Value<DateTime> createdAt;
  final Value<DateTime> updatedAt;
  final Value<int> rowid;
  const CachedChatsCompanion({
    this.id = const Value.absent(),
    this.botId = const Value.absent(),
    this.title = const Value.absent(),
    this.platform = const Value.absent(),
    this.pinned = const Value.absent(),
    this.archived = const Value.absent(),
    this.createdAt = const Value.absent(),
    this.updatedAt = const Value.absent(),
    this.rowid = const Value.absent(),
  });
  CachedChatsCompanion.insert({
    required String id,
    required String botId,
    required String title,
    this.platform = const Value.absent(),
    this.pinned = const Value.absent(),
    this.archived = const Value.absent(),
    required DateTime createdAt,
    required DateTime updatedAt,
    this.rowid = const Value.absent(),
  }) : id = Value(id),
       botId = Value(botId),
       title = Value(title),
       createdAt = Value(createdAt),
       updatedAt = Value(updatedAt);
  static Insertable<CachedChat> custom({
    Expression<String>? id,
    Expression<String>? botId,
    Expression<String>? title,
    Expression<String>? platform,
    Expression<bool>? pinned,
    Expression<bool>? archived,
    Expression<DateTime>? createdAt,
    Expression<DateTime>? updatedAt,
    Expression<int>? rowid,
  }) {
    return RawValuesInsertable({
      if (id != null) 'id': id,
      if (botId != null) 'bot_id': botId,
      if (title != null) 'title': title,
      if (platform != null) 'platform': platform,
      if (pinned != null) 'pinned': pinned,
      if (archived != null) 'archived': archived,
      if (createdAt != null) 'created_at': createdAt,
      if (updatedAt != null) 'updated_at': updatedAt,
      if (rowid != null) 'rowid': rowid,
    });
  }

  CachedChatsCompanion copyWith({
    Value<String>? id,
    Value<String>? botId,
    Value<String>? title,
    Value<String?>? platform,
    Value<bool>? pinned,
    Value<bool>? archived,
    Value<DateTime>? createdAt,
    Value<DateTime>? updatedAt,
    Value<int>? rowid,
  }) {
    return CachedChatsCompanion(
      id: id ?? this.id,
      botId: botId ?? this.botId,
      title: title ?? this.title,
      platform: platform ?? this.platform,
      pinned: pinned ?? this.pinned,
      archived: archived ?? this.archived,
      createdAt: createdAt ?? this.createdAt,
      updatedAt: updatedAt ?? this.updatedAt,
      rowid: rowid ?? this.rowid,
    );
  }

  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    if (id.present) {
      map['id'] = Variable<String>(id.value);
    }
    if (botId.present) {
      map['bot_id'] = Variable<String>(botId.value);
    }
    if (title.present) {
      map['title'] = Variable<String>(title.value);
    }
    if (platform.present) {
      map['platform'] = Variable<String>(platform.value);
    }
    if (pinned.present) {
      map['pinned'] = Variable<bool>(pinned.value);
    }
    if (archived.present) {
      map['archived'] = Variable<bool>(archived.value);
    }
    if (createdAt.present) {
      map['created_at'] = Variable<DateTime>(createdAt.value);
    }
    if (updatedAt.present) {
      map['updated_at'] = Variable<DateTime>(updatedAt.value);
    }
    if (rowid.present) {
      map['rowid'] = Variable<int>(rowid.value);
    }
    return map;
  }

  @override
  String toString() {
    return (StringBuffer('CachedChatsCompanion(')
          ..write('id: $id, ')
          ..write('botId: $botId, ')
          ..write('title: $title, ')
          ..write('platform: $platform, ')
          ..write('pinned: $pinned, ')
          ..write('archived: $archived, ')
          ..write('createdAt: $createdAt, ')
          ..write('updatedAt: $updatedAt, ')
          ..write('rowid: $rowid')
          ..write(')'))
        .toString();
  }
}

class $CachedMessagesTable extends CachedMessages
    with TableInfo<$CachedMessagesTable, CachedMessage> {
  @override
  final GeneratedDatabase attachedDatabase;
  final String? _alias;
  $CachedMessagesTable(this.attachedDatabase, [this._alias]);
  static const VerificationMeta _idMeta = const VerificationMeta('id');
  @override
  late final GeneratedColumn<String> id = GeneratedColumn<String>(
    'id',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _chatIdMeta = const VerificationMeta('chatId');
  @override
  late final GeneratedColumn<String> chatId = GeneratedColumn<String>(
    'chat_id',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _botIdMeta = const VerificationMeta('botId');
  @override
  late final GeneratedColumn<String> botId = GeneratedColumn<String>(
    'bot_id',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _roleMeta = const VerificationMeta('role');
  @override
  late final GeneratedColumn<String> role = GeneratedColumn<String>(
    'role',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _contentMeta = const VerificationMeta(
    'content',
  );
  @override
  late final GeneratedColumn<String> content = GeneratedColumn<String>(
    'content',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _timestampMeta = const VerificationMeta(
    'timestamp',
  );
  @override
  late final GeneratedColumn<DateTime> timestamp = GeneratedColumn<DateTime>(
    'timestamp',
    aliasedName,
    false,
    type: DriftSqlType.dateTime,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _metadataMeta = const VerificationMeta(
    'metadata',
  );
  @override
  late final GeneratedColumn<String> metadata = GeneratedColumn<String>(
    'metadata',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: false,
    defaultValue: const Constant('{}'),
  );
  static const VerificationMeta _replyToIdMeta = const VerificationMeta(
    'replyToId',
  );
  @override
  late final GeneratedColumn<String> replyToId = GeneratedColumn<String>(
    'reply_to_id',
    aliasedName,
    true,
    type: DriftSqlType.string,
    requiredDuringInsert: false,
  );
  @override
  List<GeneratedColumn> get $columns => [
    id,
    chatId,
    botId,
    role,
    content,
    timestamp,
    metadata,
    replyToId,
  ];
  @override
  String get aliasedName => _alias ?? actualTableName;
  @override
  String get actualTableName => $name;
  static const String $name = 'cached_messages';
  @override
  VerificationContext validateIntegrity(
    Insertable<CachedMessage> instance, {
    bool isInserting = false,
  }) {
    final context = VerificationContext();
    final data = instance.toColumns(true);
    if (data.containsKey('id')) {
      context.handle(_idMeta, id.isAcceptableOrUnknown(data['id']!, _idMeta));
    } else if (isInserting) {
      context.missing(_idMeta);
    }
    if (data.containsKey('chat_id')) {
      context.handle(
        _chatIdMeta,
        chatId.isAcceptableOrUnknown(data['chat_id']!, _chatIdMeta),
      );
    } else if (isInserting) {
      context.missing(_chatIdMeta);
    }
    if (data.containsKey('bot_id')) {
      context.handle(
        _botIdMeta,
        botId.isAcceptableOrUnknown(data['bot_id']!, _botIdMeta),
      );
    } else if (isInserting) {
      context.missing(_botIdMeta);
    }
    if (data.containsKey('role')) {
      context.handle(
        _roleMeta,
        role.isAcceptableOrUnknown(data['role']!, _roleMeta),
      );
    } else if (isInserting) {
      context.missing(_roleMeta);
    }
    if (data.containsKey('content')) {
      context.handle(
        _contentMeta,
        content.isAcceptableOrUnknown(data['content']!, _contentMeta),
      );
    } else if (isInserting) {
      context.missing(_contentMeta);
    }
    if (data.containsKey('timestamp')) {
      context.handle(
        _timestampMeta,
        timestamp.isAcceptableOrUnknown(data['timestamp']!, _timestampMeta),
      );
    } else if (isInserting) {
      context.missing(_timestampMeta);
    }
    if (data.containsKey('metadata')) {
      context.handle(
        _metadataMeta,
        metadata.isAcceptableOrUnknown(data['metadata']!, _metadataMeta),
      );
    }
    if (data.containsKey('reply_to_id')) {
      context.handle(
        _replyToIdMeta,
        replyToId.isAcceptableOrUnknown(data['reply_to_id']!, _replyToIdMeta),
      );
    }
    return context;
  }

  @override
  Set<GeneratedColumn> get $primaryKey => {id};
  @override
  CachedMessage map(Map<String, dynamic> data, {String? tablePrefix}) {
    final effectivePrefix = tablePrefix != null ? '$tablePrefix.' : '';
    return CachedMessage(
      id:
          attachedDatabase.typeMapping.read(
            DriftSqlType.string,
            data['${effectivePrefix}id'],
          )!,
      chatId:
          attachedDatabase.typeMapping.read(
            DriftSqlType.string,
            data['${effectivePrefix}chat_id'],
          )!,
      botId:
          attachedDatabase.typeMapping.read(
            DriftSqlType.string,
            data['${effectivePrefix}bot_id'],
          )!,
      role:
          attachedDatabase.typeMapping.read(
            DriftSqlType.string,
            data['${effectivePrefix}role'],
          )!,
      content:
          attachedDatabase.typeMapping.read(
            DriftSqlType.string,
            data['${effectivePrefix}content'],
          )!,
      timestamp:
          attachedDatabase.typeMapping.read(
            DriftSqlType.dateTime,
            data['${effectivePrefix}timestamp'],
          )!,
      metadata:
          attachedDatabase.typeMapping.read(
            DriftSqlType.string,
            data['${effectivePrefix}metadata'],
          )!,
      replyToId: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}reply_to_id'],
      ),
    );
  }

  @override
  $CachedMessagesTable createAlias(String alias) {
    return $CachedMessagesTable(attachedDatabase, alias);
  }
}

class CachedMessage extends DataClass implements Insertable<CachedMessage> {
  final String id;
  final String chatId;
  final String botId;
  final String role;
  final String content;
  final DateTime timestamp;
  final String metadata;
  final String? replyToId;
  const CachedMessage({
    required this.id,
    required this.chatId,
    required this.botId,
    required this.role,
    required this.content,
    required this.timestamp,
    required this.metadata,
    this.replyToId,
  });
  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    map['id'] = Variable<String>(id);
    map['chat_id'] = Variable<String>(chatId);
    map['bot_id'] = Variable<String>(botId);
    map['role'] = Variable<String>(role);
    map['content'] = Variable<String>(content);
    map['timestamp'] = Variable<DateTime>(timestamp);
    map['metadata'] = Variable<String>(metadata);
    if (!nullToAbsent || replyToId != null) {
      map['reply_to_id'] = Variable<String>(replyToId);
    }
    return map;
  }

  CachedMessagesCompanion toCompanion(bool nullToAbsent) {
    return CachedMessagesCompanion(
      id: Value(id),
      chatId: Value(chatId),
      botId: Value(botId),
      role: Value(role),
      content: Value(content),
      timestamp: Value(timestamp),
      metadata: Value(metadata),
      replyToId:
          replyToId == null && nullToAbsent
              ? const Value.absent()
              : Value(replyToId),
    );
  }

  factory CachedMessage.fromJson(
    Map<String, dynamic> json, {
    ValueSerializer? serializer,
  }) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return CachedMessage(
      id: serializer.fromJson<String>(json['id']),
      chatId: serializer.fromJson<String>(json['chatId']),
      botId: serializer.fromJson<String>(json['botId']),
      role: serializer.fromJson<String>(json['role']),
      content: serializer.fromJson<String>(json['content']),
      timestamp: serializer.fromJson<DateTime>(json['timestamp']),
      metadata: serializer.fromJson<String>(json['metadata']),
      replyToId: serializer.fromJson<String?>(json['replyToId']),
    );
  }
  @override
  Map<String, dynamic> toJson({ValueSerializer? serializer}) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return <String, dynamic>{
      'id': serializer.toJson<String>(id),
      'chatId': serializer.toJson<String>(chatId),
      'botId': serializer.toJson<String>(botId),
      'role': serializer.toJson<String>(role),
      'content': serializer.toJson<String>(content),
      'timestamp': serializer.toJson<DateTime>(timestamp),
      'metadata': serializer.toJson<String>(metadata),
      'replyToId': serializer.toJson<String?>(replyToId),
    };
  }

  CachedMessage copyWith({
    String? id,
    String? chatId,
    String? botId,
    String? role,
    String? content,
    DateTime? timestamp,
    String? metadata,
    Value<String?> replyToId = const Value.absent(),
  }) => CachedMessage(
    id: id ?? this.id,
    chatId: chatId ?? this.chatId,
    botId: botId ?? this.botId,
    role: role ?? this.role,
    content: content ?? this.content,
    timestamp: timestamp ?? this.timestamp,
    metadata: metadata ?? this.metadata,
    replyToId: replyToId.present ? replyToId.value : this.replyToId,
  );
  CachedMessage copyWithCompanion(CachedMessagesCompanion data) {
    return CachedMessage(
      id: data.id.present ? data.id.value : this.id,
      chatId: data.chatId.present ? data.chatId.value : this.chatId,
      botId: data.botId.present ? data.botId.value : this.botId,
      role: data.role.present ? data.role.value : this.role,
      content: data.content.present ? data.content.value : this.content,
      timestamp: data.timestamp.present ? data.timestamp.value : this.timestamp,
      metadata: data.metadata.present ? data.metadata.value : this.metadata,
      replyToId: data.replyToId.present ? data.replyToId.value : this.replyToId,
    );
  }

  @override
  String toString() {
    return (StringBuffer('CachedMessage(')
          ..write('id: $id, ')
          ..write('chatId: $chatId, ')
          ..write('botId: $botId, ')
          ..write('role: $role, ')
          ..write('content: $content, ')
          ..write('timestamp: $timestamp, ')
          ..write('metadata: $metadata, ')
          ..write('replyToId: $replyToId')
          ..write(')'))
        .toString();
  }

  @override
  int get hashCode => Object.hash(
    id,
    chatId,
    botId,
    role,
    content,
    timestamp,
    metadata,
    replyToId,
  );
  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      (other is CachedMessage &&
          other.id == this.id &&
          other.chatId == this.chatId &&
          other.botId == this.botId &&
          other.role == this.role &&
          other.content == this.content &&
          other.timestamp == this.timestamp &&
          other.metadata == this.metadata &&
          other.replyToId == this.replyToId);
}

class CachedMessagesCompanion extends UpdateCompanion<CachedMessage> {
  final Value<String> id;
  final Value<String> chatId;
  final Value<String> botId;
  final Value<String> role;
  final Value<String> content;
  final Value<DateTime> timestamp;
  final Value<String> metadata;
  final Value<String?> replyToId;
  final Value<int> rowid;
  const CachedMessagesCompanion({
    this.id = const Value.absent(),
    this.chatId = const Value.absent(),
    this.botId = const Value.absent(),
    this.role = const Value.absent(),
    this.content = const Value.absent(),
    this.timestamp = const Value.absent(),
    this.metadata = const Value.absent(),
    this.replyToId = const Value.absent(),
    this.rowid = const Value.absent(),
  });
  CachedMessagesCompanion.insert({
    required String id,
    required String chatId,
    required String botId,
    required String role,
    required String content,
    required DateTime timestamp,
    this.metadata = const Value.absent(),
    this.replyToId = const Value.absent(),
    this.rowid = const Value.absent(),
  }) : id = Value(id),
       chatId = Value(chatId),
       botId = Value(botId),
       role = Value(role),
       content = Value(content),
       timestamp = Value(timestamp);
  static Insertable<CachedMessage> custom({
    Expression<String>? id,
    Expression<String>? chatId,
    Expression<String>? botId,
    Expression<String>? role,
    Expression<String>? content,
    Expression<DateTime>? timestamp,
    Expression<String>? metadata,
    Expression<String>? replyToId,
    Expression<int>? rowid,
  }) {
    return RawValuesInsertable({
      if (id != null) 'id': id,
      if (chatId != null) 'chat_id': chatId,
      if (botId != null) 'bot_id': botId,
      if (role != null) 'role': role,
      if (content != null) 'content': content,
      if (timestamp != null) 'timestamp': timestamp,
      if (metadata != null) 'metadata': metadata,
      if (replyToId != null) 'reply_to_id': replyToId,
      if (rowid != null) 'rowid': rowid,
    });
  }

  CachedMessagesCompanion copyWith({
    Value<String>? id,
    Value<String>? chatId,
    Value<String>? botId,
    Value<String>? role,
    Value<String>? content,
    Value<DateTime>? timestamp,
    Value<String>? metadata,
    Value<String?>? replyToId,
    Value<int>? rowid,
  }) {
    return CachedMessagesCompanion(
      id: id ?? this.id,
      chatId: chatId ?? this.chatId,
      botId: botId ?? this.botId,
      role: role ?? this.role,
      content: content ?? this.content,
      timestamp: timestamp ?? this.timestamp,
      metadata: metadata ?? this.metadata,
      replyToId: replyToId ?? this.replyToId,
      rowid: rowid ?? this.rowid,
    );
  }

  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    if (id.present) {
      map['id'] = Variable<String>(id.value);
    }
    if (chatId.present) {
      map['chat_id'] = Variable<String>(chatId.value);
    }
    if (botId.present) {
      map['bot_id'] = Variable<String>(botId.value);
    }
    if (role.present) {
      map['role'] = Variable<String>(role.value);
    }
    if (content.present) {
      map['content'] = Variable<String>(content.value);
    }
    if (timestamp.present) {
      map['timestamp'] = Variable<DateTime>(timestamp.value);
    }
    if (metadata.present) {
      map['metadata'] = Variable<String>(metadata.value);
    }
    if (replyToId.present) {
      map['reply_to_id'] = Variable<String>(replyToId.value);
    }
    if (rowid.present) {
      map['rowid'] = Variable<int>(rowid.value);
    }
    return map;
  }

  @override
  String toString() {
    return (StringBuffer('CachedMessagesCompanion(')
          ..write('id: $id, ')
          ..write('chatId: $chatId, ')
          ..write('botId: $botId, ')
          ..write('role: $role, ')
          ..write('content: $content, ')
          ..write('timestamp: $timestamp, ')
          ..write('metadata: $metadata, ')
          ..write('replyToId: $replyToId, ')
          ..write('rowid: $rowid')
          ..write(')'))
        .toString();
  }
}

class $PendingMessagesTable extends PendingMessages
    with TableInfo<$PendingMessagesTable, PendingMessage> {
  @override
  final GeneratedDatabase attachedDatabase;
  final String? _alias;
  $PendingMessagesTable(this.attachedDatabase, [this._alias]);
  static const VerificationMeta _idMeta = const VerificationMeta('id');
  @override
  late final GeneratedColumn<int> id = GeneratedColumn<int>(
    'id',
    aliasedName,
    false,
    hasAutoIncrement: true,
    type: DriftSqlType.int,
    requiredDuringInsert: false,
    defaultConstraints: GeneratedColumn.constraintIsAlways(
      'PRIMARY KEY AUTOINCREMENT',
    ),
  );
  static const VerificationMeta _botIdMeta = const VerificationMeta('botId');
  @override
  late final GeneratedColumn<String> botId = GeneratedColumn<String>(
    'bot_id',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _chatIdMeta = const VerificationMeta('chatId');
  @override
  late final GeneratedColumn<String> chatId = GeneratedColumn<String>(
    'chat_id',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _contentMeta = const VerificationMeta(
    'content',
  );
  @override
  late final GeneratedColumn<String> content = GeneratedColumn<String>(
    'content',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _createdAtMeta = const VerificationMeta(
    'createdAt',
  );
  @override
  late final GeneratedColumn<DateTime> createdAt = GeneratedColumn<DateTime>(
    'created_at',
    aliasedName,
    false,
    type: DriftSqlType.dateTime,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _sentMeta = const VerificationMeta('sent');
  @override
  late final GeneratedColumn<bool> sent = GeneratedColumn<bool>(
    'sent',
    aliasedName,
    false,
    type: DriftSqlType.bool,
    requiredDuringInsert: false,
    defaultConstraints: GeneratedColumn.constraintIsAlways(
      'CHECK ("sent" IN (0, 1))',
    ),
    defaultValue: const Constant(false),
  );
  @override
  List<GeneratedColumn> get $columns => [
    id,
    botId,
    chatId,
    content,
    createdAt,
    sent,
  ];
  @override
  String get aliasedName => _alias ?? actualTableName;
  @override
  String get actualTableName => $name;
  static const String $name = 'pending_messages';
  @override
  VerificationContext validateIntegrity(
    Insertable<PendingMessage> instance, {
    bool isInserting = false,
  }) {
    final context = VerificationContext();
    final data = instance.toColumns(true);
    if (data.containsKey('id')) {
      context.handle(_idMeta, id.isAcceptableOrUnknown(data['id']!, _idMeta));
    }
    if (data.containsKey('bot_id')) {
      context.handle(
        _botIdMeta,
        botId.isAcceptableOrUnknown(data['bot_id']!, _botIdMeta),
      );
    } else if (isInserting) {
      context.missing(_botIdMeta);
    }
    if (data.containsKey('chat_id')) {
      context.handle(
        _chatIdMeta,
        chatId.isAcceptableOrUnknown(data['chat_id']!, _chatIdMeta),
      );
    } else if (isInserting) {
      context.missing(_chatIdMeta);
    }
    if (data.containsKey('content')) {
      context.handle(
        _contentMeta,
        content.isAcceptableOrUnknown(data['content']!, _contentMeta),
      );
    } else if (isInserting) {
      context.missing(_contentMeta);
    }
    if (data.containsKey('created_at')) {
      context.handle(
        _createdAtMeta,
        createdAt.isAcceptableOrUnknown(data['created_at']!, _createdAtMeta),
      );
    } else if (isInserting) {
      context.missing(_createdAtMeta);
    }
    if (data.containsKey('sent')) {
      context.handle(
        _sentMeta,
        sent.isAcceptableOrUnknown(data['sent']!, _sentMeta),
      );
    }
    return context;
  }

  @override
  Set<GeneratedColumn> get $primaryKey => {id};
  @override
  PendingMessage map(Map<String, dynamic> data, {String? tablePrefix}) {
    final effectivePrefix = tablePrefix != null ? '$tablePrefix.' : '';
    return PendingMessage(
      id:
          attachedDatabase.typeMapping.read(
            DriftSqlType.int,
            data['${effectivePrefix}id'],
          )!,
      botId:
          attachedDatabase.typeMapping.read(
            DriftSqlType.string,
            data['${effectivePrefix}bot_id'],
          )!,
      chatId:
          attachedDatabase.typeMapping.read(
            DriftSqlType.string,
            data['${effectivePrefix}chat_id'],
          )!,
      content:
          attachedDatabase.typeMapping.read(
            DriftSqlType.string,
            data['${effectivePrefix}content'],
          )!,
      createdAt:
          attachedDatabase.typeMapping.read(
            DriftSqlType.dateTime,
            data['${effectivePrefix}created_at'],
          )!,
      sent:
          attachedDatabase.typeMapping.read(
            DriftSqlType.bool,
            data['${effectivePrefix}sent'],
          )!,
    );
  }

  @override
  $PendingMessagesTable createAlias(String alias) {
    return $PendingMessagesTable(attachedDatabase, alias);
  }
}

class PendingMessage extends DataClass implements Insertable<PendingMessage> {
  final int id;
  final String botId;
  final String chatId;
  final String content;
  final DateTime createdAt;
  final bool sent;
  const PendingMessage({
    required this.id,
    required this.botId,
    required this.chatId,
    required this.content,
    required this.createdAt,
    required this.sent,
  });
  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    map['id'] = Variable<int>(id);
    map['bot_id'] = Variable<String>(botId);
    map['chat_id'] = Variable<String>(chatId);
    map['content'] = Variable<String>(content);
    map['created_at'] = Variable<DateTime>(createdAt);
    map['sent'] = Variable<bool>(sent);
    return map;
  }

  PendingMessagesCompanion toCompanion(bool nullToAbsent) {
    return PendingMessagesCompanion(
      id: Value(id),
      botId: Value(botId),
      chatId: Value(chatId),
      content: Value(content),
      createdAt: Value(createdAt),
      sent: Value(sent),
    );
  }

  factory PendingMessage.fromJson(
    Map<String, dynamic> json, {
    ValueSerializer? serializer,
  }) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return PendingMessage(
      id: serializer.fromJson<int>(json['id']),
      botId: serializer.fromJson<String>(json['botId']),
      chatId: serializer.fromJson<String>(json['chatId']),
      content: serializer.fromJson<String>(json['content']),
      createdAt: serializer.fromJson<DateTime>(json['createdAt']),
      sent: serializer.fromJson<bool>(json['sent']),
    );
  }
  @override
  Map<String, dynamic> toJson({ValueSerializer? serializer}) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return <String, dynamic>{
      'id': serializer.toJson<int>(id),
      'botId': serializer.toJson<String>(botId),
      'chatId': serializer.toJson<String>(chatId),
      'content': serializer.toJson<String>(content),
      'createdAt': serializer.toJson<DateTime>(createdAt),
      'sent': serializer.toJson<bool>(sent),
    };
  }

  PendingMessage copyWith({
    int? id,
    String? botId,
    String? chatId,
    String? content,
    DateTime? createdAt,
    bool? sent,
  }) => PendingMessage(
    id: id ?? this.id,
    botId: botId ?? this.botId,
    chatId: chatId ?? this.chatId,
    content: content ?? this.content,
    createdAt: createdAt ?? this.createdAt,
    sent: sent ?? this.sent,
  );
  PendingMessage copyWithCompanion(PendingMessagesCompanion data) {
    return PendingMessage(
      id: data.id.present ? data.id.value : this.id,
      botId: data.botId.present ? data.botId.value : this.botId,
      chatId: data.chatId.present ? data.chatId.value : this.chatId,
      content: data.content.present ? data.content.value : this.content,
      createdAt: data.createdAt.present ? data.createdAt.value : this.createdAt,
      sent: data.sent.present ? data.sent.value : this.sent,
    );
  }

  @override
  String toString() {
    return (StringBuffer('PendingMessage(')
          ..write('id: $id, ')
          ..write('botId: $botId, ')
          ..write('chatId: $chatId, ')
          ..write('content: $content, ')
          ..write('createdAt: $createdAt, ')
          ..write('sent: $sent')
          ..write(')'))
        .toString();
  }

  @override
  int get hashCode => Object.hash(id, botId, chatId, content, createdAt, sent);
  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      (other is PendingMessage &&
          other.id == this.id &&
          other.botId == this.botId &&
          other.chatId == this.chatId &&
          other.content == this.content &&
          other.createdAt == this.createdAt &&
          other.sent == this.sent);
}

class PendingMessagesCompanion extends UpdateCompanion<PendingMessage> {
  final Value<int> id;
  final Value<String> botId;
  final Value<String> chatId;
  final Value<String> content;
  final Value<DateTime> createdAt;
  final Value<bool> sent;
  const PendingMessagesCompanion({
    this.id = const Value.absent(),
    this.botId = const Value.absent(),
    this.chatId = const Value.absent(),
    this.content = const Value.absent(),
    this.createdAt = const Value.absent(),
    this.sent = const Value.absent(),
  });
  PendingMessagesCompanion.insert({
    this.id = const Value.absent(),
    required String botId,
    required String chatId,
    required String content,
    required DateTime createdAt,
    this.sent = const Value.absent(),
  }) : botId = Value(botId),
       chatId = Value(chatId),
       content = Value(content),
       createdAt = Value(createdAt);
  static Insertable<PendingMessage> custom({
    Expression<int>? id,
    Expression<String>? botId,
    Expression<String>? chatId,
    Expression<String>? content,
    Expression<DateTime>? createdAt,
    Expression<bool>? sent,
  }) {
    return RawValuesInsertable({
      if (id != null) 'id': id,
      if (botId != null) 'bot_id': botId,
      if (chatId != null) 'chat_id': chatId,
      if (content != null) 'content': content,
      if (createdAt != null) 'created_at': createdAt,
      if (sent != null) 'sent': sent,
    });
  }

  PendingMessagesCompanion copyWith({
    Value<int>? id,
    Value<String>? botId,
    Value<String>? chatId,
    Value<String>? content,
    Value<DateTime>? createdAt,
    Value<bool>? sent,
  }) {
    return PendingMessagesCompanion(
      id: id ?? this.id,
      botId: botId ?? this.botId,
      chatId: chatId ?? this.chatId,
      content: content ?? this.content,
      createdAt: createdAt ?? this.createdAt,
      sent: sent ?? this.sent,
    );
  }

  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    if (id.present) {
      map['id'] = Variable<int>(id.value);
    }
    if (botId.present) {
      map['bot_id'] = Variable<String>(botId.value);
    }
    if (chatId.present) {
      map['chat_id'] = Variable<String>(chatId.value);
    }
    if (content.present) {
      map['content'] = Variable<String>(content.value);
    }
    if (createdAt.present) {
      map['created_at'] = Variable<DateTime>(createdAt.value);
    }
    if (sent.present) {
      map['sent'] = Variable<bool>(sent.value);
    }
    return map;
  }

  @override
  String toString() {
    return (StringBuffer('PendingMessagesCompanion(')
          ..write('id: $id, ')
          ..write('botId: $botId, ')
          ..write('chatId: $chatId, ')
          ..write('content: $content, ')
          ..write('createdAt: $createdAt, ')
          ..write('sent: $sent')
          ..write(')'))
        .toString();
  }
}

abstract class _$AppDatabase extends GeneratedDatabase {
  _$AppDatabase(QueryExecutor e) : super(e);
  $AppDatabaseManager get managers => $AppDatabaseManager(this);
  late final $CachedChatsTable cachedChats = $CachedChatsTable(this);
  late final $CachedMessagesTable cachedMessages = $CachedMessagesTable(this);
  late final $PendingMessagesTable pendingMessages = $PendingMessagesTable(
    this,
  );
  @override
  Iterable<TableInfo<Table, Object?>> get allTables =>
      allSchemaEntities.whereType<TableInfo<Table, Object?>>();
  @override
  List<DatabaseSchemaEntity> get allSchemaEntities => [
    cachedChats,
    cachedMessages,
    pendingMessages,
  ];
}

typedef $$CachedChatsTableCreateCompanionBuilder =
    CachedChatsCompanion Function({
      required String id,
      required String botId,
      required String title,
      Value<String?> platform,
      Value<bool> pinned,
      Value<bool> archived,
      required DateTime createdAt,
      required DateTime updatedAt,
      Value<int> rowid,
    });
typedef $$CachedChatsTableUpdateCompanionBuilder =
    CachedChatsCompanion Function({
      Value<String> id,
      Value<String> botId,
      Value<String> title,
      Value<String?> platform,
      Value<bool> pinned,
      Value<bool> archived,
      Value<DateTime> createdAt,
      Value<DateTime> updatedAt,
      Value<int> rowid,
    });

class $$CachedChatsTableFilterComposer
    extends Composer<_$AppDatabase, $CachedChatsTable> {
  $$CachedChatsTableFilterComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnFilters<String> get id => $composableBuilder(
    column: $table.id,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get botId => $composableBuilder(
    column: $table.botId,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get title => $composableBuilder(
    column: $table.title,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get platform => $composableBuilder(
    column: $table.platform,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<bool> get pinned => $composableBuilder(
    column: $table.pinned,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<bool> get archived => $composableBuilder(
    column: $table.archived,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<DateTime> get createdAt => $composableBuilder(
    column: $table.createdAt,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<DateTime> get updatedAt => $composableBuilder(
    column: $table.updatedAt,
    builder: (column) => ColumnFilters(column),
  );
}

class $$CachedChatsTableOrderingComposer
    extends Composer<_$AppDatabase, $CachedChatsTable> {
  $$CachedChatsTableOrderingComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnOrderings<String> get id => $composableBuilder(
    column: $table.id,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get botId => $composableBuilder(
    column: $table.botId,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get title => $composableBuilder(
    column: $table.title,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get platform => $composableBuilder(
    column: $table.platform,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<bool> get pinned => $composableBuilder(
    column: $table.pinned,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<bool> get archived => $composableBuilder(
    column: $table.archived,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<DateTime> get createdAt => $composableBuilder(
    column: $table.createdAt,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<DateTime> get updatedAt => $composableBuilder(
    column: $table.updatedAt,
    builder: (column) => ColumnOrderings(column),
  );
}

class $$CachedChatsTableAnnotationComposer
    extends Composer<_$AppDatabase, $CachedChatsTable> {
  $$CachedChatsTableAnnotationComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  GeneratedColumn<String> get id =>
      $composableBuilder(column: $table.id, builder: (column) => column);

  GeneratedColumn<String> get botId =>
      $composableBuilder(column: $table.botId, builder: (column) => column);

  GeneratedColumn<String> get title =>
      $composableBuilder(column: $table.title, builder: (column) => column);

  GeneratedColumn<String> get platform =>
      $composableBuilder(column: $table.platform, builder: (column) => column);

  GeneratedColumn<bool> get pinned =>
      $composableBuilder(column: $table.pinned, builder: (column) => column);

  GeneratedColumn<bool> get archived =>
      $composableBuilder(column: $table.archived, builder: (column) => column);

  GeneratedColumn<DateTime> get createdAt =>
      $composableBuilder(column: $table.createdAt, builder: (column) => column);

  GeneratedColumn<DateTime> get updatedAt =>
      $composableBuilder(column: $table.updatedAt, builder: (column) => column);
}

class $$CachedChatsTableTableManager
    extends
        RootTableManager<
          _$AppDatabase,
          $CachedChatsTable,
          CachedChat,
          $$CachedChatsTableFilterComposer,
          $$CachedChatsTableOrderingComposer,
          $$CachedChatsTableAnnotationComposer,
          $$CachedChatsTableCreateCompanionBuilder,
          $$CachedChatsTableUpdateCompanionBuilder,
          (
            CachedChat,
            BaseReferences<_$AppDatabase, $CachedChatsTable, CachedChat>,
          ),
          CachedChat,
          PrefetchHooks Function()
        > {
  $$CachedChatsTableTableManager(_$AppDatabase db, $CachedChatsTable table)
    : super(
        TableManagerState(
          db: db,
          table: table,
          createFilteringComposer:
              () => $$CachedChatsTableFilterComposer($db: db, $table: table),
          createOrderingComposer:
              () => $$CachedChatsTableOrderingComposer($db: db, $table: table),
          createComputedFieldComposer:
              () =>
                  $$CachedChatsTableAnnotationComposer($db: db, $table: table),
          updateCompanionCallback:
              ({
                Value<String> id = const Value.absent(),
                Value<String> botId = const Value.absent(),
                Value<String> title = const Value.absent(),
                Value<String?> platform = const Value.absent(),
                Value<bool> pinned = const Value.absent(),
                Value<bool> archived = const Value.absent(),
                Value<DateTime> createdAt = const Value.absent(),
                Value<DateTime> updatedAt = const Value.absent(),
                Value<int> rowid = const Value.absent(),
              }) => CachedChatsCompanion(
                id: id,
                botId: botId,
                title: title,
                platform: platform,
                pinned: pinned,
                archived: archived,
                createdAt: createdAt,
                updatedAt: updatedAt,
                rowid: rowid,
              ),
          createCompanionCallback:
              ({
                required String id,
                required String botId,
                required String title,
                Value<String?> platform = const Value.absent(),
                Value<bool> pinned = const Value.absent(),
                Value<bool> archived = const Value.absent(),
                required DateTime createdAt,
                required DateTime updatedAt,
                Value<int> rowid = const Value.absent(),
              }) => CachedChatsCompanion.insert(
                id: id,
                botId: botId,
                title: title,
                platform: platform,
                pinned: pinned,
                archived: archived,
                createdAt: createdAt,
                updatedAt: updatedAt,
                rowid: rowid,
              ),
          withReferenceMapper:
              (p0) =>
                  p0
                      .map(
                        (e) => (
                          e.readTable(table),
                          BaseReferences(db, table, e),
                        ),
                      )
                      .toList(),
          prefetchHooksCallback: null,
        ),
      );
}

typedef $$CachedChatsTableProcessedTableManager =
    ProcessedTableManager<
      _$AppDatabase,
      $CachedChatsTable,
      CachedChat,
      $$CachedChatsTableFilterComposer,
      $$CachedChatsTableOrderingComposer,
      $$CachedChatsTableAnnotationComposer,
      $$CachedChatsTableCreateCompanionBuilder,
      $$CachedChatsTableUpdateCompanionBuilder,
      (
        CachedChat,
        BaseReferences<_$AppDatabase, $CachedChatsTable, CachedChat>,
      ),
      CachedChat,
      PrefetchHooks Function()
    >;
typedef $$CachedMessagesTableCreateCompanionBuilder =
    CachedMessagesCompanion Function({
      required String id,
      required String chatId,
      required String botId,
      required String role,
      required String content,
      required DateTime timestamp,
      Value<String> metadata,
      Value<String?> replyToId,
      Value<int> rowid,
    });
typedef $$CachedMessagesTableUpdateCompanionBuilder =
    CachedMessagesCompanion Function({
      Value<String> id,
      Value<String> chatId,
      Value<String> botId,
      Value<String> role,
      Value<String> content,
      Value<DateTime> timestamp,
      Value<String> metadata,
      Value<String?> replyToId,
      Value<int> rowid,
    });

class $$CachedMessagesTableFilterComposer
    extends Composer<_$AppDatabase, $CachedMessagesTable> {
  $$CachedMessagesTableFilterComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnFilters<String> get id => $composableBuilder(
    column: $table.id,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get chatId => $composableBuilder(
    column: $table.chatId,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get botId => $composableBuilder(
    column: $table.botId,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get role => $composableBuilder(
    column: $table.role,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get content => $composableBuilder(
    column: $table.content,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<DateTime> get timestamp => $composableBuilder(
    column: $table.timestamp,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get metadata => $composableBuilder(
    column: $table.metadata,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get replyToId => $composableBuilder(
    column: $table.replyToId,
    builder: (column) => ColumnFilters(column),
  );
}

class $$CachedMessagesTableOrderingComposer
    extends Composer<_$AppDatabase, $CachedMessagesTable> {
  $$CachedMessagesTableOrderingComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnOrderings<String> get id => $composableBuilder(
    column: $table.id,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get chatId => $composableBuilder(
    column: $table.chatId,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get botId => $composableBuilder(
    column: $table.botId,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get role => $composableBuilder(
    column: $table.role,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get content => $composableBuilder(
    column: $table.content,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<DateTime> get timestamp => $composableBuilder(
    column: $table.timestamp,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get metadata => $composableBuilder(
    column: $table.metadata,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get replyToId => $composableBuilder(
    column: $table.replyToId,
    builder: (column) => ColumnOrderings(column),
  );
}

class $$CachedMessagesTableAnnotationComposer
    extends Composer<_$AppDatabase, $CachedMessagesTable> {
  $$CachedMessagesTableAnnotationComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  GeneratedColumn<String> get id =>
      $composableBuilder(column: $table.id, builder: (column) => column);

  GeneratedColumn<String> get chatId =>
      $composableBuilder(column: $table.chatId, builder: (column) => column);

  GeneratedColumn<String> get botId =>
      $composableBuilder(column: $table.botId, builder: (column) => column);

  GeneratedColumn<String> get role =>
      $composableBuilder(column: $table.role, builder: (column) => column);

  GeneratedColumn<String> get content =>
      $composableBuilder(column: $table.content, builder: (column) => column);

  GeneratedColumn<DateTime> get timestamp =>
      $composableBuilder(column: $table.timestamp, builder: (column) => column);

  GeneratedColumn<String> get metadata =>
      $composableBuilder(column: $table.metadata, builder: (column) => column);

  GeneratedColumn<String> get replyToId =>
      $composableBuilder(column: $table.replyToId, builder: (column) => column);
}

class $$CachedMessagesTableTableManager
    extends
        RootTableManager<
          _$AppDatabase,
          $CachedMessagesTable,
          CachedMessage,
          $$CachedMessagesTableFilterComposer,
          $$CachedMessagesTableOrderingComposer,
          $$CachedMessagesTableAnnotationComposer,
          $$CachedMessagesTableCreateCompanionBuilder,
          $$CachedMessagesTableUpdateCompanionBuilder,
          (
            CachedMessage,
            BaseReferences<_$AppDatabase, $CachedMessagesTable, CachedMessage>,
          ),
          CachedMessage,
          PrefetchHooks Function()
        > {
  $$CachedMessagesTableTableManager(
    _$AppDatabase db,
    $CachedMessagesTable table,
  ) : super(
        TableManagerState(
          db: db,
          table: table,
          createFilteringComposer:
              () => $$CachedMessagesTableFilterComposer($db: db, $table: table),
          createOrderingComposer:
              () =>
                  $$CachedMessagesTableOrderingComposer($db: db, $table: table),
          createComputedFieldComposer:
              () => $$CachedMessagesTableAnnotationComposer(
                $db: db,
                $table: table,
              ),
          updateCompanionCallback:
              ({
                Value<String> id = const Value.absent(),
                Value<String> chatId = const Value.absent(),
                Value<String> botId = const Value.absent(),
                Value<String> role = const Value.absent(),
                Value<String> content = const Value.absent(),
                Value<DateTime> timestamp = const Value.absent(),
                Value<String> metadata = const Value.absent(),
                Value<String?> replyToId = const Value.absent(),
                Value<int> rowid = const Value.absent(),
              }) => CachedMessagesCompanion(
                id: id,
                chatId: chatId,
                botId: botId,
                role: role,
                content: content,
                timestamp: timestamp,
                metadata: metadata,
                replyToId: replyToId,
                rowid: rowid,
              ),
          createCompanionCallback:
              ({
                required String id,
                required String chatId,
                required String botId,
                required String role,
                required String content,
                required DateTime timestamp,
                Value<String> metadata = const Value.absent(),
                Value<String?> replyToId = const Value.absent(),
                Value<int> rowid = const Value.absent(),
              }) => CachedMessagesCompanion.insert(
                id: id,
                chatId: chatId,
                botId: botId,
                role: role,
                content: content,
                timestamp: timestamp,
                metadata: metadata,
                replyToId: replyToId,
                rowid: rowid,
              ),
          withReferenceMapper:
              (p0) =>
                  p0
                      .map(
                        (e) => (
                          e.readTable(table),
                          BaseReferences(db, table, e),
                        ),
                      )
                      .toList(),
          prefetchHooksCallback: null,
        ),
      );
}

typedef $$CachedMessagesTableProcessedTableManager =
    ProcessedTableManager<
      _$AppDatabase,
      $CachedMessagesTable,
      CachedMessage,
      $$CachedMessagesTableFilterComposer,
      $$CachedMessagesTableOrderingComposer,
      $$CachedMessagesTableAnnotationComposer,
      $$CachedMessagesTableCreateCompanionBuilder,
      $$CachedMessagesTableUpdateCompanionBuilder,
      (
        CachedMessage,
        BaseReferences<_$AppDatabase, $CachedMessagesTable, CachedMessage>,
      ),
      CachedMessage,
      PrefetchHooks Function()
    >;
typedef $$PendingMessagesTableCreateCompanionBuilder =
    PendingMessagesCompanion Function({
      Value<int> id,
      required String botId,
      required String chatId,
      required String content,
      required DateTime createdAt,
      Value<bool> sent,
    });
typedef $$PendingMessagesTableUpdateCompanionBuilder =
    PendingMessagesCompanion Function({
      Value<int> id,
      Value<String> botId,
      Value<String> chatId,
      Value<String> content,
      Value<DateTime> createdAt,
      Value<bool> sent,
    });

class $$PendingMessagesTableFilterComposer
    extends Composer<_$AppDatabase, $PendingMessagesTable> {
  $$PendingMessagesTableFilterComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnFilters<int> get id => $composableBuilder(
    column: $table.id,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get botId => $composableBuilder(
    column: $table.botId,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get chatId => $composableBuilder(
    column: $table.chatId,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get content => $composableBuilder(
    column: $table.content,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<DateTime> get createdAt => $composableBuilder(
    column: $table.createdAt,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<bool> get sent => $composableBuilder(
    column: $table.sent,
    builder: (column) => ColumnFilters(column),
  );
}

class $$PendingMessagesTableOrderingComposer
    extends Composer<_$AppDatabase, $PendingMessagesTable> {
  $$PendingMessagesTableOrderingComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnOrderings<int> get id => $composableBuilder(
    column: $table.id,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get botId => $composableBuilder(
    column: $table.botId,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get chatId => $composableBuilder(
    column: $table.chatId,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get content => $composableBuilder(
    column: $table.content,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<DateTime> get createdAt => $composableBuilder(
    column: $table.createdAt,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<bool> get sent => $composableBuilder(
    column: $table.sent,
    builder: (column) => ColumnOrderings(column),
  );
}

class $$PendingMessagesTableAnnotationComposer
    extends Composer<_$AppDatabase, $PendingMessagesTable> {
  $$PendingMessagesTableAnnotationComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  GeneratedColumn<int> get id =>
      $composableBuilder(column: $table.id, builder: (column) => column);

  GeneratedColumn<String> get botId =>
      $composableBuilder(column: $table.botId, builder: (column) => column);

  GeneratedColumn<String> get chatId =>
      $composableBuilder(column: $table.chatId, builder: (column) => column);

  GeneratedColumn<String> get content =>
      $composableBuilder(column: $table.content, builder: (column) => column);

  GeneratedColumn<DateTime> get createdAt =>
      $composableBuilder(column: $table.createdAt, builder: (column) => column);

  GeneratedColumn<bool> get sent =>
      $composableBuilder(column: $table.sent, builder: (column) => column);
}

class $$PendingMessagesTableTableManager
    extends
        RootTableManager<
          _$AppDatabase,
          $PendingMessagesTable,
          PendingMessage,
          $$PendingMessagesTableFilterComposer,
          $$PendingMessagesTableOrderingComposer,
          $$PendingMessagesTableAnnotationComposer,
          $$PendingMessagesTableCreateCompanionBuilder,
          $$PendingMessagesTableUpdateCompanionBuilder,
          (
            PendingMessage,
            BaseReferences<
              _$AppDatabase,
              $PendingMessagesTable,
              PendingMessage
            >,
          ),
          PendingMessage,
          PrefetchHooks Function()
        > {
  $$PendingMessagesTableTableManager(
    _$AppDatabase db,
    $PendingMessagesTable table,
  ) : super(
        TableManagerState(
          db: db,
          table: table,
          createFilteringComposer:
              () =>
                  $$PendingMessagesTableFilterComposer($db: db, $table: table),
          createOrderingComposer:
              () => $$PendingMessagesTableOrderingComposer(
                $db: db,
                $table: table,
              ),
          createComputedFieldComposer:
              () => $$PendingMessagesTableAnnotationComposer(
                $db: db,
                $table: table,
              ),
          updateCompanionCallback:
              ({
                Value<int> id = const Value.absent(),
                Value<String> botId = const Value.absent(),
                Value<String> chatId = const Value.absent(),
                Value<String> content = const Value.absent(),
                Value<DateTime> createdAt = const Value.absent(),
                Value<bool> sent = const Value.absent(),
              }) => PendingMessagesCompanion(
                id: id,
                botId: botId,
                chatId: chatId,
                content: content,
                createdAt: createdAt,
                sent: sent,
              ),
          createCompanionCallback:
              ({
                Value<int> id = const Value.absent(),
                required String botId,
                required String chatId,
                required String content,
                required DateTime createdAt,
                Value<bool> sent = const Value.absent(),
              }) => PendingMessagesCompanion.insert(
                id: id,
                botId: botId,
                chatId: chatId,
                content: content,
                createdAt: createdAt,
                sent: sent,
              ),
          withReferenceMapper:
              (p0) =>
                  p0
                      .map(
                        (e) => (
                          e.readTable(table),
                          BaseReferences(db, table, e),
                        ),
                      )
                      .toList(),
          prefetchHooksCallback: null,
        ),
      );
}

typedef $$PendingMessagesTableProcessedTableManager =
    ProcessedTableManager<
      _$AppDatabase,
      $PendingMessagesTable,
      PendingMessage,
      $$PendingMessagesTableFilterComposer,
      $$PendingMessagesTableOrderingComposer,
      $$PendingMessagesTableAnnotationComposer,
      $$PendingMessagesTableCreateCompanionBuilder,
      $$PendingMessagesTableUpdateCompanionBuilder,
      (
        PendingMessage,
        BaseReferences<_$AppDatabase, $PendingMessagesTable, PendingMessage>,
      ),
      PendingMessage,
      PrefetchHooks Function()
    >;

class $AppDatabaseManager {
  final _$AppDatabase _db;
  $AppDatabaseManager(this._db);
  $$CachedChatsTableTableManager get cachedChats =>
      $$CachedChatsTableTableManager(_db, _db.cachedChats);
  $$CachedMessagesTableTableManager get cachedMessages =>
      $$CachedMessagesTableTableManager(_db, _db.cachedMessages);
  $$PendingMessagesTableTableManager get pendingMessages =>
      $$PendingMessagesTableTableManager(_db, _db.pendingMessages);
}
