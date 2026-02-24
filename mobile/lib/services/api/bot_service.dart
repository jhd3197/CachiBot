import '../../models/bot.dart';
import '../../models/chat.dart';
import 'api_client.dart';

class BotService {
  BotService(this._client);

  final ApiClient _client;

  Future<List<Bot>> listBots() async {
    final response = await _client.dio.get('/api/bots');
    final list = response.data as List<dynamic>;
    return list
        .map((e) => Bot.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  Future<Bot> getBot(String botId) async {
    final response = await _client.dio.get('/api/bots/$botId');
    return Bot.fromJson(response.data as Map<String, dynamic>);
  }

  Future<List<Chat>> listChats(String botId) async {
    final response = await _client.dio.get('/api/bots/$botId/chats');
    final list = response.data as List<dynamic>;
    return list
        .map((e) => Chat.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  Future<List<ChatMessage>> getChatMessages(
    String botId,
    String chatId, {
    int limit = 50,
  }) async {
    final response = await _client.dio.get(
      '/api/bots/$botId/chats/$chatId/messages',
      queryParameters: {'limit': limit},
    );
    final list = response.data as List<dynamic>;
    return list
        .map((e) => ChatMessage.fromJson(e as Map<String, dynamic>))
        .toList();
  }
}
