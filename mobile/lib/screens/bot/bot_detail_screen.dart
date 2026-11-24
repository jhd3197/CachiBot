import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../models/bot.dart';
import '../../providers/bots_provider.dart';
import '../../providers/computer_provider.dart';
import '../chat/chat_list_screen.dart';
import '../knowledge/knowledge_list_screen.dart';
import '../work/work_list_screen.dart';

class BotDetailScreen extends ConsumerStatefulWidget {
  const BotDetailScreen({required this.botId, super.key});

  final String botId;

  @override
  ConsumerState<BotDetailScreen> createState() => _BotDetailScreenState();
}

class _BotDetailScreenState extends ConsumerState<BotDetailScreen>
    with SingleTickerProviderStateMixin {
  late final TabController _tabController;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 3, vsync: this);
    // The Docker probe decides whether the Computer entry may appear at all.
    Future.microtask(() => ref.read(computerProvider.notifier).fetchStatus());
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  Bot? _findBot(BotsState state) {
    return state.bots.where((b) => b.id == widget.botId).firstOrNull;
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final botsState = ref.watch(botsProvider);
    final bot = _findBot(botsState);
    final computerAvailable =
        ref.watch(computerProvider).status?.available == true;

    Color? botColor;
    if (bot?.color != null && bot!.color!.isNotEmpty) {
      try {
        final hex = bot.color!.replaceFirst('#', '');
        botColor = Color(int.parse('FF$hex', radix: 16));
      } catch (_) {}
    }

    return Scaffold(
      appBar: AppBar(
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () => context.go('/'),
        ),
        title: Row(
          children: [
            if (bot != null) ...[
              Container(
                width: 32,
                height: 32,
                decoration: BoxDecoration(
                  color: (botColor ?? theme.colorScheme.primary)
                      .withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Center(
                  child: bot.icon != null && bot.icon!.isNotEmpty
                      ? Text(bot.icon!, style: const TextStyle(fontSize: 18))
                      : Icon(
                          Icons.smart_toy,
                          size: 18,
                          color: botColor ?? theme.colorScheme.primary,
                        ),
                ),
              ),
              const SizedBox(width: 10),
            ],
            Expanded(
              child: Text(
                bot?.name ?? 'Bot',
                overflow: TextOverflow.ellipsis,
              ),
            ),
          ],
        ),
        actions: [
          // The bot's computer — only while the Docker probe says available;
          // no dead button when Docker is off.
          if (computerAvailable)
            IconButton(
              icon: const Icon(Icons.desktop_windows_outlined),
              tooltip: 'Computer',
              onPressed: () => context.push('/bot/${widget.botId}/computer'),
            ),
        ],
        bottom: TabBar(
          controller: _tabController,
          tabs: const [
            Tab(text: 'Chats', icon: Icon(Icons.chat_bubble_outline, size: 20)),
            Tab(text: 'Knowledge', icon: Icon(Icons.auto_stories_outlined, size: 20)),
            Tab(text: 'Work', icon: Icon(Icons.work_outline, size: 20)),
          ],
        ),
      ),
      body: TabBarView(
        controller: _tabController,
        children: [
          ChatListTab(botId: widget.botId),
          KnowledgeListScreen(botId: widget.botId),
          WorkListScreen(botId: widget.botId),
        ],
      ),
    );
  }
}

/// Chat list embedded as a tab (no Scaffold/AppBar).
class ChatListTab extends ConsumerStatefulWidget {
  const ChatListTab({required this.botId, super.key});

  final String botId;

  @override
  ConsumerState<ChatListTab> createState() => _ChatListTabState();
}

class _ChatListTabState extends ConsumerState<ChatListTab>
    with AutomaticKeepAliveClientMixin {
  @override
  bool get wantKeepAlive => true;

  @override
  Widget build(BuildContext context) {
    super.build(context);
    return ChatListContent(botId: widget.botId);
  }
}
