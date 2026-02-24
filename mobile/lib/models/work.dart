enum WorkStatus {
  pending,
  inProgress,
  completed,
  failed,
  cancelled,
  paused;

  static WorkStatus fromString(String value) {
    switch (value) {
      case 'in_progress':
        return WorkStatus.inProgress;
      default:
        return WorkStatus.values.firstWhere(
          (e) => e.name == value,
          orElse: () => WorkStatus.pending,
        );
    }
  }

  String toApi() {
    switch (this) {
      case WorkStatus.inProgress:
        return 'in_progress';
      default:
        return name;
    }
  }
}

enum TaskStatus {
  pending,
  ready,
  inProgress,
  completed,
  failed,
  blocked,
  skipped;

  static TaskStatus fromString(String value) {
    switch (value) {
      case 'in_progress':
        return TaskStatus.inProgress;
      default:
        return TaskStatus.values.firstWhere(
          (e) => e.name == value,
          orElse: () => TaskStatus.pending,
        );
    }
  }

  String toApi() {
    switch (this) {
      case TaskStatus.inProgress:
        return 'in_progress';
      default:
        return name;
    }
  }
}

enum JobStatus {
  pending,
  running,
  completed,
  failed,
  cancelled;

  static JobStatus fromString(String value) {
    return JobStatus.values.firstWhere(
      (e) => e.name == value,
      orElse: () => JobStatus.pending,
    );
  }
}

enum TodoStatus {
  open,
  done,
  dismissed;

  static TodoStatus fromString(String value) {
    return TodoStatus.values.firstWhere(
      (e) => e.name == value,
      orElse: () => TodoStatus.open,
    );
  }
}

enum Priority {
  low,
  normal,
  high,
  urgent;

  static Priority fromString(String value) {
    return Priority.values.firstWhere(
      (e) => e.name == value,
      orElse: () => Priority.normal,
    );
  }
}

class BotWork {
  const BotWork({
    required this.id,
    required this.botId,
    this.chatId,
    required this.title,
    this.description,
    this.goal,
    this.functionId,
    this.scheduleId,
    this.parentWorkId,
    required this.status,
    required this.priority,
    required this.progress,
    required this.createdAt,
    this.startedAt,
    this.completedAt,
    this.dueAt,
    this.result,
    this.error,
    this.context,
    this.tags = const [],
    this.taskCount,
    this.completedTaskCount,
  });

  final String id;
  final String botId;
  final String? chatId;
  final String title;
  final String? description;
  final String? goal;
  final String? functionId;
  final String? scheduleId;
  final String? parentWorkId;
  final WorkStatus status;
  final Priority priority;
  final double progress;
  final DateTime createdAt;
  final DateTime? startedAt;
  final DateTime? completedAt;
  final DateTime? dueAt;
  final String? result;
  final String? error;
  final Map<String, dynamic>? context;
  final List<String> tags;
  final int? taskCount;
  final int? completedTaskCount;

  factory BotWork.fromJson(Map<String, dynamic> json) {
    return BotWork(
      id: json['id'] as String,
      botId: json['botId'] as String,
      chatId: json['chatId'] as String?,
      title: json['title'] as String,
      description: json['description'] as String?,
      goal: json['goal'] as String?,
      functionId: json['functionId'] as String?,
      scheduleId: json['scheduleId'] as String?,
      parentWorkId: json['parentWorkId'] as String?,
      status: WorkStatus.fromString(json['status'] as String),
      priority: Priority.fromString(json['priority'] as String? ?? 'normal'),
      progress: (json['progress'] as num?)?.toDouble() ?? 0.0,
      createdAt: DateTime.parse(json['createdAt'] as String),
      startedAt: json['startedAt'] != null
          ? DateTime.parse(json['startedAt'] as String)
          : null,
      completedAt: json['completedAt'] != null
          ? DateTime.parse(json['completedAt'] as String)
          : null,
      dueAt: json['dueAt'] != null
          ? DateTime.parse(json['dueAt'] as String)
          : null,
      result: json['result'] as String?,
      error: json['error'] as String?,
      context: json['context'] as Map<String, dynamic>?,
      tags: (json['tags'] as List<dynamic>?)?.cast<String>() ?? [],
      taskCount: json['taskCount'] as int?,
      completedTaskCount: json['completedTaskCount'] as int?,
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'botId': botId,
        'chatId': chatId,
        'title': title,
        'description': description,
        'goal': goal,
        'status': status.toApi(),
        'priority': priority.name,
        'progress': progress,
        'createdAt': createdAt.toIso8601String(),
        'startedAt': startedAt?.toIso8601String(),
        'completedAt': completedAt?.toIso8601String(),
        'dueAt': dueAt?.toIso8601String(),
        'tags': tags,
      };

  BotWork copyWith({
    String? title,
    String? description,
    String? goal,
    WorkStatus? status,
    Priority? priority,
    double? progress,
    int? taskCount,
    int? completedTaskCount,
  }) {
    return BotWork(
      id: id,
      botId: botId,
      chatId: chatId,
      title: title ?? this.title,
      description: description ?? this.description,
      goal: goal ?? this.goal,
      functionId: functionId,
      scheduleId: scheduleId,
      parentWorkId: parentWorkId,
      status: status ?? this.status,
      priority: priority ?? this.priority,
      progress: progress ?? this.progress,
      createdAt: createdAt,
      startedAt: startedAt,
      completedAt: completedAt,
      dueAt: dueAt,
      result: result,
      error: error,
      context: context,
      tags: tags,
      taskCount: taskCount ?? this.taskCount,
      completedTaskCount: completedTaskCount ?? this.completedTaskCount,
    );
  }

  bool get isActive =>
      status == WorkStatus.pending || status == WorkStatus.inProgress;
  bool get isDone => status == WorkStatus.completed;
  bool get hasFailed => status == WorkStatus.failed;
}

class WorkTask {
  const WorkTask({
    required this.id,
    required this.botId,
    required this.workId,
    this.chatId,
    required this.title,
    this.description,
    this.action,
    this.order = 0,
    this.dependsOn = const [],
    required this.status,
    required this.priority,
    this.retryCount = 0,
    this.maxRetries = 0,
    this.timeoutSeconds,
    required this.createdAt,
    this.startedAt,
    this.completedAt,
    this.result,
    this.error,
  });

