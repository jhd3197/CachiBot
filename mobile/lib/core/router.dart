import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../providers/auth_provider.dart';
import '../screens/auth/biometric_lock_screen.dart';
import '../screens/auth/login_screen.dart';
import '../screens/auth/qr_pair_screen.dart';
import '../screens/bot/bot_detail_screen.dart';
import '../screens/chat/chat_screen.dart';
import '../screens/chat/recent_chats_screen.dart';
import '../screens/home/home_screen.dart';
import '../screens/knowledge/knowledge_search_screen.dart';
import '../screens/knowledge/note_editor_screen.dart';
import '../screens/settings/settings_screen.dart';
import '../screens/work/todos_screen.dart';
import '../screens/work/work_detail_screen.dart';
import '../widgets/common/app_shell.dart';

final _rootNavigatorKey = GlobalKey<NavigatorState>();
final _shellNavigatorKey = GlobalKey<NavigatorState>();

final routerProvider = Provider<GoRouter>((ref) {
  final authState = ref.watch(authProvider);

  return GoRouter(
    navigatorKey: _rootNavigatorKey,
    initialLocation: '/',
    redirect: (context, state) {
      final isAuthenticated = authState.isAuthenticated;
      final location = state.uri.toString();
      final isOnLogin = location == '/login';
      final isOnQrPair = location == '/qr-pair';
      final isOnBiometric = location == '/biometric-lock';

      // Allow unauthenticated access to login and QR pairing
      if (!isAuthenticated && !isOnLogin && !isOnQrPair) return '/login';

      // Biometric lock redirect
      if (isAuthenticated && authState.requiresBiometric && !isOnBiometric) {
        return '/biometric-lock';
      }

      if (isAuthenticated && isOnLogin) return '/';
      return null;
    },
    routes: [
      GoRoute(
        path: '/login',
        builder: (context, state) => const LoginScreen(),
      ),
      GoRoute(
        path: '/qr-pair',
        builder: (context, state) => const QrPairScreen(),
      ),
      GoRoute(
        path: '/biometric-lock',
        builder: (context, state) => const BiometricLockScreen(),
      ),
      ShellRoute(
        navigatorKey: _shellNavigatorKey,
        builder: (context, state, child) => AppShell(child: child),
        routes: [
          GoRoute(
            path: '/',
            builder: (context, state) => const HomeScreen(),
          ),
          GoRoute(
            path: '/chats',
            builder: (context, state) => const RecentChatsScreen(),
          ),
          GoRoute(
            path: '/bot/:botId',
            builder: (context, state) => BotDetailScreen(
              botId: state.pathParameters['botId']!,
            ),
            routes: [
              // Knowledge routes
              GoRoute(
                path: 'knowledge/new',
                parentNavigatorKey: _rootNavigatorKey,
                builder: (context, state) => NoteEditorScreen(
                  botId: state.pathParameters['botId']!,
                ),
              ),
              GoRoute(
                path: 'knowledge/search',
                parentNavigatorKey: _rootNavigatorKey,
                builder: (context, state) => KnowledgeSearchScreen(
                  botId: state.pathParameters['botId']!,
                ),
              ),
              GoRoute(
                path: 'knowledge/:noteId',
                parentNavigatorKey: _rootNavigatorKey,
                builder: (context, state) => NoteEditorScreen(
                  botId: state.pathParameters['botId']!,
                  noteId: state.pathParameters['noteId'],
                ),
              ),
              // Work routes
              GoRoute(
                path: 'work/:workId',
                parentNavigatorKey: _rootNavigatorKey,
                builder: (context, state) => WorkDetailScreen(
                  botId: state.pathParameters['botId']!,
                  workId: state.pathParameters['workId']!,
                ),
              ),
              // Todos route
              GoRoute(
                path: 'todos',
                parentNavigatorKey: _rootNavigatorKey,
                builder: (context, state) => TodosScreen(
                  botId: state.pathParameters['botId']!,
                ),
              ),
            ],
          ),
          GoRoute(
            path: '/chat/:botId',
            builder: (context, state) => ChatScreen(
              botId: state.pathParameters['botId']!,
            ),
            routes: [
              GoRoute(
                path: ':chatId',
                builder: (context, state) => ChatScreen(
                  botId: state.pathParameters['botId']!,
                  chatId: state.pathParameters['chatId'],
                ),
              ),
            ],
          ),
          GoRoute(
            path: '/settings',
            builder: (context, state) => const SettingsScreen(),
          ),
        ],
      ),
    ],
  );
});
