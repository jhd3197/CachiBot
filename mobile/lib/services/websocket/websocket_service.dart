import 'dart:async';
import 'dart:convert';
import 'dart:math';

import 'package:web_socket_channel/web_socket_channel.dart';

import '../../models/ws_message.dart';

class WebSocketService {
  WebSocketService({
    required this.baseUrl,
    required this.tokenProvider,
  });

  /// Base HTTP URL of the server (e.g. "http://192.168.1.100:5870").
  final String baseUrl;

  /// Returns the current access token.
  final Future<String?> Function() tokenProvider;

  WebSocketChannel? _channel;
  StreamSubscription? _subscription;

  final _eventController = StreamController<WSEvent>.broadcast();
  Stream<WSEvent> get events => _eventController.stream;

  final _connectionController = StreamController<bool>.broadcast();
  Stream<bool> get connectionState => _connectionController.stream;

  bool _intentionalClose = false;
  int _reconnectAttempts = 0;
  static const _maxReconnectAttempts = 5;
  static const _baseDelay = Duration(seconds: 1);

  bool get isConnected => _channel != null;

  Future<void> connect() async {
    _intentionalClose = false;
    _reconnectAttempts = 0;
    await _doConnect();
  }

  Future<void> _doConnect() async {
    final token = await tokenProvider();
    if (token == null) return;

    // Convert http(s) to ws(s)
    final wsBase = baseUrl
        .replaceFirst('https://', 'wss://')
        .replaceFirst('http://', 'ws://');
    final uri = Uri.parse('$wsBase/ws?token=$token');

    try {
      final wasReconnecting = _reconnectAttempts > 0;
      _channel = WebSocketChannel.connect(uri);
      await _channel!.ready;
      _reconnectAttempts = 0;

      _connectionController.add(true);

      _subscription = _channel!.stream.listen(
        _onData,
        onError: _onError,
        onDone: _onDone,
      );

      // Emit synthetic reconnected event so providers can flush queues
      if (wasReconnecting) {
        _eventController.add(const WSEvent(
          type: WSEvent.reconnected,
          payload: {},
        ));
      }
    } catch (e) {
      _channel = null;
      _connectionController.add(false);
      _scheduleReconnect();
    }
  }

  void _onData(dynamic data) {
    try {
      final json = jsonDecode(data as String) as Map<String, dynamic>;
      _eventController.add(WSEvent.fromJson(json));
    } catch (_) {
      // Ignore malformed messages
    }
  }

  void _onError(Object error) {
    _eventController.addError(error);
    _cleanup();
    if (!_intentionalClose) _scheduleReconnect();
  }

  void _onDone() {
    _cleanup();
    if (!_intentionalClose) _scheduleReconnect();
  }

  void _cleanup() {
    _subscription?.cancel();
    _subscription = null;
    _channel = null;
    _connectionController.add(false);
  }

  void _scheduleReconnect() {
    if (_reconnectAttempts >= _maxReconnectAttempts) return;
    _reconnectAttempts++;

    final delay = _baseDelay * pow(2, _reconnectAttempts - 1);
    Future.delayed(delay, () {
      if (!_intentionalClose) _doConnect();
    });
  }

  void disconnect() {
    _intentionalClose = true;
    _subscription?.cancel();
    _channel?.sink.close();
    _cleanup();
  }

  void _send(Map<String, dynamic> data) {
    _channel?.sink.add(jsonEncode(data));
  }

  void sendChat(
    String message, {
    String? botId,
    String? chatId,
    String? model,
    String? systemPrompt,
    Map<String, dynamic>? capabilities,
  }) {
    _send({
      'type': WSEvent.chat,
      'payload': {
        'message': message,
        if (botId != null) 'botId': botId,
        if (chatId != null) 'chatId': chatId,
        if (model != null) 'model': model,
        if (systemPrompt != null) 'systemPrompt': systemPrompt,
        if (capabilities != null) 'capabilities': capabilities,
      },
    });
  }

  void sendCancel() {
    _send({
      'type': WSEvent.cancel,
      'payload': {},
    });
  }

  void sendApproval(String id, bool approved) {
    _send({
      'type': WSEvent.approval,
      'payload': {
        'id': id,
        'approved': approved,
      },
    });
  }

  Future<void> dispose() async {
    disconnect();
    await _eventController.close();
    await _connectionController.close();
  }
}
