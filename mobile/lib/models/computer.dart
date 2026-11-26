import 'dart:typed_data';

/// Lifecycle states of a bot's computer, mirroring the backend's
/// `ComputerState`. A computer in [off] or [asleep] has no live frame —
/// the UI shows the real state, never an invented one.
class ComputerStates {
  static const String unavailable = 'unavailable';
  static const String off = 'off';
  static const String building = 'building';
  static const String starting = 'starting';
  static const String awake = 'awake';
  static const String asleep = 'asleep';
  static const String needsYou = 'needs_you';

  /// States with a live desktop to watch (and a preview endpoint that
  /// answers instead of refusing with a 409).
  static bool isLive(String? state) =>
      state == awake || state == needsYou;
}

/// GET /api/computer/status — the Docker probe summary. Every computer
/// surface stays hidden while [available] is false.
class DockerProbeStatus {
  const DockerProbeStatus({
    required this.available,
    this.reason,
    this.dockerVersion,
    this.serverOs,
    this.arch,
  });

  final bool available;
  final String? reason;
  final String? dockerVersion;
  final String? serverOs;
  final String? arch;

  factory DockerProbeStatus.fromJson(Map<String, dynamic> json) {
    return DockerProbeStatus(
      available: json['available'] as bool? ?? false,
      reason: json['reason'] as String?,
      dockerVersion: json['docker_version'] as String?,
      serverOs: json['server_os'] as String?,
      arch: json['arch'] as String?,
    );
  }

  /// An unreachable probe reads as "no computer": views stay hidden.
  static const unavailable = DockerProbeStatus(available: false);
}

/// Progress of the (global, single-flight) Vela image build. [step]/[total]
/// are present only when the build line carried a step marker.
class ComputerBuild {
  const ComputerBuild({
    required this.status,
    this.step,
    this.total,
    this.line = '',
    this.error,
  });

  final String status;
  final int? step;
  final int? total;
  final String line;
  final String? error;

  factory ComputerBuild.fromJson(Map<String, dynamic> json) {
    return ComputerBuild(
      status: json['status'] as String? ?? 'idle',
      step: json['step'] as int?,
      total: json['total'] as int?,
      line: json['line'] as String? ?? '',
      error: json['error'] as String?,
    );
  }
}

/// The desktop's one-line "what it is doing", derived by Vela from the step
/// that is actually running (never invented).
class ComputerActivity {
  const ComputerActivity({required this.text, required this.at, this.viewId});

  final String text;
  final double at;
  final String? viewId;

  factory ComputerActivity.fromJson(Map<String, dynamic> json) {
    return ComputerActivity(
      text: json['text'] as String? ?? '',
      at: (json['at'] as num?)?.toDouble() ?? 0,
      viewId: json['viewId'] as String?,
    );
  }
}

/// Who is driving the computer right now (a person holding the take-over).
class ComputerDriver {
  const ComputerDriver({
    required this.userId,
    required this.name,
    required this.since,
  });

  final String userId;
  final String name;
  final String since;

  factory ComputerDriver.fromJson(Map<String, dynamic> json) {
    return ComputerDriver(
      userId: json['userId'] as String? ?? '',
      name: json['name'] as String? ?? '',
      since: json['since'] as String? ?? '',
    );
  }
}

/// GET /api/bots/{id}/computer — one bot's computer status. Never carries
/// the controller token or the container's host port.
class BotComputerStatus {
  const BotComputerStatus({
    required this.available,
    this.reason,
    required this.state,
    this.build,
    this.velaVersion = '',
    this.lastActiveAt,
    this.lastError,
    this.activity,
    this.windowsCount = 0,
    this.watchers = 0,
    this.driver,
    this.needsYou,
    this.previewRevision,
  });

  final bool available;
  final String? reason;
  final String state;
  final ComputerBuild? build;
  final String velaVersion;
  final String? lastActiveAt;
  final String? lastError;
  final ComputerActivity? activity;
  final int windowsCount;
  final int watchers;
  final ComputerDriver? driver;
  final String? needsYou;
  final String? previewRevision;

  bool get isLive => ComputerStates.isLive(state);

  factory BotComputerStatus.fromJson(Map<String, dynamic> json) {
    final build = json['build'];
    final activity = json['activity'];
    final driver = json['driver'];
    return BotComputerStatus(
      available: json['available'] as bool? ?? false,
      reason: json['reason'] as String?,
      state: json['state'] as String? ?? ComputerStates.off,
      build: build is Map<String, dynamic>
          ? ComputerBuild.fromJson(build)
          : null,
      velaVersion: json['velaVersion'] as String? ?? '',
      lastActiveAt: json['lastActiveAt'] as String?,
      lastError: json['lastError'] as String?,
      activity: activity is Map<String, dynamic>
          ? ComputerActivity.fromJson(activity)
          : null,
      windowsCount: json['windowsCount'] as int? ?? 0,
      watchers: json['watchers'] as int? ?? 0,
      driver:
          driver is Map<String, dynamic> ? ComputerDriver.fromJson(driver) : null,
      needsYou: json['needsYou'] as String?,
      previewRevision: json['previewRevision'] as String?,
    );
  }

  /// A `computer_update` WS payload: the status plus the bot it belongs to.
  factory BotComputerStatus.fromUpdatePayload(Map<String, dynamic> json) =>
      BotComputerStatus.fromJson(json);
}

/// One open window on the bot's desktop (a Vela view), as the UI lists it.
class ComputerWindow {
  const ComputerWindow({
    required this.id,
    required this.kind,
    required this.title,
    required this.app,
    this.url,
  });

  final String id;
  final String kind;
  final String title;
  final String app;
  final String? url;

  factory ComputerWindow.fromJson(Map<String, dynamic> json) {
    return ComputerWindow(
      id: json['id'] as String,
      kind: json['kind'] as String? ?? 'app',
      title: json['title'] as String? ?? '',
      app: json['app'] as String? ?? '',
      url: json['url'] as String?,
    );
  }
}

/// GET .../computer/views — the open windows plus the activity line.
class ComputerViews {
  const ComputerViews({required this.windows, this.activity});

  final List<ComputerWindow> windows;
  final ComputerActivity? activity;

  factory ComputerViews.fromJson(Map<String, dynamic> json) {
    final raw = json['windows'] as List<dynamic>? ?? const [];
    final activity = json['activity'];
    return ComputerViews(
      windows: raw
          .map((e) => ComputerWindow.fromJson(e as Map<String, dynamic>))
          .toList(),
      activity: activity is Map<String, dynamic>
          ? ComputerActivity.fromJson(activity)
          : null,
    );
  }
}

/// One fetched frame (preview or window): the image bytes plus the ETag the
/// server named them by. A 304 answer means the bytes on screen are current.
class ComputerFrame {
  const ComputerFrame({required this.bytes, this.etag, this.revision});

  final Uint8List bytes;
  final String? etag;
  final String? revision;
}
