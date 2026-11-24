class Bot {
  const Bot({
    required this.id,
    required this.name,
    this.description,
    this.icon,
    this.color,
    required this.model,
    this.models,
    required this.systemPrompt,
    required this.capabilities,
    required this.createdAt,
    required this.updatedAt,
    this.accessLevel,
  });

  final String id;
  final String name;
  final String? description;
  final String? icon;
  final String? color;
  final String model;
  final Map<String, dynamic>? models;
  final String systemPrompt;
  final Map<String, dynamic> capabilities;
  final DateTime createdAt;
  final DateTime updatedAt;

  /// The caller's access to this bot ("owner", "admin", "editor",
  /// "operator", "viewer"), present only in the list endpoint's payload.
  final String? accessLevel;

  /// Effective access rank for gating operator+ controls (0 = no access).
  /// Mirrors the frontend's `botAccessRank`.
  int get accessRank {
    const ranks = {'viewer': 1, 'operator': 2, 'editor': 3, 'owner': 4, 'admin': 4};
    return ranks[accessLevel] ?? 0;
  }

  bool get canOperate => accessRank >= 2;

  factory Bot.fromJson(Map<String, dynamic> json) {
    return Bot(
      id: json['id'] as String,
      name: json['name'] as String,
      description: json['description'] as String?,
      icon: json['icon'] as String?,
      color: json['color'] as String?,
      model: json['model'] as String,
      models: json['models'] as Map<String, dynamic>?,
      systemPrompt: json['systemPrompt'] as String,
      capabilities: (json['capabilities'] as Map<String, dynamic>?) ?? {},
      createdAt: DateTime.parse(json['createdAt'] as String),
      updatedAt: DateTime.parse(json['updatedAt'] as String),
      accessLevel: json['access_level'] as String?,
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'name': name,
        'description': description,
        'icon': icon,
        'color': color,
        'model': model,
        'models': models,
        'systemPrompt': systemPrompt,
        'capabilities': capabilities,
        'createdAt': createdAt.toIso8601String(),
        'updatedAt': updatedAt.toIso8601String(),
        if (accessLevel != null) 'access_level': accessLevel,
      };
}
