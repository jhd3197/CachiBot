import 'package:dio/dio.dart';

import '../../models/knowledge.dart';
import 'api_client.dart';

class KnowledgeService {
  KnowledgeService(this._client);

  final ApiClient _client;

  // ---- Notes ----

  Future<List<BotNote>> listNotes(
    String botId, {
    List<String>? tags,
    String? search,
    int? limit,
    int? offset,
  }) async {
    final params = <String, dynamic>{};
    if (tags != null && tags.isNotEmpty) params['tags'] = tags.join(',');
    if (search != null) params['search'] = search;
    if (limit != null) params['limit'] = limit;
    if (offset != null) params['offset'] = offset;

    final response = await _client.dio.get(
      '/api/bots/$botId/knowledge/notes',
      queryParameters: params,
    );
    final list = response.data as List<dynamic>;
    return list.map((e) => BotNote.fromJson(e as Map<String, dynamic>)).toList();
  }

  Future<BotNote> getNote(String botId, String noteId) async {
    final response = await _client.dio.get(
      '/api/bots/$botId/knowledge/notes/$noteId',
    );
    return BotNote.fromJson(response.data as Map<String, dynamic>);
  }

  Future<BotNote> createNote(
    String botId, {
    required String title,
    required String content,
    List<String> tags = const [],
  }) async {
    final response = await _client.dio.post(
      '/api/bots/$botId/knowledge/notes',
      data: {
        'title': title,
        'content': content,
        'tags': tags,
      },
    );
    return BotNote.fromJson(response.data as Map<String, dynamic>);
  }

  Future<BotNote> updateNote(
    String botId,
    String noteId, {
    String? title,
    String? content,
    List<String>? tags,
  }) async {
    final data = <String, dynamic>{};
    if (title != null) data['title'] = title;
    if (content != null) data['content'] = content;
    if (tags != null) data['tags'] = tags;

    final response = await _client.dio.put(
      '/api/bots/$botId/knowledge/notes/$noteId',
      data: data,
    );
    return BotNote.fromJson(response.data as Map<String, dynamic>);
  }

  Future<void> deleteNote(String botId, String noteId) async {
    await _client.dio.delete('/api/bots/$botId/knowledge/notes/$noteId');
  }

  Future<List<String>> getTags(String botId) async {
    final response = await _client.dio.get(
      '/api/bots/$botId/knowledge/notes/tags',
    );
    return (response.data as List<dynamic>).cast<String>();
  }

  // ---- Stats ----

  Future<KnowledgeStats> getStats(String botId) async {
    final response = await _client.dio.get(
      '/api/bots/$botId/knowledge/stats',
    );
    return KnowledgeStats.fromJson(response.data as Map<String, dynamic>);
  }

  // ---- Search ----

  Future<List<SearchResult>> search(
    String botId,
    String query, {
    bool includeNotes = true,
    bool includeDocs = true,
    int limit = 20,
  }) async {
    final response = await _client.dio.post(
      '/api/bots/$botId/knowledge/search',
      data: {
        'query': query,
        'include_notes': includeNotes,
        'include_documents': includeDocs,
        'limit': limit,
      },
    );
    final list = response.data as List<dynamic>;
    return list.map((e) => SearchResult.fromJson(e as Map<String, dynamic>)).toList();
  }

  // ---- Documents ----

  Future<List<KnowledgeDocument>> listDocuments(String botId) async {
    final response = await _client.dio.get('/api/bots/$botId/documents');
    final list = response.data as List<dynamic>;
    return list
        .map((e) => KnowledgeDocument.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  Future<Map<String, dynamic>> uploadDocument(
    String botId,
    String filePath,
    String fileName,
  ) async {
    final formData = FormData.fromMap({
      'file': await MultipartFile.fromFile(filePath, filename: fileName),
    });
    final response = await _client.dio.post(
      '/api/bots/$botId/documents',
      data: formData,
    );
    return response.data as Map<String, dynamic>;
  }

  Future<void> deleteDocument(String botId, String docId) async {
    await _client.dio.delete('/api/bots/$botId/documents/$docId');
  }
}
