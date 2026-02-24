import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:shared_preferences/shared_preferences.dart';

class SecureStorageService {
  SecureStorageService(this._prefs);

  final SharedPreferences _prefs;

  static const _storage = FlutterSecureStorage(
    aOptions: AndroidOptions(encryptedSharedPreferences: true),
  );

  static const _keyAccessToken = 'access_token';
  static const _keyRefreshToken = 'refresh_token';
  static const _keyServerUrl = 'server_url';

  // --- Token management ---

  Future<void> saveTokens({
    required String accessToken,
    required String refreshToken,
  }) async {
    await Future.wait([
      _storage.write(key: _keyAccessToken, value: accessToken),
      _storage.write(key: _keyRefreshToken, value: refreshToken),
    ]);
  }

  Future<String?> getAccessToken() =>
      _storage.read(key: _keyAccessToken);

  Future<String?> getRefreshToken() =>
      _storage.read(key: _keyRefreshToken);

  Future<void> saveAccessToken(String token) =>
      _storage.write(key: _keyAccessToken, value: token);

  Future<void> clearTokens() async {
    await Future.wait([
      _storage.delete(key: _keyAccessToken),
      _storage.delete(key: _keyRefreshToken),
    ]);
  }

  // --- Server URL (not secret, stored in SharedPreferences) ---

  Future<void> saveServerUrl(String url) =>
      _prefs.setString(_keyServerUrl, url);

  String? getServerUrl() => _prefs.getString(_keyServerUrl);
}
