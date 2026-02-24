/// Server health and version information.
class ServerInfo {
  const ServerInfo({
    required this.status,
    required this.version,
    required this.build,
    required this.python,
    required this.platform,
    required this.desktop,
    required this.distribution,
  });

  final String status;
  final String version;
  final String build;
  final String python;
  final String platform;
  final bool desktop;
  final String distribution;

  factory ServerInfo.fromJson(Map<String, dynamic> json) {
    return ServerInfo(
      status: json['status'] as String? ?? 'unknown',
      version: json['version'] as String? ?? 'unknown',
      build: json['build'] as String? ?? 'unknown',
      python: json['python'] as String? ?? 'unknown',
      platform: json['platform'] as String? ?? 'unknown',
      desktop: json['desktop'] as bool? ?? false,
      distribution: json['distribution'] as String? ?? 'unknown',
    );
  }
}
