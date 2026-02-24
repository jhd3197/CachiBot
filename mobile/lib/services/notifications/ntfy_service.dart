import 'dart:async';
import 'dart:convert';

import 'package:dio/dio.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'notification_service.dart';

/// Self-hosted ntfy integration for push notifications when the WebSocket
/// connection is not available (app killed / no background service).
///
/// Subscribes to a user-specific ntfy topic via Server-Sent Events (SSE)
/// and delivers local notifications.
class NtfyService {
  NtfyService._();

  static final NtfyService instance = NtfyService._();

  static const _serverUrlKey = 'ntfy_server_url';
  static const _topicKey = 'ntfy_topic';

  final Dio _dio = Dio();
  StreamSubscription<dynamic>? _sseSub;
  bool _isListening = false;
  int _notificationId = 2000;

  bool get isListening => _isListening;

  /// Start listening to the configured ntfy topic.
  Future<bool> start({String? userId}) async {
    if (_isListening) return true;

    final prefs = await SharedPreferences.getInstance();
    final serverUrl = prefs.getString(_serverUrlKey);
    if (serverUrl == null || serverUrl.isEmpty) return false;

    final topic = prefs.getString(_topicKey) ?? 'cachibot-${userId ?? 'default'}';

    try {
      final response = await _dio.get<ResponseBody>(
        '$serverUrl/$topic/sse',
        options: Options(
          responseType: ResponseType.stream,
          headers: {'Accept': 'text/event-stream'},
        ),
      );

      _isListening = true;

      final stream = response.data?.stream;
      if (stream == null) return false;

      _sseSub = stream
          .cast<List<int>>()
          .transform(utf8.decoder)
          .transform(const LineSplitter())
          .listen(
        (line) {
          if (line.startsWith('data: ')) {
            _handleData(line.substring(6));
          }
        },
        onError: (_) {
          _isListening = false;
        },
        onDone: () {
          _isListening = false;
        },
        cancelOnError: false,
      );

      return true;
    } catch (_) {
      return false;
    }
  }

  /// Stop listening.
  void stop() {
    _sseSub?.cancel();
    _sseSub = null;
    _isListening = false;
  }

  void _handleData(String data) async {
    try {
      final json = jsonDecode(data) as Map<String, dynamic>;
      final title = json['title'] as String? ?? 'CachiBot';
      final message = json['message'] as String? ?? '';
      final tags = (json['tags'] as List<dynamic>?)?.cast<String>() ?? [];

      if (message.isEmpty) return;

      // Route notifications based on tags
      if (tags.contains('message')) {
        await notificationService.showMessage(
          id: _notificationId++,
          botName: title,
          message: message,
        );
      } else if (tags.contains('work')) {
        await notificationService.showWorkUpdate(
          id: _notificationId++,
          title: title,
          body: message,
        );
      } else {
        await notificationService.showReminder(
          id: _notificationId++,
          title: title,
          body: message,
        );
      }
    } catch (_) {
      // Malformed SSE data — ignore
    }
  }

  // ---- Configuration ----

  static Future<String?> getServerUrl() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString(_serverUrlKey);
  }

  static Future<void> setServerUrl(String url) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_serverUrlKey, url);
  }

  static Future<void> clearServerUrl() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_serverUrlKey);
  }

  static Future<void> setTopic(String topic) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_topicKey, topic);
  }
}

/// Convenience global accessor.
final ntfyService = NtfyService.instance;
