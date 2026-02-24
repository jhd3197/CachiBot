import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/utils/time_utils.dart';
import '../../models/work.dart';
import '../../providers/todos_provider.dart';

class TodosScreen extends ConsumerStatefulWidget {
  const TodosScreen({required this.botId, super.key});

  final String botId;

  @override
  ConsumerState<TodosScreen> createState() => _TodosScreenState();
}

class _TodosScreenState extends ConsumerState<TodosScreen> {
  @override
  void initState() {
    super.initState();
    Future.microtask(
      () => ref.read(todosProvider.notifier).loadTodos(widget.botId),
    );
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final state = ref.watch(todosProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Todos'),
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: () => _showCreateDialog(context),
        child: const Icon(Icons.add),
      ),
      body: Column(
        children: [
          // Filter chips
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
            child: Row(
              children: TodoFilter.values.map((filter) {
                final isSelected = state.filter == filter;
                return Padding(
                  padding: const EdgeInsets.only(right: 8),
                  child: FilterChip(
                    label: Text(_filterLabel(filter)),
                    selected: isSelected,
                    onSelected: (_) =>
                        ref.read(todosProvider.notifier).setFilter(filter),
                  ),
                );
              }).toList(),
            ),
          ),

          // Content
          Expanded(child: _buildContent(theme, state)),
        ],
      ),
    );
  }

  String _filterLabel(TodoFilter filter) {
    switch (filter) {
      case TodoFilter.open:
        return 'Open';
      case TodoFilter.done:
        return 'Done';
      case TodoFilter.all:
        return 'All';
    }
  }

  Widget _buildContent(ThemeData theme, TodosState state) {
    if (state.isLoading && state.todos.isEmpty) {
      return const Center(child: CircularProgressIndicator());
    }

    if (state.errorMessage != null && state.todos.isEmpty) {
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
                    ref.read(todosProvider.notifier).loadTodos(widget.botId),
                icon: const Icon(Icons.refresh),
                label: const Text('Retry'),
              ),
            ],
          ),
        ),
      );
    }

    final items = state.filteredTodos;

    if (items.isEmpty) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.checklist,
                size: 64,
                color: theme.colorScheme.onSurface.withValues(alpha: 0.3)),
            const SizedBox(height: 16),
            Text(
              'No todos',
              style: theme.textTheme.bodyLarge?.copyWith(
                color: theme.colorScheme.onSurface.withValues(alpha: 0.5),
              ),
            ),
          ],
        ),
      );
    }

    return RefreshIndicator(
      onRefresh: () =>
          ref.read(todosProvider.notifier).loadTodos(widget.botId),
      child: ListView.builder(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
        itemCount: items.length,
        itemBuilder: (context, index) {
          final todo = items[index];
          return _TodoCard(
            todo: todo,
            onToggle: () {
              if (todo.isOpen) {
                ref
                    .read(todosProvider.notifier)
                    .completeTodo(widget.botId, todo.id);
              }
            },
            onDismiss: () => ref
                .read(todosProvider.notifier)
                .dismissTodo(widget.botId, todo.id),
            onDelete: () => _confirmDelete(todo),
            onLongPress: () => _showContextMenu(todo),
          );
        },
      ),
    );
  }

  void _showContextMenu(Todo todo) {
    showModalBottomSheet(
      context: context,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (ctx) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (todo.isOpen)
              ListTile(
                leading: const Icon(Icons.check_circle_outline),
                title: const Text('Mark Done'),
                onTap: () {
                  Navigator.of(ctx).pop();
                  ref
                      .read(todosProvider.notifier)
                      .completeTodo(widget.botId, todo.id);
                },
              ),
            if (todo.isOpen)
              ListTile(
                leading: const Icon(Icons.do_not_disturb),
                title: const Text('Dismiss'),
                onTap: () {
                  Navigator.of(ctx).pop();
                  ref
                      .read(todosProvider.notifier)
                      .dismissTodo(widget.botId, todo.id);
                },
              ),
            if (todo.isOpen)
              ListTile(
                leading: const Icon(Icons.work_outline),
                title: const Text('Convert to Work'),
                onTap: () {
                  Navigator.of(ctx).pop();
                  ref.read(todosProvider.notifier).convertToWork(
                        widget.botId,
                        todo.id,
                        workTitle: todo.title,
                      );
                },
              ),
            ListTile(
              leading: Icon(Icons.delete_outline,
                  color: Theme.of(ctx).colorScheme.error),
              title: Text('Delete',
                  style: TextStyle(color: Theme.of(ctx).colorScheme.error)),
              onTap: () {
                Navigator.of(ctx).pop();
                _confirmDelete(todo);
              },
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _confirmDelete(Todo todo) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Delete Todo'),
        content: Text('Delete "${todo.title}"? This cannot be undone.'),
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
      ref.read(todosProvider.notifier).deleteTodo(widget.botId, todo.id);
    }
  }

  Future<void> _showCreateDialog(BuildContext context) async {
    final titleController = TextEditingController();
    final notesController = TextEditingController();

    final result = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('New Todo'),
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
              controller: notesController,
              decoration: const InputDecoration(
                labelText: 'Notes (optional)',
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
            child: const Text('Create'),
          ),
        ],
      ),
    );

    if (result == true && mounted) {
      final title = titleController.text.trim();
      if (title.isNotEmpty) {
        final notes = notesController.text.trim();
        ref.read(todosProvider.notifier).createTodo(
              widget.botId,
              title: title,
              notes: notes.isNotEmpty ? notes : null,
            );
      }
    }

    titleController.dispose();
    notesController.dispose();
  }
}

