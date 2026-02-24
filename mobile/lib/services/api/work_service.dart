import '../../models/work.dart';
import 'api_client.dart';

class WorkService {
  WorkService(this._client);

  final ApiClient _client;

  // ---- Work CRUD ----

  Future<List<BotWork>> listWork(
    String botId, {
    String? status,
    int? limit,
  }) async {
    final params = <String, dynamic>{};
    if (status != null) params['status'] = status;
    if (limit != null) params['limit'] = limit;

    final response = await _client.dio.get(
      '/api/bots/$botId/work',
      queryParameters: params,
    );
    final list = response.data as List<dynamic>;
    return list.map((e) => BotWork.fromJson(e as Map<String, dynamic>)).toList();
  }

  Future<List<BotWork>> getActiveWork(String botId) async {
    final response = await _client.dio.get('/api/bots/$botId/work/active');
    final list = response.data as List<dynamic>;
    return list.map((e) => BotWork.fromJson(e as Map<String, dynamic>)).toList();
  }

  Future<BotWork> getWork(String botId, String workId) async {
    final response = await _client.dio.get('/api/bots/$botId/work/$workId');
    return BotWork.fromJson(response.data as Map<String, dynamic>);
  }

  Future<BotWork> createWork(
    String botId, {
    required String title,
    String? description,
    String? goal,
    String? chatId,
    String? priority,
    String? dueAt,
    List<String>? tags,
  }) async {
    final data = <String, dynamic>{
      'title': title,
    };
    if (description != null) data['description'] = description;
    if (goal != null) data['goal'] = goal;
    if (chatId != null) data['chatId'] = chatId;
    if (priority != null) data['priority'] = priority;
    if (dueAt != null) data['dueAt'] = dueAt;
    if (tags != null) data['tags'] = tags;

    final response = await _client.dio.post(
      '/api/bots/$botId/work',
      data: data,
    );
    return BotWork.fromJson(response.data as Map<String, dynamic>);
  }

  Future<BotWork> updateWork(
    String botId,
    String workId, {
    String? title,
    String? description,
    String? goal,
    String? status,
    String? priority,
    double? progress,
    String? dueAt,
    List<String>? tags,
  }) async {
    final data = <String, dynamic>{};
    if (title != null) data['title'] = title;
    if (description != null) data['description'] = description;
    if (goal != null) data['goal'] = goal;
    if (status != null) data['status'] = status;
    if (priority != null) data['priority'] = priority;
    if (progress != null) data['progress'] = progress;
    if (dueAt != null) data['dueAt'] = dueAt;
    if (tags != null) data['tags'] = tags;

    final response = await _client.dio.patch(
      '/api/bots/$botId/work/$workId',
      data: data,
    );
    return BotWork.fromJson(response.data as Map<String, dynamic>);
  }

  Future<void> deleteWork(String botId, String workId) async {
    await _client.dio.delete('/api/bots/$botId/work/$workId');
  }

  // ---- Work Actions ----

  Future<BotWork> startWork(String botId, String workId) async {
    final response = await _client.dio.post('/api/bots/$botId/work/$workId/start');
    return BotWork.fromJson(response.data as Map<String, dynamic>);
  }

  Future<BotWork> completeWork(String botId, String workId, {String? result}) async {
    final params = <String, dynamic>{};
    if (result != null) params['result'] = result;

    final response = await _client.dio.post(
      '/api/bots/$botId/work/$workId/complete',
      queryParameters: params,
    );
    return BotWork.fromJson(response.data as Map<String, dynamic>);
  }

  Future<BotWork> failWork(String botId, String workId, {String? error}) async {
    final params = <String, dynamic>{};
    if (error != null) params['error'] = error;

    final response = await _client.dio.post(
      '/api/bots/$botId/work/$workId/fail',
      queryParameters: params,
    );
    return BotWork.fromJson(response.data as Map<String, dynamic>);
  }

  Future<BotWork> cancelWork(String botId, String workId) async {
    final response = await _client.dio.post('/api/bots/$botId/work/$workId/cancel');
    return BotWork.fromJson(response.data as Map<String, dynamic>);
  }

  // ---- Tasks ----

  Future<List<WorkTask>> listTasks(String botId, String workId) async {
    final response = await _client.dio.get('/api/bots/$botId/work/$workId/tasks');
    final list = response.data as List<dynamic>;
    return list.map((e) => WorkTask.fromJson(e as Map<String, dynamic>)).toList();
  }

  Future<WorkTask> createTask(
    String botId,
    String workId, {
    required String title,
    String? description,
    String? action,
    int? order,
    List<String>? dependsOn,
    String? priority,
  }) async {
    final data = <String, dynamic>{
      'title': title,
    };
    if (description != null) data['description'] = description;
    if (action != null) data['action'] = action;
    if (order != null) data['order'] = order;
    if (dependsOn != null) data['dependsOn'] = dependsOn;
    if (priority != null) data['priority'] = priority;

    final response = await _client.dio.post(
      '/api/bots/$botId/work/$workId/tasks',
      data: data,
    );
    return WorkTask.fromJson(response.data as Map<String, dynamic>);
  }

  Future<WorkTask> updateTask(
    String botId,
    String taskId, {
    String? title,
    String? description,
    String? status,
    String? priority,
  }) async {
    final data = <String, dynamic>{};
    if (title != null) data['title'] = title;
    if (description != null) data['description'] = description;
    if (status != null) data['status'] = status;
    if (priority != null) data['priority'] = priority;

    final response = await _client.dio.patch(
      '/api/bots/$botId/tasks/$taskId',
      data: data,
    );
    return WorkTask.fromJson(response.data as Map<String, dynamic>);
  }

