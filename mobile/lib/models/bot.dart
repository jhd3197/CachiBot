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
      };
}