  final String id;
  final String botId;
  final String workId;
  final String? chatId;
  final String title;
  final String? description;
  final String? action;
  final int order;
  final List<String> dependsOn;
  final TaskStatus status;
  final Priority priority;
  final int retryCount;
  final int maxRetries;
  final int? timeoutSeconds;
  final DateTime createdAt;
  final DateTime? startedAt;
  final DateTime? completedAt;
  final String? result;
  final String? error;

  factory WorkTask.fromJson(Map<String, dynamic> json) {
    return WorkTask(
      id: json['id'] as String,
      botId: json['botId'] as String,
      workId: json['workId'] as String,
      chatId: json['chatId'] as String?,
      title: json['title'] as String,
      description: json['description'] as String?,
      action: json['action'] as String?,
      order: json['order'] as int? ?? 0,
      dependsOn: (json['dependsOn'] as List<dynamic>?)?.cast<String>() ?? [],
      status: TaskStatus.fromString(json['status'] as String),
      priority: Priority.fromString(json['priority'] as String? ?? 'normal'),
      retryCount: json['retryCount'] as int? ?? 0,
      maxRetries: json['maxRetries'] as int? ?? 0,
      timeoutSeconds: json['timeoutSeconds'] as int?,
      createdAt: DateTime.parse(json['createdAt'] as String),
      startedAt: json['startedAt'] != null
          ? DateTime.parse(json['startedAt'] as String)
          : null,
      completedAt: json['completedAt'] != null
          ? DateTime.parse(json['completedAt'] as String)
          : null,
      result: json['result'] as String?,
      error: json['error'] as String?,
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'botId': botId,
        'workId': workId,
        'title': title,
        'description': description,
        'action': action,
        'order': order,
        'dependsOn': dependsOn,
        'status': status.toApi(),
        'priority': priority.name,
        'createdAt': createdAt.toIso8601String(),
      };

  WorkTask copyWith({
    String? title,
    String? description,
    TaskStatus? status,
    Priority? priority,
    String? result,
    String? error,
  }) {
    return WorkTask(
      id: id,
      botId: botId,
      workId: workId,
      chatId: chatId,
      title: title ?? this.title,
      description: description ?? this.description,
      action: action,
      order: order,
      dependsOn: dependsOn,
      status: status ?? this.status,
      priority: priority ?? this.priority,
      retryCount: retryCount,
      maxRetries: maxRetries,
      timeoutSeconds: timeoutSeconds,
      createdAt: createdAt,
      startedAt: startedAt,
      completedAt: completedAt,
      result: result ?? this.result,
      error: error ?? this.error,
    );
  }

  bool get isRunning => status == TaskStatus.inProgress;
  bool get isDone => status == TaskStatus.completed;
  bool get hasFailed => status == TaskStatus.failed;
}

class Job {
  const Job({
    required this.id,
    required this.botId,
    required this.taskId,
    required this.workId,
    this.chatId,
    required this.status,
    required this.attempt,
    required this.progress,
    required this.createdAt,
    this.startedAt,
    this.completedAt,
    this.result,
    this.error,
    this.logs = const [],
  });