  Future<void> deleteTask(String botId, String taskId) async {
    await _client.dio.delete('/api/bots/$botId/tasks/$taskId');
  }

  Future<WorkTask> startTask(String botId, String taskId) async {
    final response = await _client.dio.post('/api/bots/$botId/tasks/$taskId/start');
    return WorkTask.fromJson(response.data as Map<String, dynamic>);
  }

  Future<WorkTask> completeTask(String botId, String taskId, {String? result}) async {
    final params = <String, dynamic>{};
    if (result != null) params['result'] = result;

    final response = await _client.dio.post(
      '/api/bots/$botId/tasks/$taskId/complete',
      queryParameters: params,
    );
    return WorkTask.fromJson(response.data as Map<String, dynamic>);
  }

  Future<WorkTask> failTask(String botId, String taskId, {String? error}) async {
    final params = <String, dynamic>{};
    if (error != null) params['error'] = error;

    final response = await _client.dio.post(
      '/api/bots/$botId/tasks/$taskId/fail',
      queryParameters: params,
    );
    return WorkTask.fromJson(response.data as Map<String, dynamic>);
  }

  // ---- Jobs ----

  Future<List<Job>> listJobsForTask(String botId, String taskId) async {
    final response = await _client.dio.get('/api/bots/$botId/tasks/$taskId/jobs');
    final list = response.data as List<dynamic>;
    return list.map((e) => Job.fromJson(e as Map<String, dynamic>)).toList();
  }

  Future<List<Job>> listJobsForWork(String botId, String workId) async {
    final response = await _client.dio.get('/api/bots/$botId/work/$workId/jobs');
    final list = response.data as List<dynamic>;
    return list.map((e) => Job.fromJson(e as Map<String, dynamic>)).toList();
  }

  Future<Job> getJob(String botId, String jobId) async {
    final response = await _client.dio.get('/api/bots/$botId/jobs/$jobId');
    return Job.fromJson(response.data as Map<String, dynamic>);
  }

  // ---- Todos ----

  Future<List<Todo>> listTodos(
    String botId, {
    String? status,
    int? limit,
  }) async {
    final params = <String, dynamic>{};
    if (status != null) params['status'] = status;
    if (limit != null) params['limit'] = limit;

    final response = await _client.dio.get(
      '/api/bots/$botId/todos',
      queryParameters: params,
    );
    final list = response.data as List<dynamic>;
    return list.map((e) => Todo.fromJson(e as Map<String, dynamic>)).toList();
  }

  Future<List<Todo>> getOpenTodos(String botId) async {
    final response = await _client.dio.get('/api/bots/$botId/todos/open');
    final list = response.data as List<dynamic>;
    return list.map((e) => Todo.fromJson(e as Map<String, dynamic>)).toList();
  }

  Future<Todo> createTodo(
    String botId, {
    required String title,
    String? notes,
    String? chatId,
    String? priority,
    String? remindAt,
    List<String>? tags,
  }) async {
    final data = <String, dynamic>{
      'title': title,
    };
    if (notes != null) data['notes'] = notes;
    if (chatId != null) data['chatId'] = chatId;
    if (priority != null) data['priority'] = priority;
    if (remindAt != null) data['remindAt'] = remindAt;
    if (tags != null) data['tags'] = tags;

    final response = await _client.dio.post(
      '/api/bots/$botId/todos',
      data: data,
    );
    return Todo.fromJson(response.data as Map<String, dynamic>);
  }

  Future<Todo> updateTodo(
    String botId,
    String todoId, {
    String? title,
    String? notes,
    String? status,
    String? priority,
    String? remindAt,
    List<String>? tags,
  }) async {
    final data = <String, dynamic>{};
    if (title != null) data['title'] = title;
    if (notes != null) data['notes'] = notes;
    if (status != null) data['status'] = status;
    if (priority != null) data['priority'] = priority;
    if (remindAt != null) data['remindAt'] = remindAt;
    if (tags != null) data['tags'] = tags;

    final response = await _client.dio.patch(
      '/api/bots/$botId/todos/$todoId',
      data: data,
    );
    return Todo.fromJson(response.data as Map<String, dynamic>);
  }

  Future<void> deleteTodo(String botId, String todoId) async {
    await _client.dio.delete('/api/bots/$botId/todos/$todoId');
  }

  Future<Todo> completeTodo(String botId, String todoId) async {
    final response = await _client.dio.post('/api/bots/$botId/todos/$todoId/done');
    return Todo.fromJson(response.data as Map<String, dynamic>);
  }

  Future<Todo> dismissTodo(String botId, String todoId) async {
    final response = await _client.dio.post('/api/bots/$botId/todos/$todoId/dismiss');
    return Todo.fromJson(response.data as Map<String, dynamic>);
  }

  Future<BotWork> convertTodoToWork(
    String botId,
    String todoId, {
    bool toWork = true,
    String? workTitle,
    String? workDescription,
    String? priority,
  }) async {
    final data = <String, dynamic>{
      'toWork': toWork,
    };
    if (workTitle != null) data['workTitle'] = workTitle;
    if (workDescription != null) data['workDescription'] = workDescription;
    if (priority != null) data['priority'] = priority;

    final response = await _client.dio.post(
      '/api/bots/$botId/todos/$todoId/convert',
      data: data,
    );
    return BotWork.fromJson(response.data as Map<String, dynamic>);
  }
}
