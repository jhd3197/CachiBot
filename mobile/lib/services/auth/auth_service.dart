import 'dart:convert';

import 'package:crypto/crypto.dart';

import '../../models/auth.dart';
import '../../models/user.dart';
import '../api/api_client.dart';

class AuthService {
  AuthService(this._client);

  final ApiClient _client;

  /// SHA-256 hex-digest of the password, matching the web frontend.
  static String hashPassword(String password) {
    final bytes = utf8.encode(password);
    final digest = sha256.convert(bytes);
    return digest.toString();
  }

  Future<AuthModeResponse> getAuthMode() async {
    final response = await _client.dio.get('/api/auth/mode');
    return AuthModeResponse.fromJson(response.data as Map<String, dynamic>);
  }

  Future<SetupStatusResponse> checkSetupRequired() async {
    final response = await _client.dio.get('/api/auth/setup-required');
    return SetupStatusResponse.fromJson(response.data as Map<String, dynamic>);
  }

  Future<LoginResponse> login({
    required String identifier,
    required String password,
  }) async {
    final hashed = hashPassword(password);
    final response = await _client.dio.post(
      '/api/auth/login',
      data: LoginRequest(identifier: identifier, password: hashed).toJson(),
    );
    return LoginResponse.fromJson(response.data as Map<String, dynamic>);
  }

  Future<LoginResponse> setup({
    required String email,
    required String username,
    required String password,
  }) async {
    final hashed = hashPassword(password);
    final response = await _client.dio.post(
      '/api/auth/setup',
      data: SetupRequest(
        email: email,
        username: username,
        password: hashed,
      ).toJson(),
    );
    return LoginResponse.fromJson(response.data as Map<String, dynamic>);
  }

  Future<RefreshResponse> refreshToken(String refreshToken) async {
    final response = await _client.dio.post(
      '/api/auth/refresh',
      data: {'refresh_token': refreshToken},
    );
    return RefreshResponse.fromJson(response.data as Map<String, dynamic>);
  }

  Future<User> getCurrentUser() async {
    final response = await _client.dio.get('/api/auth/me');
    return User.fromJson(response.data as Map<String, dynamic>);
  }
}
