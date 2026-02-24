import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/utils/time_utils.dart';
import '../../models/work.dart';
import '../../providers/work_provider.dart';

class WorkListScreen extends ConsumerStatefulWidget {
  const WorkListScreen({required this.botId, super.key});

  final String botId;

  @override
  ConsumerState<WorkListScreen> createState() => _WorkListScreenState();
}

class _WorkListScreenState extends ConsumerState<WorkListScreen>
    with AutomaticKeepAliveClientMixin {
  @override
  bool get wantKeepAlive => true;

  @override
  void initState() {
    super.initState();
    Future.microtask(
      () => ref.read(workProvider.notifier).loadWork(widget.botId),
    );
  }

  @override
  Widget build(BuildContext context) {
    super.build(context);
    final theme = Theme.of(context);
    final state = ref.watch(workProvider);

    return Stack(
      children: [
        Column(
          children: [
            // Filter chips
            SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              child: Row(
                children: WorkFilter.values.map((filter) {
                  final isSelected = state.filter == filter;
                  return Padding(
                    padding: const EdgeInsets.only(right: 8),
                    child: FilterChip(
                      label: Text(_filterLabel(filter)),
                      selected: isSelected,
                      onSelected: (_) =>
                          ref.read(workProvider.notifier).setFilter(filter),
                    ),
                  );
                }).toList(),
              ),
            ),

            // Content
            Expanded(child: _buildContent(theme, state)),
          ],
        ),

        // FAB
        Positioned(
          right: 16,
          bottom: 16,
          child: FloatingActionButton(
            heroTag: 'work_${widget.botId}',
            onPressed: () => _showCreateDialog(context),
            child: const Icon(Icons.add),
          ),
        ),
      ],
    );
  }

  String _filterLabel(WorkFilter filter) {
    switch (filter) {
      case WorkFilter.all:
        return 'All';
      case WorkFilter.active:
        return 'Active';
      case WorkFilter.completed:
        return 'Completed';
      case WorkFilter.failed:
        return 'Failed';
    }
  }

  Widget _buildContent(ThemeData theme, WorkState state) {
    if (state.isLoading && state.workItems.isEmpty) {
      return const Center(child: CircularProgressIndicator());
    }

    if (state.errorMessage != null && state.workItems.isEmpty) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(Icons.error_outline,
                  size: 48, color: theme.colorScheme.error),
              const SizedBox(height: 16),
              Text(state.errorMessage!, textAlign: TextAlign.center),
              const SizedBox(height: 16),
              OutlinedButton.icon(
                onPressed: () =>
                    ref.read(workProvider.notifier).loadWork(widget.botId),
                icon: const Icon(Icons.refresh),
                label: const Text('Retry'),
              ),
            ],
          ),
        ),
      );
    }

    final items = state.filteredItems;

    if (items.isEmpty) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.work_outline,
                size: 64,
                color: theme.colorScheme.onSurface.withValues(alpha: 0.3)),
            const SizedBox(height: 16),
            Text(
              state.filter == WorkFilter.all
                  ? 'No work items'
                  : 'No ${_filterLabel(state.filter).toLowerCase()} items',
              style: theme.textTheme.bodyLarge?.copyWith(
                color: theme.colorScheme.onSurface.withValues(alpha: 0.5),
              ),
            ),
          ],
        ),
      );
    }

    return RefreshIndicator(
      onRefresh: () => ref.read(workProvider.notifier).loadWork(widget.botId),
      child: ListView.builder(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
        itemCount: items.length,
        itemBuilder: (context, index) {
          final work = items[index];
          return _WorkCard(
            work: work,
            onTap: () => context.push('/bot/${widget.botId}/work/${work.id}'),
            onLongPress: () => _showContextMenu(work),
          );
        },
      ),
    );
  }

  void _showContextMenu(BotWork work) {
    showModalBottomSheet(
      context: context,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (ctx) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (work.status == WorkStatus.pending)
              ListTile(
                leading: const Icon(Icons.play_arrow),
                title: const Text('Start'),
                onTap: () {
                  Navigator.of(ctx).pop();
                  ref
                      .read(workProvider.notifier)
                      .startWork(widget.botId, work.id);
                },
              ),
            if (work.isActive)
              ListTile(
                leading: const Icon(Icons.check_circle_outline),
                title: const Text('Complete'),
                onTap: () {
                  Navigator.of(ctx).pop();
                  ref
                      .read(workProvider.notifier)
                      .completeWork(widget.botId, work.id);
                },
              ),
            if (work.isActive)
              ListTile(
                leading: const Icon(Icons.cancel_outlined),
                title: const Text('Cancel'),
                onTap: () {
                  Navigator.of(ctx).pop();
                  ref
                      .read(workProvider.notifier)
                      .cancelWork(widget.botId, work.id);
                },
              ),
            ListTile(
              leading: Icon(Icons.delete_outline,
                  color: Theme.of(ctx).colorScheme.error),
              title: Text('Delete',
                  style: TextStyle(color: Theme.of(ctx).colorScheme.error)),
              onTap: () {
                Navigator.of(ctx).pop();
                _confirmDelete(work);
              },
            ),
          ],
        ),
      ),
    );
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
      ref.read(workProvider.notifier).deleteWork(widget.botId, work.id);
    }
  }

  Future<void> _showCreateDialog(BuildContext context) async {
    final titleController = TextEditingController();
    final descriptionController = TextEditingController();

    final result = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Create Work'),
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
              controller: descriptionController,
              decoration: const InputDecoration(
                labelText: 'Description (optional)',
                border: OutlineInputBorder(),
              ),
              maxLines: 3,
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
            child: const Text('Create'),
          ),
        ],
      ),
    );

    if (result == true && mounted) {
      final title = titleController.text.trim();
      if (title.isNotEmpty) {
        final desc = descriptionController.text.trim();
        ref.read(workProvider.notifier).createWork(
              widget.botId,
              title: title,
              description: desc.isNotEmpty ? desc : null,
            );
      }
    }

    titleController.dispose();
    descriptionController.dispose();
  }
}

