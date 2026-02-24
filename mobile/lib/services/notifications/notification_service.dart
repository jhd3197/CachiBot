import 'dart:io';

import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:go_router/go_router.dart';

/// Manages local notifications on Android/iOS.
class NotificationService {
  NotificationService._();

  static final NotificationService instance = NotificationService._();

  final FlutterLocalNotificationsPlugin _plugin =
      FlutterLocalNotificationsPlugin();

  GoRouter? _router;
  bool _initialized = false;

  /// Android notification channel IDs.
  static const _messagesChannelId = 'cachibot_messages';
  static const _workChannelId = 'cachibot_work';
  static const _remindersChannelId = 'cachibot_reminders';

  /// Initialize the notification plugin and create channels.
  Future<void> init({GoRouter? router}) async {
    if (_initialized) return;
    _router = router;

    const androidSettings =
        AndroidInitializationSettings('@mipmap/ic_launcher');
    const iosSettings = DarwinInitializationSettings(
      requestAlertPermission: false,
      requestBadgePermission: false,
      requestSoundPermission: false,
    );

    await _plugin.initialize(
      const InitializationSettings(
        android: androidSettings,
        iOS: iosSettings,
      ),
      onDidReceiveNotificationResponse: _onNotificationTap,
    );

    // Create Android channels
    if (Platform.isAndroid) {
      final androidPlugin =
          _plugin.resolvePlatformSpecificImplementation<
              AndroidFlutterLocalNotificationsPlugin>();

      await androidPlugin?.createNotificationChannel(
        const AndroidNotificationChannel(
          _messagesChannelId,
          'Messages',
          description: 'New messages from bots',
          importance: Importance.high,
        ),
      );
      await androidPlugin?.createNotificationChannel(
        const AndroidNotificationChannel(
          _workChannelId,
          'Work Updates',
          description: 'Work and task status changes',
          importance: Importance.defaultImportance,
        ),
      );
      await androidPlugin?.createNotificationChannel(
        const AndroidNotificationChannel(
          _remindersChannelId,
          'Reminders',
          description: 'Scheduled reminders',
          importance: Importance.high,
        ),
      );
    }

    _initialized = true;
  }

  /// Request notification permission (iOS/Android 13+).
  Future<bool> requestPermission() async {
    if (Platform.isAndroid) {
      final androidPlugin =
          _plugin.resolvePlatformSpecificImplementation<
              AndroidFlutterLocalNotificationsPlugin>();
      return await androidPlugin?.requestNotificationsPermission() ?? false;
    }

    if (Platform.isIOS) {
      final iosPlugin =
          _plugin.resolvePlatformSpecificImplementation<
              IOSFlutterLocalNotificationsPlugin>();
      return await iosPlugin?.requestPermissions(
            alert: true,
            badge: true,
            sound: true,
          ) ??
          false;
    }

    return false;
  }

  /// Show a message notification.
  Future<void> showMessage({
    required int id,
    required String botName,
    required String message,
    String? chatRoute,
  }) async {
    await _show(
      id: id,
      title: botName,
      body: message,
      channelId: _messagesChannelId,
      channelName: 'Messages',
      payload: chatRoute,
    );
  }

  /// Show a work update notification.
  Future<void> showWorkUpdate({
    required int id,
    required String title,
    required String body,
    String? workRoute,
  }) async {
    await _show(
      id: id,
      title: title,
      body: body,
      channelId: _workChannelId,
      channelName: 'Work Updates',
      payload: workRoute,
    );
  }

  /// Show a reminder notification.
  Future<void> showReminder({
    required int id,
    required String title,
    required String body,
    String? route,
  }) async {
    await _show(
      id: id,
      title: title,
      body: body,
      channelId: _remindersChannelId,
      channelName: 'Reminders',
      payload: route,
    );
  }

  Future<void> _show({
    required int id,
    required String title,
    required String body,
    required String channelId,
    required String channelName,
    String? payload,
  }) async {
    await _plugin.show(
      id,
      title,
      body,
      NotificationDetails(
        android: AndroidNotificationDetails(
          channelId,
          channelName,
          importance: Importance.high,
          priority: Priority.high,
        ),
        iOS: const DarwinNotificationDetails(
          presentAlert: true,
          presentBadge: true,
          presentSound: true,
        ),
      ),
      payload: payload,
    );
  }

  void _onNotificationTap(NotificationResponse response) {
    final route = response.payload;
    if (route != null && route.isNotEmpty && _router != null) {
      _router!.go(route);
    }
  }

  /// Cancel a specific notification.
  Future<void> cancel(int id) => _plugin.cancel(id);

  /// Cancel all notifications.
  Future<void> cancelAll() => _plugin.cancelAll();
}

/// Convenience global accessor.
final notificationService = NotificationService.instance;
