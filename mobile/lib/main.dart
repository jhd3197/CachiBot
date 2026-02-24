import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:receive_sharing_intent/receive_sharing_intent.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'core/router.dart';
import 'providers/auth_provider.dart';
import 'providers/theme_provider.dart';
import 'services/notifications/notification_service.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final prefs = await SharedPreferences.getInstance();

  // Initialize notification service early
  await notificationService.init();

  runApp(
    ProviderScope(
      overrides: [
        sharedPreferencesProvider.overrideWithValue(prefs),
      ],
      child: const CachiBotApp(),
    ),
  );
}

class CachiBotApp extends ConsumerStatefulWidget {
  const CachiBotApp({super.key});

  @override
  ConsumerState<CachiBotApp> createState() => _CachiBotAppState();
}

class _CachiBotAppState extends ConsumerState<CachiBotApp> {
  StreamSubscription<List<SharedMediaFile>>? _shareSub;
  String? _pendingSharedText;

  @override
  void initState() {
    super.initState();
    // Restore session from saved tokens on startup
    Future.microtask(() {
      ref.read(authProvider.notifier).restoreSession();
    });

    // Handle shared content from other apps
    _initShareIntents();
  }

  void _initShareIntents() {
    // Handle share when app is already running
    _shareSub = ReceiveSharingIntent.instance.getMediaStream().listen(
      (files) => _handleSharedFiles(files),
      onError: (_) {},
    );

    // Handle share that launched the app
    ReceiveSharingIntent.instance.getInitialMedia().then((files) {
      if (files.isNotEmpty) {
        _handleSharedFiles(files);
        ReceiveSharingIntent.instance.reset();
      }
    });
  }

  void _handleSharedFiles(List<SharedMediaFile> files) {
    if (files.isEmpty) return;

    final router = ref.read(routerProvider);

    for (final file in files) {
      if (file.type == SharedMediaType.text ||
          file.type == SharedMediaType.url) {
        // Shared text: navigate to recent chats with text pre-filled
        // User can pick a bot/chat from there
        _pendingSharedText = file.path;
        router.go('/chats');
        break;
      } else if (file.type == SharedMediaType.file) {
        // Shared file: could be a document to upload
        // For now, just navigate home — the user picks a bot
        router.go('/');
        break;
      }
    }
  }

  @override
  void dispose() {
    _shareSub?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final themeMode = ref.watch(themeModeProvider);
    final lightTheme = ref.watch(lightThemeProvider);
    final darkTheme = ref.watch(darkThemeProvider);
    final router = ref.watch(routerProvider);

    // Pass router to notification service for tap navigation
    notificationService.init(router: router);

    return MaterialApp.router(
      title: 'CachiBot',
      debugShowCheckedModeBanner: false,
      theme: lightTheme,
      darkTheme: darkTheme,
      themeMode: themeMode,
      routerConfig: router,
    );
  }
}
