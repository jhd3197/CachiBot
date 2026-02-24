import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/work.dart';
import 'service_providers.dart';

enum WorkFilter { all, active, completed, failed }

class WorkState {
  const WorkState({
    this.workItems = const [],
    this.isLoading = false,
    this.errorMessage,
    this.isOffline = false,
    this.filter = WorkFilter.all,
  });

  final List<BotWork> workItems;
  final bool isLoading;
  final String? errorMessage;
  final bool isOffline;
  final WorkFilter filter;

  WorkState copyWith({
    List<BotWork>? workItems,
    bool? isLoading,
    String? errorMessage,
    bool clearError = false,
    bool? isOffline,
    WorkFilter? filter,
  }) {
    return WorkState(
      workItems: workItems ?? this.workItems,
      isLoading: isLoading ?? this.isLoading,
      errorMessage: clearError ? null : (errorMessage ?? this.errorMessage),
      isOffline: isOffline ?? this.isOffline,
      filter: filter ?? this.filter,
    );
  }

  List<BotWork> get filteredItems {
    switch (filter) {
      case WorkFilter.all:
        return workItems;
      case WorkFilter.active:
        return workItems.where((w) => w.isActive).toList();
      case WorkFilter.completed:
        return workItems.where((w) => w.isDone).toList();
      case WorkFilter.failed:
        return workItems.where((w) => w.hasFailed).toList();
    }
  }
}

class WorkNotifier extends StateNotifier<WorkState> {
  WorkNotifier(this._ref) : super(const WorkState());

  final Ref _ref;

  Future<void> loadWork(String botId) async {
    state = state.copyWith(isLoading: true, clearError: true);
    try {
      final service = _ref.read(workServiceProvider);
      final items = await service.listWork(botId);
      state = state.copyWith(workItems: items, isLoading: false, isOffline: false);
    } on DioException catch (e) {
      state = state.copyWith(
        isLoading: false,
        errorMessage: _extractError(e),
      );
    } catch (e) {
      state = state.copyWith(isLoading: false, errorMessage: e.toString());
    }
  }

  Future<BotWork?> createWork(
    String botId, {
    required String title,
    String? description,
    String? goal,
    String? priority,
    List<String>? tags,
  }) async {
    try {
      final service = _ref.read(workServiceProvider);
      final work = await service.createWork(
        botId,
        title: title,
        description: description,
        goal: goal,
        priority: priority,
        tags: tags,
      );
      state = state.copyWith(workItems: [work, ...state.workItems]);
      return work;
    } on DioException catch (e) {
      state = state.copyWith(errorMessage: _extractError(e));
      return null;
    }
  }

  Future<void> deleteWork(String botId, String workId) async {
    try {
      final service = _ref.read(workServiceProvider);
      await service.deleteWork(botId, workId);
      state = state.copyWith(
        workItems: state.workItems.where((w) => w.id != workId).toList(),
      );
    } on DioException catch (e) {
      state = state.copyWith(errorMessage: _extractError(e));
    }
  }

  Future<void> startWork(String botId, String workId) async {
    try {
      final service = _ref.read(workServiceProvider);
      final updated = await service.startWork(botId, workId);
      _replaceWork(updated);
    } on DioException catch (e) {
      state = state.copyWith(errorMessage: _extractError(e));
    }
  }

  Future<void> completeWork(String botId, String workId) async {
    try {
      final service = _ref.read(workServiceProvider);
      final updated = await service.completeWork(botId, workId);
      _replaceWork(updated);
    } on DioException catch (e) {
      state = state.copyWith(errorMessage: _extractError(e));
    }
  }

  Future<void> cancelWork(String botId, String workId) async {
    try {
      final service = _ref.read(workServiceProvider);
      final updated = await service.cancelWork(botId, workId);
      _replaceWork(updated);
    } on DioException catch (e) {
      state = state.copyWith(errorMessage: _extractError(e));
    }
  }

  void setFilter(WorkFilter filter) {
    state = state.copyWith(filter: filter);
  }

  void clearError() {
    state = state.copyWith(clearError: true);
  }

  void _replaceWork(BotWork updated) {
    state = state.copyWith(
      workItems:
          state.workItems.map((w) => w.id == updated.id ? updated : w).toList(),
    );
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

final workProvider =
    StateNotifierProvider<WorkNotifier, WorkState>((ref) {
  return WorkNotifier(ref);
});