class _TodoCard extends StatelessWidget {
  const _TodoCard({
    required this.todo,
    required this.onToggle,
    required this.onDismiss,
    required this.onDelete,
    required this.onLongPress,
  });

  final Todo todo;
  final VoidCallback onToggle;
  final VoidCallback onDismiss;
  final VoidCallback onDelete;
  final VoidCallback onLongPress;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    Color priorityColor;
    switch (todo.priority) {
      case Priority.urgent:
        priorityColor = Colors.red;
      case Priority.high:
        priorityColor = Colors.orange;
      case Priority.normal:
        priorityColor = theme.colorScheme.primary;
      case Priority.low:
        priorityColor = Colors.grey;
    }

    return Dismissible(
      key: ValueKey(todo.id),
      background: Container(
        alignment: Alignment.centerLeft,
        padding: const EdgeInsets.only(left: 20),
        decoration: BoxDecoration(
          color: Colors.green,
          borderRadius: BorderRadius.circular(12),
        ),
        child: const Icon(Icons.check, color: Colors.white),
      ),
      secondaryBackground: Container(
        alignment: Alignment.centerRight,
        padding: const EdgeInsets.only(right: 20),
        decoration: BoxDecoration(
          color: theme.colorScheme.error,
          borderRadius: BorderRadius.circular(12),
        ),
        child: Icon(Icons.delete, color: theme.colorScheme.onError),
      ),
      confirmDismiss: (direction) async {
        if (direction == DismissDirection.startToEnd) {
          onToggle();
          return false;
        } else {
          onDelete();
          return false;
        }
      },
      child: Card(
        margin: const EdgeInsets.only(bottom: 6),
        child: ListTile(
          dense: true,
          leading: Container(
            width: 4,
            height: 32,
            decoration: BoxDecoration(
              color: priorityColor,
              borderRadius: BorderRadius.circular(2),
            ),
          ),
          title: Row(
            children: [
              Checkbox(
                value: todo.isDone,
                onChanged: todo.isOpen ? (_) => onToggle() : null,
                visualDensity: VisualDensity.compact,
              ),
              Expanded(
                child: Text(
                  todo.title,
                  style: theme.textTheme.bodyMedium?.copyWith(
                    decoration:
                        todo.isDone ? TextDecoration.lineThrough : null,
                    color: todo.isDone
                        ? theme.colorScheme.onSurface.withValues(alpha: 0.5)
                        : null,
                  ),
                ),
              ),
            ],
          ),
          subtitle: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              if (todo.notes != null)
                Padding(
                  padding: const EdgeInsets.only(left: 40),
                  child: Text(
                    todo.notes!,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: theme.colorScheme.onSurface
                          .withValues(alpha: 0.6),
                    ),
                  ),
                ),
              Padding(
                padding: const EdgeInsets.only(left: 40, top: 2),
                child: Row(
                  children: [
                    Text(
                      formatRelativeTime(todo.createdAt),
                      style: theme.textTheme.bodySmall?.copyWith(
                        fontSize: 10,
                        color: theme.colorScheme.onSurface
                            .withValues(alpha: 0.4),
                      ),
                    ),
                    if (todo.remindAt != null) ...[
                      const SizedBox(width: 8),
                      const Icon(Icons.alarm, size: 12, color: Colors.orange),
                      const SizedBox(width: 2),
                      Text(
                        formatRelativeTime(todo.remindAt!),
                        style: theme.textTheme.bodySmall?.copyWith(
                          fontSize: 10,
                          color: Colors.orange,
                        ),
                      ),
                    ],
                  ],
                ),
              ),
            ],
          ),
          onLongPress: onLongPress,
        ),
      ),
    );
  }
}
