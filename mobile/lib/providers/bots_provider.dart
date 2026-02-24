import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/bot.dart';
import 'service_providers.dart';

class BotsState {
  const BotsState({
    this.bots = const [],
    this.isLoading = false,
    this.errorMessage,
  });

  final List<Bot> bots;
  final bool isLoading;
  final String? errorMessage;

  BotsState copyWith({
    List<Bot>? bots,
    bool? isLoading,
    String? errorMessage,
    bool clearError = false,
  }) {
    return BotsState(
      bots: bots ?? this.bots,
      isLoading: isLoading ?? this.isLoading,
      errorMessage: clearError ? null : (errorMessage ?? this.errorMessage),
    );
  }
}

class BotsNotifier extends StateNotifier<BotsState> {
  BotsNotifier(this._ref) : super(const BotsState());

  final Ref _ref;

  Future<void> loadBots() async {
    state = state.copyWith(isLoading: true, clearError: true);

    try {
      final botService = _ref.read(botServiceProvider);
      final bots = await botService.listBots();
      state = BotsState(bots: bots);
    } on DioException catch (e) {
      final detail = e.response?.data;
      final message = detail is Map<String, dynamic>
          ? (detail['detail']?.toString() ?? 'Failed to load bots')
          : 'Failed to load bots';
      state = state.copyWith(isLoading: false, errorMessage: message);
    } catch (e) {
      state = state.copyWith(
        isLoading: false,
        errorMessage: e.toString(),
      );
    }
  }

  void clear() {
    state = const BotsState();
  }
}

final botsProvider = StateNotifierProvider<BotsNotifier, BotsState>((ref) {
  return BotsNotifier(ref);
});
