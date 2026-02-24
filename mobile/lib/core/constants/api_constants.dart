class ApiConstants {
  ApiConstants._();

  static const int defaultPort = 5870;
  static const String defaultHost = '192.168.1.100';
  static const String scheme = 'http';

  // REST endpoints
  static const String healthEndpoint = '/api/health';
  static const String chatEndpoint = '/api/chat';
  static const String configEndpoint = '/api/config';
  static const String modelsEndpoint = '/api/models';
  static const String botsEndpoint = '/api/bots';

  // Auth endpoints
  static const String authMode = '/api/auth/mode';
  static const String authSetupRequired = '/api/auth/setup-required';
  static const String authSetup = '/api/auth/setup';
  static const String authLogin = '/api/auth/login';
  static const String authRefresh = '/api/auth/refresh';
  static const String authMe = '/api/auth/me';

  // Chat endpoints (parameterized)
  static String botChats(String botId) => '/api/bots/$botId/chats';
  static String chatMessages(String botId, String chatId) =>
      '/api/bots/$botId/chats/$chatId/messages';

  // WebSocket
  static const String wsEndpoint = '/ws';

  static String baseUrl(String host, int port) => '$scheme://$host:$port';
  static String wsUrl(String host, int port, {String? token}) {
    final base = 'ws://$host:$port$wsEndpoint';
    return token != null ? '$base?token=$token' : base;
  }
}
