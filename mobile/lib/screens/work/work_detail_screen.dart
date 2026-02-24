import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/utils/time_utils.dart';
import '../../models/work.dart';
import '../../providers/tasks_provider.dart';
import '../../providers/work_provider.dart';

class WorkDetailScreen extends ConsumerStatefulWidget {
  const WorkDetailScreen({
    required this.botId,
    required this.workId,
    super.key,
  });

  final String botId;
  final String workId;

  @override
  ConsumerState<WorkDetailScreen> createState() => _WorkDetailScreenState();
}

class _WorkDetailScreenState extends ConsumerState<WorkDetailScreen> {
  @override
  void initState() {
    super.initState();
    Future.microtask(() {
      ref.read(tasksProvider.notifier).loadTasks(widget.botId, widget.workId);
    });
  }

  BotWork? _findWork(WorkState state) {
    return state.workItems.where((w) => w.id == widget.workId).firstOrNull;
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final workState = ref.watch(workProvider);
    final tasksState = ref.watch(tasksProvider);
    final work = _findWork(workState);

    if (work == null) {
      return Scaffold(
        appBar: AppBar(),
        body: const Center(child: CircularProgressIndicator()),
      );
    }

    return Scaffold(
      appBar: AppBar(
        title: Text(work.title, overflow: TextOverflow.ellipsis),
        actions: [
          PopupMenuButton<String>(
            onSelected: (action) => _handleAction(action, work),
            itemBuilder: (context) => [
              if (work.status == WorkStatus.pending)
                const PopupMenuItem(value: 'start', child: Text('Start')),
              if (work.isActive)
                const PopupMenuItem(
                    value: 'complete', child: Text('Complete')),
              if (work.isActive)
                const PopupMenuItem(value: 'cancel', child: Text('Cancel')),
              const PopupMenuItem(value: 'delete', child: Text('Delete')),
            ],
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton.small(
        onPressed: () => _showAddTaskDialog(),
        child: const Icon(Icons.add),
      ),
      body: RefreshIndicator(
        onRefresh: () => ref
            .read(tasksProvider.notifier)
            .loadTasks(widget.botId, widget.workId),
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            // Header card
            _WorkHeader(work: work),
            const SizedBox(height: 16),

            // Action buttons
            _ActionButtons(
              work: work,
              onStart: () => ref
                  .read(workProvider.notifier)
                  .startWork(widget.botId, work.id),
              onComplete: () => ref
                  .read(workProvider.notifier)
                  .completeWork(widget.botId, work.id),
              onCancel: () => ref
                  .read(workProvider.notifier)
                  .cancelWork(widget.botId, work.id),
            ),
            const SizedBox(height: 16),

            // Tasks section
            Text('Tasks', style: theme.textTheme.titleMedium),
            const SizedBox(height: 8),

            if (tasksState.isLoading && tasksState.tasks.isEmpty)
              const Padding(
                padding: EdgeInsets.all(32),
                child: Center(child: CircularProgressIndicator()),
              )
            else if (tasksState.tasks.isEmpty)
              Center(
                child: Padding(
                  padding: const EdgeInsets.all(32),
                  child: Text(
                    'No tasks yet',
                    style: theme.textTheme.bodyLarge?.copyWith(
                      color: theme.colorScheme.onSurface
                          .withValues(alpha: 0.5),
                    ),
                  ),
                ),
              )
            else
              ...tasksState.tasks.map(
                (task) => _TaskItem(
                  task: task,
                  botId: widget.botId,
                ),
              ),

            // Tags
            if (work.tags.isNotEmpty) ...[
              const SizedBox(height: 16),
              Wrap(
                spacing: 6,
                runSpacing: 6,
                children: work.tags
                    .map((tag) => Chip(
                          label: Text(tag),
                          visualDensity: VisualDensity.compact,
                        ))
                    .toList(),
              ),
            ],

            const SizedBox(height: 80),
          ],
        ),
      ),
    );
  }

  void _handleAction(String action, BotWork work) {
    switch (action) {
      case 'start':
        ref.read(workProvider.notifier).startWork(widget.botId, work.id);
      case 'complete':
        ref.read(workProvider.notifier).completeWork(widget.botId, work.id);
      case 'cancel':
        ref.read(workProvider.notifier).cancelWork(widget.botId, work.id);
      case 'delete':
        _confirmDelete(work);
    }
  }

  Future<void> _confirmDelete(BotWork work) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Delete Work'),
        content: Text('Delete "${work.title}"? This cannot be undone.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text('Delete'),
          ),
        ],
      ),
    );
    if (confirmed == true && mounted) {
      await ref
          .read(workProvider.notifier)
          .deleteWork(widget.botId, work.id);
      if (mounted) context.pop();
    }
  }

  Future<void> _showAddTaskDialog() async {
    final titleController = TextEditingController();
    final descController = TextEditingController();

    final result = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Add Task'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              controller: titleController,
              decoration: const InputDecoration(
                labelText: 'Title',
                border: OutlineInputBorder(),
              ),
              autofocus: true,
            ),
            const SizedBox(height: 12),
            TextField(
              controller: descController,
              decoration: const InputDecoration(
                labelText: 'Description (optional)',
                border: OutlineInputBorder(),
              ),
              maxLines: 2,
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.of(ctx).pop(true),
            child: const Text('Add'),
          ),
        ],
      ),
    );

    if (result == true && mounted) {
      final title = titleController.text.trim();
      if (title.isNotEmpty) {
        final desc = descController.text.trim();
        ref.read(tasksProvider.notifier).createTask(
              widget.botId,
              widget.workId,
              title: title,
              description: desc.isNotEmpty ? desc : null,
            );
      }
    }

    titleController.dispose();
    descController.dispose();
  }
}

