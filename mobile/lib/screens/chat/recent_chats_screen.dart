import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/utils/time_utils.dart';
import '../../models/bot.dart';
import '../../models/chat.dart';
import '../../providers/bots_provider.dart';
import '../../providers/service_providers.dart';

/// Entry for a chat combined with its parent bot info.
class _RecentChatEntry {
  _RecentChatEntry({required this.chat, required this.bot});
  final Chat chat;
  final Bot bot;
}

/// Shows all recent chats across every bot, sorted by most recent.
class RecentChatsScreen extends ConsumerStatefulWidget {
  const RecentChatsScreen({super.key});

  @override
  ConsumerState<RecentChatsScreen> createState() => _RecentChatsScreenState();
}

class _RecentChatsScreenState extends ConsumerState<RecentChatsScreen> {
  List<_RecentChatEntry> _entries = [];
  bool _isLoading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadAll();
  }

  Future<void> _loadAll() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });

    try {
      final botService = ref.read(botServiceProvider);
      final bots = await botService.listBots();

      final entries = <_RecentChatEntry>[];
      for (final bot in bots) {
        try {
          final chats = await botService.listChats(bot.id);
          for (final chat in chats) {
            entries.add(_RecentChatEntry(chat: chat, bot: bot));
          }
        } catch (_) {
          // Skip bots that fail to load chats
        }
      }

      entries.sort((a, b) => b.chat.updatedAt.compareTo(a.chat.updatedAt));

      if (mounted) {
        setState(() {
          _entries = entries;
          _isLoading = false;
        });
      }
    } catch (e) {
      // Try fallback from cached data
      try {
        final dao = await ref.read(chatDaoProvider.future);
        final cached = await dao.getAllCachedChats();
        final botsState = ref.read(botsProvider);

        final entries = <_RecentChatEntry>[];
        for (final chat in cached) {
          final bot = botsState.bots
              .where((b) => b.id == chat.botId)
              .firstOrNull;
          if (bot != null) {
            entries.add(_RecentChatEntry(chat: chat, bot: bot));
          }
        }

        if (mounted) {
          setState(() {
            _entries = entries;
            _isLoading = false;
          });
        }
      } catch (_) {
        if (mounted) {
          setState(() {
            _isLoading = false;
            _error = 'Failed to load recent chats';
          });
        }
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Recent Chats'),
      ),
      body: RefreshIndicator(
        onRefresh: _loadAll,
        child: _isLoading
            ? const Center(child: CircularProgressIndicator())
            : _error != null
                ? _ErrorView(
                    message: _error!,
                    onRetry: _loadAll,
                    theme: theme,
                  )
                : _entries.isEmpty
                    ? _EmptyView(theme: theme)
                    : ListView.builder(
                        padding: const EdgeInsets.symmetric(vertical: 8),
                        itemCount: _entries.length,
                        itemBuilder: (context, index) {
                          final entry = _entries[index];
                          return _ChatTile(
                            entry: entry,
                            onTap: () {
                              context.go(
                                '/chat/${entry.bot.id}/${entry.chat.id}',
                              );
                            },
                          );
                        },
                      ),
      ),
    );
  }
}

class _ChatTile extends StatelessWidget {
  const _ChatTile({required this.entry, required this.onTap});

  final _RecentChatEntry entry;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final bot = entry.bot;
    final chat = entry.chat;

    Color? botColor;
    if (bot.color != null && bot.color!.isNotEmpty) {
      try {
        final hex = bot.color!.replaceFirst('#', '');
        botColor = Color(int.parse('FF$hex', radix: 16));
      } catch (_) {}
    }

    return ListTile(
      leading: CircleAvatar(
        backgroundColor:
            botColor?.withValues(alpha: 0.15) ??
            theme.colorScheme.primaryContainer,
        child: Text(
          bot.icon ?? bot.name.substring(0, 1).toUpperCase(),
          style: TextStyle(
            fontSize: bot.icon != null ? 20 : 16,
            color: botColor ?? theme.colorScheme.primary,
            fontWeight: FontWeight.w600,
          ),
        ),
      ),
      title: Text(
        chat.title,
        maxLines: 1,
        overflow: TextOverflow.ellipsis,
      ),
      subtitle: Text(
        '${bot.name}  •  ${formatRelativeTime(chat.updatedAt)}',
        maxLines: 1,
        overflow: TextOverflow.ellipsis,
        style: theme.textTheme.bodySmall?.copyWith(
          color: theme.colorScheme.onSurface.withValues(alpha: 0.6),
        ),
      ),
      onTap: onTap,
    );
  }
}

class _EmptyView extends StatelessWidget {
  const _EmptyView({required this.theme});
  final ThemeData theme;

  @override
  Widget build(BuildContext context) {
    return ListView(
      children: [
        const SizedBox(height: 120),
        Center(
          child: Column(
            children: [
              Icon(
                Icons.chat_bubble_outline,
                size: 64,
                color: theme.colorScheme.onSurface.withValues(alpha: 0.3),
              ),
              const SizedBox(height: 16),
              Text(
                'No recent chats',
                style: theme.textTheme.bodyLarge?.copyWith(
                  color: theme.colorScheme.onSurface.withValues(alpha: 0.5),
                ),
              ),
              const SizedBox(height: 8),
              Text(
                'Start a conversation from the Home tab',
                style: theme.textTheme.bodySmall?.copyWith(
                  color: theme.colorScheme.onSurface.withValues(alpha: 0.4),
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }
}

class _ErrorView extends StatelessWidget {
  const _ErrorView({
    required this.message,
    required this.onRetry,
    required this.theme,
  });

  final String message;
  final VoidCallback onRetry;
  final ThemeData theme;

  @override
  Widget build(BuildContext context) {
    return ListView(
      children: [
        const SizedBox(height: 120),
        Center(
          child: Column(
            children: [
              Icon(
                Icons.error_outline,
                size: 48,
                color: theme.colorScheme.error,
              ),
              const SizedBox(height: 16),
              Text(message),
              const SizedBox(height: 16),
              OutlinedButton(
                onPressed: onRetry,
                child: const Text('Retry'),
              ),
            ],
          ),
        ),
      ],
    );
  }
}
