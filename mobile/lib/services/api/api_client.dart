import 'dart:async';

import 'package:dio/dio.dart';

import '../storage/secure_storage_service.dart';

/// Central HTTP client with auth token injection and 401 refresh logic.
class ApiClient {
  ApiClient({
    required this.storage,
    String? baseUrl,
  }) : dio = Dio(BaseOptions(
          baseUrl: baseUrl ?? '',
          connectTimeout: const Duration(seconds: 10),
          receiveTimeout: const Duration(seconds: 30),
          headers: {'Content-Type': 'application/json'},
        )) {
    dio.interceptors.add(_AuthInterceptor(this));
  }

  final Dio dio;
  final SecureStorageService storage;

  bool _isRefreshing = false;
  final List<_RetryRequest> _pendingRequests = [];

  /// Callback invoked when refresh fails — signals forced logout.
  void Function()? onForceLogout;

  void setBaseUrl(String url) {
    dio.options.baseUrl = url;
  }

  Future<void> _refreshToken() async {
    if (_isRefreshing) return;
    _isRefreshing = true;

    try {
      final refreshToken = await storage.getRefreshToken();
      if (refreshToken == null) throw Exception('No refresh token');

      // Use a fresh Dio to avoid interceptor loop
      final refreshDio = Dio(BaseOptions(
        baseUrl: dio.options.baseUrl,
        headers: {'Content-Type': 'application/json'},
      ));

      final response = await refreshDio.post(
        '/api/auth/refresh',
        data: {'refresh_token': refreshToken},
      );

      final newAccessToken = response.data['access_token'] as String;
      await storage.saveAccessToken(newAccessToken);

      // Retry all pending requests
      for (final pending in _pendingRequests) {
        pending.options.headers['Authorization'] = 'Bearer $newAccessToken';
        pending.completer.complete(dio.fetch(pending.options));
      }
    } catch (_) {
      // Refresh failed — reject all pending and force logout
      for (final pending in _pendingRequests) {
        pending.completer.completeError(
          DioException(
            requestOptions: pending.options,
            message: 'Session expired',
          ),
        );
      }
      await storage.clearTokens();
      onForceLogout?.call();
    } finally {
      _pendingRequests.clear();
      _isRefreshing = false;
    }
  }
}

class _AuthInterceptor extends Interceptor {
  _AuthInterceptor(this._client);

  final ApiClient _client;

  @override
  void onRequest(
    RequestOptions options,
    RequestInterceptorHandler handler,
  ) async {
    final path = options.path;
    const publicPaths = [
      '/api/auth/login',
      '/api/auth/setup',
      '/api/auth/refresh',
      '/api/auth/mode',
      '/api/health',
    ];

    if (!publicPaths.any((p) => path.startsWith(p))) {
      final token = await _client.storage.getAccessToken();
      if (token != null) {
        options.headers['Authorization'] = 'Bearer $token';
      }
    }

    handler.next(options);
  }

  @override
  void onError(DioException err, ErrorInterceptorHandler handler) async {
    if (err.response?.statusCode == 401 &&
        !err.requestOptions.path.contains('/auth/refresh') &&
        !err.requestOptions.path.contains('/auth/login')) {
      final completer = Completer<Response>();
      _client._pendingRequests.add(_RetryRequest(
        options: err.requestOptions,
        completer: completer,
      ));

      await _client._refreshToken();

      try {
        final response = await completer.future;
        handler.resolve(response);
      } catch (e) {
        handler.reject(
          e is DioException
              ? e
              : DioException(
                  requestOptions: err.requestOptions,
                  error: e,
                ),
        );
      }
      return;
    }

    handler.next(err);
  }
}

class _RetryRequest {
  _RetryRequest({required this.options, required this.completer});

  final RequestOptions options;
  final Completer<Response> completer;
}
