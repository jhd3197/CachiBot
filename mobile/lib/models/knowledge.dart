class BotNote {
  const BotNote({
    required this.id,
    required this.botId,
    required this.title,
    required this.content,
    this.tags = const [],
    required this.source,
    required this.createdAt,
    required this.updatedAt,
  });

  final String id;
  final String botId;
  final String title;
  final String content;
  final List<String> tags;
  final String source;
  final DateTime createdAt;
  final DateTime updatedAt;

  factory BotNote.fromJson(Map<String, dynamic> json) {
    return BotNote(
      id: json['id'] as String,
      botId: json['botId'] as String? ?? json['bot_id'] as String,
      title: json['title'] as String,
      content: json['content'] as String,
      tags: (json['tags'] as List<dynamic>?)?.cast<String>() ?? [],
      source: json['source'] as String,
      createdAt: DateTime.parse(json['createdAt'] as String? ?? json['created_at'] as String),
      updatedAt: DateTime.parse(json['updatedAt'] as String? ?? json['updated_at'] as String),
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'botId': botId,
        'title': title,
        'content': content,
        'tags': tags,
        'source': source,
        'createdAt': createdAt.toIso8601String(),
        'updatedAt': updatedAt.toIso8601String(),
      };

  BotNote copyWith({
    String? title,
    String? content,
    List<String>? tags,
  }) {
    return BotNote(
      id: id,
      botId: botId,
      title: title ?? this.title,
      content: content ?? this.content,
      tags: tags ?? this.tags,
      source: source,
      createdAt: createdAt,
      updatedAt: updatedAt,
    );
  }
}

class KnowledgeDocument {
  const KnowledgeDocument({
    required this.id,
    required this.filename,
    required this.fileType,
    required this.fileSize,
    required this.chunkCount,
    required this.status,
    required this.uploadedAt,
    this.processedAt,
  });

  final String id;
  final String filename;
  final String fileType;
  final int fileSize;
  final int chunkCount;
  final String status;
  final DateTime uploadedAt;
  final DateTime? processedAt;

  factory KnowledgeDocument.fromJson(Map<String, dynamic> json) {
    return KnowledgeDocument(
      id: json['id'] as String,
      filename: json['filename'] as String,
      fileType: json['fileType'] as String? ?? json['file_type'] as String,
      fileSize: json['fileSize'] as int? ?? json['file_size'] as int,
      chunkCount: json['chunkCount'] as int? ?? json['chunk_count'] as int? ?? 0,
      status: json['status'] as String,
      uploadedAt: DateTime.parse(
        json['uploadedAt'] as String? ?? json['uploaded_at'] as String,
      ),
      processedAt: json['processedAt'] != null
          ? DateTime.parse(json['processedAt'] as String)
          : json['processed_at'] != null
              ? DateTime.parse(json['processed_at'] as String)
              : null,
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'filename': filename,
        'fileType': fileType,
        'fileSize': fileSize,
        'chunkCount': chunkCount,
        'status': status,
        'uploadedAt': uploadedAt.toIso8601String(),
        'processedAt': processedAt?.toIso8601String(),
      };

  bool get isReady => status == 'ready';
  bool get isProcessing => status == 'processing';
  bool get isFailed => status == 'failed';
}

class KnowledgeStats {
  const KnowledgeStats({
    required this.totalDocuments,
    required this.documentsReady,
    required this.documentsProcessing,
    required this.documentsFailed,
    required this.totalChunks,
    required this.totalNotes,
    this.hasInstructions = false,
  });

  final int totalDocuments;
  final int documentsReady;
  final int documentsProcessing;
  final int documentsFailed;
  final int totalChunks;
  final int totalNotes;
  final bool hasInstructions;

  factory KnowledgeStats.fromJson(Map<String, dynamic> json) {
    return KnowledgeStats(
      totalDocuments: json['totalDocuments'] as int? ?? json['total_documents'] as int? ?? 0,
      documentsReady: json['documentsReady'] as int? ?? json['documents_ready'] as int? ?? 0,
      documentsProcessing:
          json['documentsProcessing'] as int? ?? json['documents_processing'] as int? ?? 0,
      documentsFailed:
          json['documentsFailed'] as int? ?? json['documents_failed'] as int? ?? 0,
      totalChunks: json['totalChunks'] as int? ?? json['total_chunks'] as int? ?? 0,
      totalNotes: json['totalNotes'] as int? ?? json['total_notes'] as int? ?? 0,
      hasInstructions:
          json['hasInstructions'] as bool? ?? json['has_instructions'] as bool? ?? false,
    );
  }
}

class SearchResult {
  const SearchResult({
    required this.type,
    required this.id,
    required this.title,
    required this.content,
    this.score,
    this.source,
  });

  final String type;
  final String id;
  final String title;
  final String content;
  final double? score;
  final String? source;

  factory SearchResult.fromJson(Map<String, dynamic> json) {
    return SearchResult(
      type: json['type'] as String,
      id: json['id'] as String,
      title: json['title'] as String,
      content: json['content'] as String,
      score: (json['score'] as num?)?.toDouble(),
      source: json['source'] as String?,
    );
  }
}
