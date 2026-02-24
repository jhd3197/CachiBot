import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/user.dart';
import 'service_providers.dart';

class AuthState {
  const AuthState({
    this.user,
    this.isAuthenticated = false,
    this.isLoading = false,
    this.setupRequired,
    this.errorMessage,
  });

  final User? user;
  final bool isAuthenticated;
  final bool isLoading;
  final bool? setupRequired;
  final String? errorMessage;

  AuthState copyWith({
    User? user,
    bool? isAuthenticated,
    bool? isLoading,
    bool? setupRequired,
    String? errorMessage,
    bool clearError = false,
    bool clearUser = false,
    bool clearSetupRequired = false,
  }) {
    return AuthState(
      user: clearUser ? null : (user ?? this.user),
      isAuthenticated: isAuthenticated ?? this.isAuthenticated,
      isLoading: isLoading ?? this.isLoading,
      setupRequired:
          clearSetupRequired ? null : (setupRequired ?? this.setupRequired),
      errorMessage: clearError ? null : (errorMessage ?? this.errorMessage),
    );
  }
}

class AuthNotifier extends StateNotifier<AuthState> {
  AuthNotifier(this._ref) : super(const AuthState());

  final Ref _ref;

  /// Attempt login: set server URL, hit health, then login.
  Future<void> login(
    String identifier,
    String password,
    String serverUrl,
  ) async {
    state = state.copyWith(isLoading: true, clearError: true);

    try {
      final storage = _ref.read(secureStorageProvider);
      final client = _ref.read(apiClientProvider);

      // Persist and apply server URL
      await storage.saveServerUrl(serverUrl);
      client.setBaseUrl(serverUrl);

      final authService = _ref.read(authServiceProvider);
      final result = await authService.login(
        identifier: identifier,
        password: password,
      );

      await storage.saveTokens(
        accessToken: result.accessToken,
        refreshToken: result.refreshToken,
      );

      state = AuthState(
        user: result.user,
        isAuthenticated: true,
      );
    } on DioException catch (e) {
      final message = _extractError(e);
      state = state.copyWith(isLoading: false, errorMessage: message);
    } catch (e) {
      state = state.copyWith(
        isLoading: false,
        errorMessage: e.toString(),
      );
    }
  }

  /// Initial setup (first-time admin creation).
  Future<void> setup(
    String email,
    String username,
    String password,
    String serverUrl,
  ) async {
    state = state.copyWith(isLoading: true, clearError: true);

    try {
      final storage = _ref.read(secureStorageProvider);
      final client = _ref.read(apiClientProvider);

      await storage.saveServerUrl(serverUrl);
      client.setBaseUrl(serverUrl);

      final authService = _ref.read(authServiceProvider);
      final result = await authService.setup(
        email: email,
        username: username,
        password: password,
      );

      await storage.saveTokens(
        accessToken: result.accessToken,
        refreshToken: result.refreshToken,
      );

      state = AuthState(
        user: result.user,
        isAuthenticated: true,
      );
    } on DioException catch (e) {
      final message = _extractError(e);
      state = state.copyWith(isLoading: false, errorMessage: message);
    } catch (e) {
      state = state.copyWith(
        isLoading: false,
        errorMessage: e.toString(),
      );
    }
  }

  /// Check if server needs initial setup.
  Future<void> checkSetupRequired(String serverUrl) async {
    state = state.copyWith(isLoading: true, clearError: true);

    try {
      final client = _ref.read(apiClientProvider);
      client.setBaseUrl(serverUrl);

      final authService = _ref.read(authServiceProvider);
      final result = await authService.checkSetupRequired();

      state = state.copyWith(
        isLoading: false,
        setupRequired: result.setupRequired,
      );
    } on DioException catch (e) {
      final message = _extractError(e);
      state = state.copyWith(isLoading: false, errorMessage: message);
    } catch (e) {
      state = state.copyWith(
        isLoading: false,
        errorMessage: e.toString(),
      );
    }
  }

  /// Restore session from stored tokens.
  Future<void> restoreSession() async {
    final storage = _ref.read(secureStorageProvider);
    final token = await storage.getAccessToken();
    final serverUrl = storage.getServerUrl();

    if (token == null || serverUrl == null) return;

    state = state.copyWith(isLoading: true);

    try {
      final client = _ref.read(apiClientProvider);
      client.setBaseUrl(serverUrl);

      final authService = _ref.read(authServiceProvider);
      final user = await authService.getCurrentUser();

      state = AuthState(
        user: user,
        isAuthenticated: true,
      );
    } catch (_) {
      // Token invalid or server unreachable — stay logged out
      await storage.clearTokens();
      state = const AuthState();
    }
  }

  Future<void> logout() async {
    final storage = _ref.read(secureStorageProvider);
    await storage.clearTokens();
    state = const AuthState();
  }

  void clearError() {
    state = state.copyWith(clearError: true);
  }

  static String _extractError(DioException e) {
    final data = e.response?.data;
    if (data is Map<String, dynamic> && data.containsKey('detail')) {
      final detail = data['detail'];
      if (detail is String) return detail;
      if (detail is Map) return detail['message']?.toString() ?? 'Request failed';
    }
    if (e.response?.statusCode == 429) return 'Too many attempts. Please wait.';
    if (e.type == DioExceptionType.connectionTimeout ||
        e.type == DioExceptionType.connectionError) {
      return 'Cannot reach server. Check the URL and your connection.';
    }
    return e.message ?? 'An unexpected error occurred';
  }
}

final authProvider = StateNotifierProvider<AuthNotifier, AuthState>((ref) {
  final notifier = AuthNotifier(ref);

  // Wire up force-logout from ApiClient
  final client = ref.watch(apiClientProvider);
  client.onForceLogout = () => notifier.logout();

  return notifier;
});
