import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/knowledge.dart';
import 'service_providers.dart';

class KnowledgeState {
  const KnowledgeState({
    this.notes = const [],
    this.documents = const [],
    this.stats,
    this.searchResults = const [],
    this.searchQuery = '',
    this.isLoading = false,
    this.errorMessage,
    this.isOffline = false,
  });

  final List<BotNote> notes;
  final List<KnowledgeDocument> documents;
  final KnowledgeStats? stats;
  final List<SearchResult> searchResults;
  final String searchQuery;
  final bool isLoading;
  final String? errorMessage;
  final bool isOffline;

  KnowledgeState copyWith({
    List<BotNote>? notes,
    List<KnowledgeDocument>? documents,
    KnowledgeStats? stats,
    List<SearchResult>? searchResults,
    String? searchQuery,
    bool? isLoading,
    String? errorMessage,
    bool clearError = false,
    bool? isOffline,
  }) {
    return KnowledgeState(
      notes: notes ?? this.notes,
      documents: documents ?? this.documents,
      stats: stats ?? this.stats,
      searchResults: searchResults ?? this.searchResults,
      searchQuery: searchQuery ?? this.searchQuery,
      isLoading: isLoading ?? this.isLoading,
      errorMessage: clearError ? null : (errorMessage ?? this.errorMessage),
      isOffline: isOffline ?? this.isOffline,
    );
  }
}

class KnowledgeNotifier extends StateNotifier<KnowledgeState> {
  KnowledgeNotifier(this._ref) : super(const KnowledgeState());

  final Ref _ref;

  Future<void> loadNotes(String botId, {List<String>? tags, String? search}) async {
    state = state.copyWith(isLoading: true, clearError: true);
    try {
      final service = _ref.read(knowledgeServiceProvider);
      final notes = await service.listNotes(botId, tags: tags, search: search);
      state = state.copyWith(notes: notes, isLoading: false, isOffline: false);
    } on DioException catch (e) {
      state = state.copyWith(
        isLoading: false,
        errorMessage: _extractError(e),
      );
    } catch (e) {
      state = state.copyWith(isLoading: false, errorMessage: e.toString());
    }
  }

  Future<void> loadDocuments(String botId) async {
    try {
      final service = _ref.read(knowledgeServiceProvider);
      final docs = await service.listDocuments(botId);
      state = state.copyWith(documents: docs);
    } catch (_) {}
  }

  Future<void> loadStats(String botId) async {
    try {
      final service = _ref.read(knowledgeServiceProvider);
      final stats = await service.getStats(botId);
      state = state.copyWith(stats: stats);
    } catch (_) {}
  }

  Future<void> loadAll(String botId) async {
    state = state.copyWith(isLoading: true, clearError: true);
    try {
      final service = _ref.read(knowledgeServiceProvider);
      final results = await Future.wait([
        service.listNotes(botId),
        service.listDocuments(botId),
        service.getStats(botId),
      ]);
      state = KnowledgeState(
        notes: results[0] as List<BotNote>,
        documents: results[1] as List<KnowledgeDocument>,
        stats: results[2] as KnowledgeStats,
      );
    } on DioException catch (e) {
      state = state.copyWith(
        isLoading: false,
        errorMessage: _extractError(e),
      );
    } catch (e) {
      state = state.copyWith(isLoading: false, errorMessage: e.toString());
    }
  }

  Future<BotNote?> createNote(
    String botId, {
    required String title,
    required String content,
    List<String> tags = const [],
  }) async {
    try {
      final service = _ref.read(knowledgeServiceProvider);
      final note = await service.createNote(
        botId,
        title: title,
        content: content,
        tags: tags,
      );
      state = state.copyWith(notes: [note, ...state.notes]);
      return note;
    } on DioException catch (e) {
      state = state.copyWith(errorMessage: _extractError(e));
      return null;
    }
  }

  Future<BotNote?> updateNote(
    String botId,
    String noteId, {
    String? title,
    String? content,
    List<String>? tags,
  }) async {
    try {
      final service = _ref.read(knowledgeServiceProvider);
      final updated = await service.updateNote(
        botId,
        noteId,
        title: title,
        content: content,
        tags: tags,
      );
      state = state.copyWith(
        notes: state.notes.map((n) => n.id == noteId ? updated : n).toList(),
      );
      return updated;
    } on DioException catch (e) {
      state = state.copyWith(errorMessage: _extractError(e));
      return null;
    }
  }

  Future<void> deleteNote(String botId, String noteId) async {
    try {
      final service = _ref.read(knowledgeServiceProvider);
      await service.deleteNote(botId, noteId);
      state = state.copyWith(
        notes: state.notes.where((n) => n.id != noteId).toList(),
      );
    } on DioException catch (e) {
      state = state.copyWith(errorMessage: _extractError(e));
    }
  }

  Future<void> search(String botId, String query) async {
    if (query.isEmpty) {
      state = state.copyWith(searchResults: [], searchQuery: '');
      return;
    }
    state = state.copyWith(searchQuery: query, isLoading: true);
    try {
      final service = _ref.read(knowledgeServiceProvider);
      final results = await service.search(botId, query);
      state = state.copyWith(searchResults: results, isLoading: false);
    } on DioException catch (e) {
      state = state.copyWith(
        isLoading: false,
        errorMessage: _extractError(e),
      );
    }
  }

  Future<void> uploadDocument(String botId, String filePath, String fileName) async {
    try {
      final service = _ref.read(knowledgeServiceProvider);
      await service.uploadDocument(botId, filePath, fileName);
      await loadDocuments(botId);
      await loadStats(botId);
    } on DioException catch (e) {
      state = state.copyWith(errorMessage: _extractError(e));
    }
  }

  Future<void> deleteDocument(String botId, String docId) async {
    try {
      final service = _ref.read(knowledgeServiceProvider);
      await service.deleteDocument(botId, docId);
      state = state.copyWith(
        documents: state.documents.where((d) => d.id != docId).toList(),
      );
    } on DioException catch (e) {
      state = state.copyWith(errorMessage: _extractError(e));
    }
  }

  void clearError() {
    state = state.copyWith(clearError: true);
  }

  String _extractError(DioException e) {
    final data = e.response?.data;
    if (data is Map<String, dynamic> && data.containsKey('detail')) {
      final detail = data['detail'];
      if (detail is String) return detail;
      if (detail is Map) return detail['message']?.toString() ?? 'Request failed';
    }
    if (e.type == DioExceptionType.connectionTimeout ||
        e.type == DioExceptionType.connectionError) {
      return 'Cannot reach server';
    }
    return 'Request failed';
  }
}

final knowledgeProvider =
    StateNotifierProvider<KnowledgeNotifier, KnowledgeState>((ref) {
  return KnowledgeNotifier(ref);
});
