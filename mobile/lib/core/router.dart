import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../providers/auth_provider.dart';
import '../screens/auth/biometric_lock_screen.dart';
import '../screens/auth/login_screen.dart';
import '../screens/auth/qr_pair_screen.dart';
import '../screens/chat/chat_list_screen.dart';
import '../screens/chat/chat_screen.dart';
import '../screens/chat/recent_chats_screen.dart';
import '../screens/home/home_screen.dart';
import '../screens/settings/settings_screen.dart';
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
            builder: (context, state) => ChatListScreen(
              botId: state.pathParameters['botId']!,
            ),
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
