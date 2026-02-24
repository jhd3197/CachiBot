import 'dart:async';

import 'package:shared_preferences/shared_preferences.dart';

import '../websocket/websocket_service.dart';
import 'notification_service.dart';

/// Manages a background WebSocket connection for push-style notifications.
///
/// When the app is backgrounded, this service keeps the WS alive and
/// triggers local notifications for incoming events.
class BackgroundNotificationService {
  BackgroundNotificationService._();

  static final BackgroundNotificationService instance =
      BackgroundNotificationService._();

  StreamSubscription<dynamic>? _eventSub;
  bool _isActive = false;
  int _notificationId = 1000;

  static const _enabledKey = 'bg_notifications_enabled';
  static const _messagesEnabledKey = 'notify_messages';
  static const _approvalsEnabledKey = 'notify_approvals';
  static const _workEnabledKey = 'notify_work';

  /// Start listening to WebSocket events for background notifications.
  Future<void> start(WebSocketService ws) async {
    if (_isActive) return;
    _isActive = true;

    _eventSub = ws.events.listen(_handleEvent);
  }

  /// Stop background notification listening.
  void stop() {
    _eventSub?.cancel();
    _eventSub = null;
    _isActive = false;
  }

  bool get isActive => _isActive;

  void _handleEvent(dynamic event) async {
    // Only notify when we have the payload and event type
    if (event is! Map<String, dynamic>) return;

    final type = event['type'] as String?;
    final payload = event['payload'] as Map<String, dynamic>?;

    if (type == null || payload == null) return;

    final prefs = await SharedPreferences.getInstance();

    switch (type) {
      case 'message':
        if (prefs.getBool(_messagesEnabledKey) ?? true) {
          final content = payload['content'] as String? ?? '';
          final botName = payload['botName'] as String? ?? 'Bot';
          if (content.isNotEmpty) {
            await notificationService.showMessage(
              id: _notificationId++,
              botName: botName,
              message: content.length > 100
                  ? '${content.substring(0, 100)}...'
                  : content,
              chatRoute: payload['chatRoute'] as String?,
            );
          }
        }

      case 'approval_needed':
        if (prefs.getBool(_approvalsEnabledKey) ?? true) {
          final tool = payload['tool'] as String? ?? 'Unknown';
          await notificationService.showMessage(
            id: _notificationId++,
            botName: 'Approval Required',
            message: 'Bot wants to use: $tool',
          );
        }

      case 'job_update':
        if (prefs.getBool(_workEnabledKey) ?? true) {
          final status = payload['status'] as String? ?? '';
          final title = payload['title'] as String? ?? 'Work';
          await notificationService.showWorkUpdate(
            id: _notificationId++,
            title: 'Work Update',
            body: '$title: $status',
          );
        }

      case 'scheduled_notification':
        await notificationService.showReminder(
          id: _notificationId++,
          title: payload['title'] as String? ?? 'Reminder',
          body: payload['body'] as String? ?? '',
          route: payload['route'] as String?,
        );
    }
  }

  // ---- Preference helpers ----

  static Future<bool> isEnabled() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getBool(_enabledKey) ?? false;
  }

  static Future<void> setEnabled(bool value) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_enabledKey, value);
  }

  static Future<bool> messagesEnabled() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getBool(_messagesEnabledKey) ?? true;
  }

  static Future<void> setMessagesEnabled(bool value) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_messagesEnabledKey, value);
  }

  static Future<bool> approvalsEnabled() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getBool(_approvalsEnabledKey) ?? true;
  }

  static Future<void> setApprovalsEnabled(bool value) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_approvalsEnabledKey, value);
  }

  static Future<bool> workEnabled() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getBool(_workEnabledKey) ?? true;
  }

  static Future<void> setWorkEnabled(bool value) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_workEnabledKey, value);
  }
}

/// Convenience global accessor.
final backgroundNotificationService = BackgroundNotificationService.instance;