class _WorkCard extends StatelessWidget {
  const _WorkCard({
    required this.work,
    required this.onTap,
    required this.onLongPress,
  });

  final BotWork work;
  final VoidCallback onTap;
  final VoidCallback onLongPress;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: InkWell(
        onTap: onTap,
        onLongPress: onLongPress,
        borderRadius: BorderRadius.circular(12),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Title row
              Row(
                children: [
                  _PriorityIndicator(priority: work.priority),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      work.title,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: theme.textTheme.titleSmall
                          ?.copyWith(fontWeight: FontWeight.w600),
                    ),
                  ),
                  _StatusBadge(status: work.status),
                ],
              ),

              // Description
              if (work.description != null) ...[
                const SizedBox(height: 4),
                Text(
                  work.description!,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: theme.colorScheme.onSurface.withValues(alpha: 0.7),
                  ),
                ),
              ],

              const SizedBox(height: 8),

              // Progress bar
              if (work.progress > 0 || work.isActive)
                ClipRRect(
                  borderRadius: BorderRadius.circular(4),
                  child: LinearProgressIndicator(
                    value: work.progress,
                    minHeight: 4,
                    backgroundColor: theme.colorScheme.surfaceContainerHigh,
                  ),
                ),

              const SizedBox(height: 6),

              // Bottom row: task count + time
              Row(
                children: [
                  if (work.taskCount != null) ...[
                    Icon(Icons.task_alt,
                        size: 14,
                        color: theme.colorScheme.onSurface
                            .withValues(alpha: 0.5)),
                    const SizedBox(width: 4),
                    Text(
                      '${work.completedTaskCount ?? 0}/${work.taskCount}',
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: theme.colorScheme.onSurface
                            .withValues(alpha: 0.5),
                      ),
                    ),
                    const SizedBox(width: 12),
                  ],
                  Text(
                    formatRelativeTime(work.createdAt),
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: theme.colorScheme.onSurface
                          .withValues(alpha: 0.4),
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _StatusBadge extends StatelessWidget {
  const _StatusBadge({required this.status});

  final WorkStatus status;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

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
        color = theme.colorScheme.error;
        label = 'Failed';
      case WorkStatus.cancelled:
        color = Colors.orange;
        label = 'Cancelled';
      case WorkStatus.paused:
        color = Colors.amber;
        label = 'Paused';
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.15),
        borderRadius: BorderRadius.circular(6),
      ),
      child: Text(
        label,
        style: theme.textTheme.bodySmall?.copyWith(
          color: color,
          fontWeight: FontWeight.w600,
          fontSize: 11,
        ),
      ),
    );
  }
}

class _PriorityIndicator extends StatelessWidget {
  const _PriorityIndicator({required this.priority});

  final Priority priority;

  @override
  Widget build(BuildContext context) {
    Color color;
    switch (priority) {
      case Priority.urgent:
        color = Colors.red;
      case Priority.high:
        color = Colors.orange;
      case Priority.normal:
        color = Colors.blue;
      case Priority.low:
        color = Colors.grey;
    }

    return Container(
      width: 4,
      height: 24,
      decoration: BoxDecoration(
        color: color,
        borderRadius: BorderRadius.circular(2),
      ),
    );
  }
}
