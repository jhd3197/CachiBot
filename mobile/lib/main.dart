import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'core/router.dart';
import 'providers/auth_provider.dart';
import 'providers/theme_provider.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final prefs = await SharedPreferences.getInstance();

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
  @override
  void initState() {
    super.initState();
    // Restore session from saved tokens on startup
    Future.microtask(() {
      ref.read(authProvider.notifier).restoreSession();
    });
  }

  @override
  Widget build(BuildContext context) {
    final themeMode = ref.watch(themeModeProvider);
    final lightTheme = ref.watch(lightThemeProvider);
    final darkTheme = ref.watch(darkThemeProvider);
    final router = ref.watch(routerProvider);

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
