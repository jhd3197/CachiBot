import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/work.dart';
import 'service_providers.dart';

class TasksState {
  const TasksState({
    this.tasks = const [],
    this.isLoading = false,
    this.errorMessage,
  });

  final List<WorkTask> tasks;
  final bool isLoading;
  final String? errorMessage;

  TasksState copyWith({
    List<WorkTask>? tasks,
    bool? isLoading,
    String? errorMessage,
    bool clearError = false,
  }) {
    return TasksState(
      tasks: tasks ?? this.tasks,
      isLoading: isLoading ?? this.isLoading,
      errorMessage: clearError ? null : (errorMessage ?? this.errorMessage),
    );
  }
}

class TasksNotifier extends StateNotifier<TasksState> {
  TasksNotifier(this._ref) : super(const TasksState());

  final Ref _ref;

  Future<void> loadTasks(String botId, String workId) async {
    state = state.copyWith(isLoading: true, clearError: true);
    try {
      final service = _ref.read(workServiceProvider);
      final tasks = await service.listTasks(botId, workId);
      tasks.sort((a, b) => a.order.compareTo(b.order));
      state = state.copyWith(tasks: tasks, isLoading: false);
    } on DioException catch (e) {
      state = state.copyWith(isLoading: false, errorMessage: _extractError(e));
    } catch (e) {
      state = state.copyWith(isLoading: false, errorMessage: e.toString());
    }
  }

  Future<WorkTask?> createTask(
    String botId,
    String workId, {
    required String title,
    String? description,
    String? priority,
  }) async {
    try {
      final service = _ref.read(workServiceProvider);
      final task = await service.createTask(
        botId,
        workId,
        title: title,
        description: description,
        priority: priority,
      );
      state = state.copyWith(tasks: [...state.tasks, task]);
      return task;
    } on DioException catch (e) {
      state = state.copyWith(errorMessage: _extractError(e));
      return null;
    }
  }

  Future<void> updateTask(
    String botId,
    String taskId, {
    String? title,
    String? description,
    String? status,
    String? priority,
  }) async {
    try {
      final service = _ref.read(workServiceProvider);
      final updated = await service.updateTask(
        botId,
        taskId,
        title: title,
        description: description,
        status: status,
        priority: priority,
      );
      state = state.copyWith(
        tasks: state.tasks.map((t) => t.id == taskId ? updated : t).toList(),
      );
    } on DioException catch (e) {
      state = state.copyWith(errorMessage: _extractError(e));
    }
  }

  Future<void> startTask(String botId, String taskId) async {
    try {
      final service = _ref.read(workServiceProvider);
      final updated = await service.startTask(botId, taskId);
      state = state.copyWith(
        tasks: state.tasks.map((t) => t.id == taskId ? updated : t).toList(),
      );
    } on DioException catch (e) {
      state = state.copyWith(errorMessage: _extractError(e));
    }
  }

  Future<void> completeTask(String botId, String taskId) async {
    try {
      final service = _ref.read(workServiceProvider);
      final updated = await service.completeTask(botId, taskId);
      state = state.copyWith(
        tasks: state.tasks.map((t) => t.id == taskId ? updated : t).toList(),
      );
    } on DioException catch (e) {
      state = state.copyWith(errorMessage: _extractError(e));
    }
  }

  Future<void> failTask(String botId, String taskId, {String? error}) async {
    try {
      final service = _ref.read(workServiceProvider);
      final updated = await service.failTask(botId, taskId, error: error);
      state = state.copyWith(
        tasks: state.tasks.map((t) => t.id == taskId ? updated : t).toList(),
      );
    } on DioException catch (e) {
      state = state.copyWith(errorMessage: _extractError(e));
    }
  }

  Future<void> deleteTask(String botId, String taskId) async {
    try {
      final service = _ref.read(workServiceProvider);
      await service.deleteTask(botId, taskId);
      state = state.copyWith(
        tasks: state.tasks.where((t) => t.id != taskId).toList(),
      );
    } on DioException catch (e) {
      state = state.copyWith(errorMessage: _extractError(e));
    }
  }

  void clear() {
    state = const TasksState();
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

final tasksProvider =
    StateNotifierProvider<TasksNotifier, TasksState>((ref) {
  return TasksNotifier(ref);
});
