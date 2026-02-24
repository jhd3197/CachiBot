import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../services/api/api_client.dart';
import '../services/api/bot_service.dart';
import '../services/auth/auth_service.dart';
import '../services/storage/secure_storage_service.dart';
import '../services/websocket/websocket_service.dart';
import 'theme_provider.dart';

final secureStorageProvider = Provider<SecureStorageService>((ref) {
  final prefs = ref.watch(sharedPreferencesProvider);
  return SecureStorageService(prefs);
});

final apiClientProvider = Provider<ApiClient>((ref) {
  final storage = ref.watch(secureStorageProvider);
  final serverUrl = storage.getServerUrl();
  return ApiClient(storage: storage, baseUrl: serverUrl);
});

final authServiceProvider = Provider<AuthService>((ref) {
  final client = ref.watch(apiClientProvider);
  return AuthService(client);
});

final botServiceProvider = Provider<BotService>((ref) {
  final client = ref.watch(apiClientProvider);
  return BotService(client);
});

final wsServiceProvider = Provider<WebSocketService>((ref) {
  final client = ref.watch(apiClientProvider);
  final storage = ref.watch(secureStorageProvider);

  final service = WebSocketService(
    baseUrl: client.dio.options.baseUrl,
    tokenProvider: () => storage.getAccessToken(),
  );

  ref.onDispose(() => service.dispose());
  return service;
});

/// Exposes the WebSocket connection state as a provider.
final wsConnectionProvider = StateProvider<bool>((ref) {
  final ws = ref.watch(wsServiceProvider);
  final isConnected = ws.isConnected;

  // Listen for connection state changes
  late final StreamSubscription<bool> sub;
  sub = ws.connectionState.listen((connected) {
    ref.controller.state = connected;
  });
  ref.onDispose(() => sub.cancel());

  return isConnected;
});
