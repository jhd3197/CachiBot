import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';

import '../../models/computer.dart';
import 'api_client.dart';

/// A computer API call the server refused, with the HTTP status kept so
/// callers can tell "asleep / nothing to show" (409/404) from "not allowed"
/// (403) from a real failure.
class ComputerApiException implements Exception {
  const ComputerApiException(this.statusCode, this.message);

  final int statusCode;
  final String message;

  bool get isForbidden => statusCode == 403;

  @override
  String toString() => message;
}

/// REST client for the bot's computer (Mini Vela).
///
/// Mirrors the web client's `api/computer.ts`: status/state, the live
/// preview and per-window frames (image bytes with the ETag/304 contract —
/// a preview never wakes the computer), the windows list with the activity
/// line, watch heartbeats, take over / hand back / person input, and the
/// needs-you answer. Everything returns real backend state — no
/// placeholders — and the views stay hidden while
/// [DockerProbeStatus.available] is false.
///
/// Auth travels through the shared [ApiClient] interceptor; tokens are
/// never logged.
class ComputerService {
  ComputerService(this._client);

  final ApiClient _client;

  /// Docker probe summary — the UI hides every computer surface when
  /// unavailable.
  Future<DockerProbeStatus> getStatus() async {
    final response = await _client.dio.get('/api/computer/status');
    return DockerProbeStatus.fromJson(response.data as Map<String, dynamic>);
  }

  /// Current state of one bot's computer.
  Future<BotComputerStatus> getBotComputer(String botId) async {
    final response = await _client.dio.get('/api/bots/$botId/computer');
    return BotComputerStatus.fromJson(response.data as Map<String, dynamic>);
  }

  /// Turn the computer on (background work; watch `computer_update` events).
  Future<BotComputerStatus> wakeComputer(String botId) async {
    final response = await _client.dio.post('/api/bots/$botId/computer/wake');
    return BotComputerStatus.fromJson(response.data as Map<String, dynamic>);
  }

  /// The live preview image: the full-desktop frame when the computer's
  /// Vela offers it, else the focused/top window's frame. Pass the ETag of
  /// the frame you hold; null means 304 (unchanged). Never wakes the
  /// computer — a sleeping one answers 409.
  Future<ComputerFrame?> getPreview(String botId, {String? etag}) {
    return _frameRequest('/api/bots/$botId/computer/preview', etag);
  }

  /// The open windows (app + title) and the activity line.
  Future<ComputerViews> getViews(String botId) async {
    final response = await _client.dio.get('/api/bots/$botId/computer/views');
    return ComputerViews.fromJson(response.data as Map<String, dynamic>);
  }

  /// One window's frame, proxied. Pass its ETag; null means 304.
  Future<ComputerFrame?> getViewFrame(
    String botId,
    String viewId, {
    String? etag,
  }) {
    return _frameRequest(
      '/api/bots/$botId/computer/views/$viewId/frame',
      etag,
    );
  }

  /// A watch heartbeat: the caller counts as watching (~30 s TTL), keeping
  /// the computer awake. Send while the computer is on screen; the server
  /// forwards it to Vela so its watcher count is right. Never wakes a
  /// sleeping computer (409).
  Future<void> watch(String botId) async {
    await _client.dio.post('/api/bots/$botId/computer/watch');
  }

  /// Take over the computer (operator+): the bot waits while you drive.
  Future<BotComputerStatus> takeover(String botId) async {
    final response =
        await _client.dio.post('/api/bots/$botId/computer/takeover');
    return BotComputerStatus.fromJson(response.data as Map<String, dynamic>);
  }

  /// Hand the computer back (operator+): releases the control lease.
  Future<BotComputerStatus> handback(String botId) async {
    final response =
        await _client.dio.post('/api/bots/$botId/computer/handback');
    return BotComputerStatus.fromJson(response.data as Map<String, dynamic>);
  }

  /// Send one piece of person input (operator+, only while you hold the
  /// take-over): click (left/right), scroll, type, key. [input] is the
  /// documented payload — kind plus its fields (`viewId`, `point`,
  /// `button`, `dx`/`dy`, `text`, `key`, `frameAt`).
  Future<void> sendInput(String botId, Map<String, dynamic> input) async {
    await _client.dio.post(
      '/api/bots/$botId/computer/input',
      data: input,
    );
  }

  /// Answer a needs-you (operator+): `takeover`, or `skip` — the documented
  /// closest refusal (an approval is denied; a needs-person pause stops the
  /// run).
  Future<BotComputerStatus> respondNeedsYou(String botId, String action) async {
    final response = await _client.dio.post(
      '/api/bots/$botId/computer/needs-you/respond',
      data: {'action': action},
    );
    return BotComputerStatus.fromJson(response.data as Map<String, dynamic>);
  }

  /// Fetch image bytes with the ETag contract: pass the ETag you hold and a
  /// 304 answers null (your bytes are current). A 409/404 (computer asleep,
  /// nothing to show) throws [ComputerApiException] — callers decide;
  /// nothing is faked.
  Future<ComputerFrame?> _frameRequest(String path, String? etag) async {
    final response = await _client.dio.get<Uint8List>(
      path,
      options: Options(
        responseType: ResponseType.bytes,
        headers: {if (etag != null) 'If-None-Match': etag},
        // 304/409/404 are answers, not transport failures — handled below.
        // A 401 still throws so the auth interceptor's refresh-retry runs.
        validateStatus: (status) =>
            status != null && status != 401 && status < 500,
      ),
    );

    final status = response.statusCode ?? 0;
    if (status == 304) return null;
    if (status == 200) {
      final bytes = response.data ?? Uint8List(0);
      final etagHeader = response.headers.value('etag');
      return ComputerFrame(
        bytes: bytes,
        etag: etagHeader,
        revision: etagHeader?.replaceAll('"', ''),
      );
    }
    throw ComputerApiException(status, _detailFrom(response) ?? 'Request failed ($status)');
  }

  /// Error bodies arrive as bytes under `ResponseType.bytes`; decode the
  /// JSON `detail` when there is one.
  static String? _detailFrom(Response<List<int>> response) {
    final data = response.data;
    if (data == null || data.isEmpty) return null;
    try {
      final decoded = jsonDecode(utf8.decode(data));
      if (decoded is Map<String, dynamic> && decoded['detail'] is String) {
        return decoded['detail'] as String;
      }
    } catch (_) {}
    return null;
  }
}
