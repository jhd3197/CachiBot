import 'ws_message.dart';

class Chat {
  const Chat({
    required this.id,
    required this.botId,
    required this.title,
    this.platform,
    required this.pinned,
    required this.archived,
    required this.createdAt,
    required this.updatedAt,
  });

  final String id;
  final String botId;
  final String title;
  final String? platform;
  final bool pinned;
  final bool archived;
  final DateTime createdAt;
  final DateTime updatedAt;

  factory Chat.fromJson(Map<String, dynamic> json) {
    return Chat(
      id: json['id'] as String,
      botId: json['botId'] as String,
      title: json['title'] as String,
      platform: json['platform'] as String?,
      pinned: json['pinned'] as bool,
      archived: json['archived'] as bool,
      createdAt: DateTime.parse(json['createdAt'] as String),
      updatedAt: DateTime.parse(json['updatedAt'] as String),
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'botId': botId,
        'title': title,
        'platform': platform,
        'pinned': pinned,
        'archived': archived,
        'createdAt': createdAt.toIso8601String(),
        'updatedAt': updatedAt.toIso8601String(),
      };
}

class ChatMessage {
  const ChatMessage({
    required this.id,
    required this.chatId,
    required this.role,
    required this.content,
    required this.timestamp,
    this.metadata = const {},
    this.replyToId,
    this.toolCalls = const [],
    this.thinking,
  });

  final String id;
  final String chatId;
  final String role;
  final String content;
  final DateTime timestamp;
  final Map<String, dynamic> metadata;
  final String? replyToId;
  final List<ToolCall> toolCalls;
  final String? thinking;

  factory ChatMessage.fromJson(Map<String, dynamic> json) {
    return ChatMessage(
      id: json['id'] as String,
      chatId: json['chatId'] as String,
      role: json['role'] as String,
      content: json['content'] as String,
      timestamp: DateTime.parse(json['timestamp'] as String),
      metadata: (json['metadata'] as Map<String, dynamic>?) ?? {},
      replyToId: json['replyToId'] as String?,
    );
  }

  ChatMessage copyWith({
    String? content,
    List<ToolCall>? toolCalls,
    String? thinking,
  }) {
    return ChatMessage(
      id: id,
      chatId: chatId,
      role: role,
      content: content ?? this.content,
      timestamp: timestamp,
      metadata: metadata,
      replyToId: replyToId,
      toolCalls: toolCalls ?? this.toolCalls,
      thinking: thinking ?? this.thinking,
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'chatId': chatId,
        'role': role,
        'content': content,
        'timestamp': timestamp.toIso8601String(),
        'metadata': metadata,
        'replyToId': replyToId,
      };
}