  final String id;
  final String botId;
  final String taskId;
  final String workId;
  final String? chatId;
  final JobStatus status;
  final int attempt;
  final double progress;
  final DateTime createdAt;
  final DateTime? startedAt;
  final DateTime? completedAt;
  final String? result;
  final String? error;
  final List<JobLog> logs;

  factory Job.fromJson(Map<String, dynamic> json) {
    return Job(
      id: json['id'] as String,
      botId: json['botId'] as String,
      taskId: json['taskId'] as String,
      workId: json['workId'] as String,
      chatId: json['chatId'] as String?,
      status: JobStatus.fromString(json['status'] as String),
      attempt: json['attempt'] as int? ?? 1,
      progress: (json['progress'] as num?)?.toDouble() ?? 0.0,
      createdAt: DateTime.parse(json['createdAt'] as String),
      startedAt: json['startedAt'] != null
          ? DateTime.parse(json['startedAt'] as String)
          : null,
      completedAt: json['completedAt'] != null
          ? DateTime.parse(json['completedAt'] as String)
          : null,
      result: json['result'] as String?,
      error: json['error'] as String?,
      logs: (json['logs'] as List<dynamic>?)
              ?.map((e) => JobLog.fromJson(e as Map<String, dynamic>))
              .toList() ??
          [],
    );
  }
}

class JobLog {
  const JobLog({
    required this.timestamp,
    required this.level,
    required this.message,
    this.data,
  });

  final DateTime timestamp;
  final String level;
  final String message;
  final Map<String, dynamic>? data;

  factory JobLog.fromJson(Map<String, dynamic> json) {
    return JobLog(
      timestamp: DateTime.parse(json['timestamp'] as String),
      level: json['level'] as String,
      message: json['message'] as String,
      data: json['data'] as Map<String, dynamic>?,
    );
  }
}

class Todo {
  const Todo({
    required this.id,
    required this.botId,
    this.chatId,
    required this.title,
    this.notes,
    required this.status,
    required this.priority,
    required this.createdAt,
    this.completedAt,
    this.remindAt,
    this.convertedToWorkId,
    this.convertedToTaskId,
    this.tags = const [],
  });

  final String id;
  final String botId;
  final String? chatId;
  final String title;
  final String? notes;
  final TodoStatus status;
  final Priority priority;
  final DateTime createdAt;
  final DateTime? completedAt;
  final DateTime? remindAt;
  final String? convertedToWorkId;
  final String? convertedToTaskId;
  final List<String> tags;

  factory Todo.fromJson(Map<String, dynamic> json) {
    return Todo(
      id: json['id'] as String,
      botId: json['botId'] as String,
      chatId: json['chatId'] as String?,
      title: json['title'] as String,
      notes: json['notes'] as String?,
      status: TodoStatus.fromString(json['status'] as String),
      priority: Priority.fromString(json['priority'] as String? ?? 'normal'),
      createdAt: DateTime.parse(json['createdAt'] as String),
      completedAt: json['completedAt'] != null
          ? DateTime.parse(json['completedAt'] as String)
          : null,
      remindAt: json['remindAt'] != null
          ? DateTime.parse(json['remindAt'] as String)
          : null,
      convertedToWorkId: json['convertedToWorkId'] as String?,
      convertedToTaskId: json['convertedToTaskId'] as String?,
      tags: (json['tags'] as List<dynamic>?)?.cast<String>() ?? [],
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'botId': botId,
        'chatId': chatId,
        'title': title,
        'notes': notes,
        'status': status.name,
        'priority': priority.name,
        'createdAt': createdAt.toIso8601String(),
        'completedAt': completedAt?.toIso8601String(),
        'remindAt': remindAt?.toIso8601String(),
        'tags': tags,
      };

  Todo copyWith({
    String? title,
    String? notes,
    TodoStatus? status,
    Priority? priority,
    DateTime? remindAt,
    List<String>? tags,
  }) {
    return Todo(
      id: id,
      botId: botId,
      chatId: chatId,
      title: title ?? this.title,
      notes: notes ?? this.notes,
      status: status ?? this.status,
      priority: priority ?? this.priority,
      createdAt: createdAt,
      completedAt: completedAt,
      remindAt: remindAt ?? this.remindAt,
      convertedToWorkId: convertedToWorkId,
      convertedToTaskId: convertedToTaskId,
      tags: tags ?? this.tags,
    );
  }

  bool get isOpen => status == TodoStatus.open;
  bool get isDone => status == TodoStatus.done;
  bool get isDismissed => status == TodoStatus.dismissed;
}