class _WorkHeader extends StatelessWidget {
  const _WorkHeader({required this.work});

  final BotWork work;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Status + priority
            Row(
              children: [
                _StatusChip(status: work.status),
                const SizedBox(width: 8),
                _PriorityChip(priority: work.priority),
                const Spacer(),
                Text(
                  formatRelativeTime(work.createdAt),
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: theme.colorScheme.onSurface.withValues(alpha: 0.5),
                  ),
                ),
              ],
            ),

            // Description
            if (work.description != null) ...[
              const SizedBox(height: 12),
              Text(work.description!, style: theme.textTheme.bodyMedium),
            ],

            // Goal
            if (work.goal != null) ...[
              const SizedBox(height: 8),
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Icon(Icons.flag_outlined,
                      size: 16, color: theme.colorScheme.primary),
                  const SizedBox(width: 6),
                  Expanded(
                    child: Text(
                      work.goal!,
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: theme.colorScheme.primary,
                      ),
                    ),
                  ),
                ],
              ),
            ],

            // Progress
            if (work.progress > 0 || work.isActive) ...[
              const SizedBox(height: 12),
              Row(
                children: [
                  Expanded(
                    child: ClipRRect(
                      borderRadius: BorderRadius.circular(4),
                      child: LinearProgressIndicator(
                        value: work.progress,
                        minHeight: 6,
                        backgroundColor:
                            theme.colorScheme.surfaceContainerHigh,
                      ),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Text(
                    '${(work.progress * 100).toInt()}%',
                    style: theme.textTheme.bodySmall,
                  ),
                ],
              ),
            ],

            // Error
            if (work.error != null) ...[
              const SizedBox(height: 8),
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: theme.colorScheme.errorContainer,
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Row(
                  children: [
                    Icon(Icons.error_outline,
                        size: 16, color: theme.colorScheme.error),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        work.error!,
                        style: theme.textTheme.bodySmall?.copyWith(
                          color: theme.colorScheme.onErrorContainer,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _StatusChip extends StatelessWidget {
  const _StatusChip({required this.status});

  final WorkStatus status;

  @override
  Widget build(BuildContext context) {
    Color color;
    String label;
    switch (status) {
      case WorkStatus.pending:
        color = Colors.grey;
        label = 'Pending';
      case WorkStatus.inProgress:
        color = Colors.blue;
        label = 'In Progress';
      case WorkStatus.completed:
        color = Colors.green;
        label = 'Completed';
      case WorkStatus.failed:
        color = Theme.of(context).colorScheme.error;
        label = 'Failed';
      case WorkStatus.cancelled:
        color = Colors.orange;
        label = 'Cancelled';
      case WorkStatus.paused:
        color = Colors.amber;
        label = 'Paused';
    }

    return Chip(
      label: Text(label,
          style: TextStyle(color: color, fontSize: 12)),
      backgroundColor: color.withValues(alpha: 0.15),
      side: BorderSide.none,
      visualDensity: VisualDensity.compact,
      materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
    );
  }
}

class _PriorityChip extends StatelessWidget {
  const _PriorityChip({required this.priority});

  final Priority priority;

  @override
  Widget build(BuildContext context) {
    if (priority == Priority.normal) return const SizedBox.shrink();

    Color color;
    String label;
    switch (priority) {
      case Priority.urgent:
        color = Colors.red;
        label = 'Urgent';
      case Priority.high:
        color = Colors.orange;
        label = 'High';
      case Priority.low:
        color = Colors.grey;
        label = 'Low';
      case Priority.normal:
        color = Colors.blue;
        label = 'Normal';
    }

    return Chip(
      avatar: Icon(Icons.flag, size: 14, color: color),
      label: Text(label, style: TextStyle(color: color, fontSize: 12)),
      backgroundColor: color.withValues(alpha: 0.1),
      side: BorderSide.none,
      visualDensity: VisualDensity.compact,
      materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
    );
  }
}

class _ActionButtons extends StatelessWidget {
  const _ActionButtons({
    required this.work,
    required this.onStart,
    required this.onComplete,
    required this.onCancel,
  });

  final BotWork work;
  final VoidCallback onStart;
  final VoidCallback onComplete;
  final VoidCallback onCancel;

  @override
  Widget build(BuildContext context) {
    if (work.isDone || work.status == WorkStatus.cancelled) {
      return const SizedBox.shrink();
    }

    return Row(
      children: [
        if (work.status == WorkStatus.pending)
          Expanded(
            child: FilledButton.icon(
              onPressed: onStart,
              icon: const Icon(Icons.play_arrow, size: 18),
              label: const Text('Start'),
            ),
          ),
        if (work.isActive) ...[
          Expanded(
            child: FilledButton.icon(
              onPressed: onComplete,
              icon: const Icon(Icons.check, size: 18),
              label: const Text('Complete'),
            ),
          ),
          const SizedBox(width: 8),
          OutlinedButton.icon(
            onPressed: onCancel,
            icon: const Icon(Icons.close, size: 18),
            label: const Text('Cancel'),
          ),
        ],
      ],
    );
  }
}

class _TaskItem extends ConsumerWidget {
  const _TaskItem({required this.task, required this.botId});

  final WorkTask task;
  final String botId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context);

    IconData icon;
    Color iconColor;
    switch (task.status) {
      case TaskStatus.completed:
        icon = Icons.check_circle;
        iconColor = Colors.green;
      case TaskStatus.failed:
        icon = Icons.error;
        iconColor = theme.colorScheme.error;
      case TaskStatus.inProgress:
        icon = Icons.play_circle_filled;
        iconColor = Colors.blue;
      case TaskStatus.blocked:
        icon = Icons.block;
        iconColor = Colors.orange;
      case TaskStatus.skipped:
        icon = Icons.skip_next;
        iconColor = Colors.grey;
      default:
        icon = Icons.radio_button_unchecked;
        iconColor = Colors.grey;
    }

    return Card(
      margin: const EdgeInsets.only(bottom: 6),
      child: ListTile(
        dense: true,
        leading: Icon(icon, color: iconColor, size: 22),
        title: Text(
          task.title,
          style: theme.textTheme.bodyMedium?.copyWith(
            decoration:
                task.isDone ? TextDecoration.lineThrough : null,
          ),
        ),
        subtitle: task.description != null
            ? Text(
                task.description!,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: theme.textTheme.bodySmall?.copyWith(
                  color: theme.colorScheme.onSurface.withValues(alpha: 0.6),
                ),
              )
            : null,
        trailing: task.error != null
            ? Tooltip(
                message: task.error!,
                child: Icon(Icons.warning_amber,
                    size: 18, color: theme.colorScheme.error),
              )
            : null,
        onTap: () {
          if (task.status == TaskStatus.pending ||
              task.status == TaskStatus.ready) {
            ref
                .read(tasksProvider.notifier)
                .startTask(botId, task.id);
          } else if (task.isRunning) {
            ref
                .read(tasksProvider.notifier)
                .completeTask(botId, task.id);
          }
        },
      ),
    );
  }
}
