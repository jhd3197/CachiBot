import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/work.dart';
import 'service_providers.dart';

enum TodoFilter { open, done, all }

class TodosState {
  const TodosState({
    this.todos = const [],
    this.isLoading = false,
    this.errorMessage,
    this.filter = TodoFilter.open,
  });

  final List<Todo> todos;
  final bool isLoading;
  final String? errorMessage;
  final TodoFilter filter;

  TodosState copyWith({
    List<Todo>? todos,
    bool? isLoading,
    String? errorMessage,
    bool clearError = false,
    TodoFilter? filter,
  }) {
    return TodosState(
      todos: todos ?? this.todos,
      isLoading: isLoading ?? this.isLoading,
      errorMessage: clearError ? null : (errorMessage ?? this.errorMessage),
      filter: filter ?? this.filter,
    );
  }

  List<Todo> get filteredTodos {
    switch (filter) {
      case TodoFilter.open:
        return todos.where((t) => t.isOpen).toList();
      case TodoFilter.done:
        return todos.where((t) => t.isDone || t.isDismissed).toList();
      case TodoFilter.all:
        return todos;
    }
  }
}

class TodosNotifier extends StateNotifier<TodosState> {
  TodosNotifier(this._ref) : super(const TodosState());

  final Ref _ref;

  Future<void> loadTodos(String botId) async {
    state = state.copyWith(isLoading: true, clearError: true);
    try {
      final service = _ref.read(workServiceProvider);
      final todos = await service.listTodos(botId);
      state = state.copyWith(todos: todos, isLoading: false);
    } on DioException catch (e) {
      state = state.copyWith(isLoading: false, errorMessage: _extractError(e));
    } catch (e) {
      state = state.copyWith(isLoading: false, errorMessage: e.toString());
    }
  }

  Future<Todo?> createTodo(
    String botId, {
    required String title,
    String? notes,
    String? priority,
    List<String>? tags,
  }) async {
    try {
      final service = _ref.read(workServiceProvider);
      final todo = await service.createTodo(
        botId,
        title: title,
        notes: notes,
        priority: priority,
        tags: tags,
      );
      state = state.copyWith(todos: [todo, ...state.todos]);
      return todo;
    } on DioException catch (e) {
      state = state.copyWith(errorMessage: _extractError(e));
      return null;
    }
  }

  Future<void> completeTodo(String botId, String todoId) async {
    try {
      final service = _ref.read(workServiceProvider);
      final updated = await service.completeTodo(botId, todoId);
      state = state.copyWith(
        todos: state.todos.map((t) => t.id == todoId ? updated : t).toList(),
      );
    } on DioException catch (e) {
      state = state.copyWith(errorMessage: _extractError(e));
    }
  }

  Future<void> dismissTodo(String botId, String todoId) async {
    try {
      final service = _ref.read(workServiceProvider);
      final updated = await service.dismissTodo(botId, todoId);
      state = state.copyWith(
        todos: state.todos.map((t) => t.id == todoId ? updated : t).toList(),
      );
    } on DioException catch (e) {
      state = state.copyWith(errorMessage: _extractError(e));
    }
  }

  Future<void> deleteTodo(String botId, String todoId) async {
    try {
      final service = _ref.read(workServiceProvider);
      await service.deleteTodo(botId, todoId);
      state = state.copyWith(
        todos: state.todos.where((t) => t.id != todoId).toList(),
      );
    } on DioException catch (e) {
      state = state.copyWith(errorMessage: _extractError(e));
    }
  }

  Future<BotWork?> convertToWork(
    String botId,
    String todoId, {
    String? workTitle,
    String? workDescription,
  }) async {
    try {
      final service = _ref.read(workServiceProvider);
      final work = await service.convertTodoToWork(
        botId,
        todoId,
        workTitle: workTitle,
        workDescription: workDescription,
      );
      // Reload todos since the converted one changes status
      await loadTodos(botId);
      return work;
    } on DioException catch (e) {
      state = state.copyWith(errorMessage: _extractError(e));
      return null;
    }
  }

  void setFilter(TodoFilter filter) {
    state = state.copyWith(filter: filter);
  }

  void clear() {
    state = const TodosState();
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

final todosProvider =
    StateNotifierProvider<TodosNotifier, TodosState>((ref) {
  return TodosNotifier(ref);
});
