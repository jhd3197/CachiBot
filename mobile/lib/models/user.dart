class User {
  const User({
    required this.id,
    required this.email,
    required this.username,
    required this.role,
    required this.isActive,
    required this.createdAt,
    this.lastLogin,
  });

  final String id;
  final String email;
  final String username;
  final String role;
  final bool isActive;
  final DateTime createdAt;
  final DateTime? lastLogin;

  factory User.fromJson(Map<String, dynamic> json) {
    return User(
      id: json['id'] as String,
      email: json['email'] as String,
      username: json['username'] as String,
      role: json['role'] as String,
      isActive: json['is_active'] as bool,
      createdAt: DateTime.parse(json['created_at'] as String),
      lastLogin: json['last_login'] != null
          ? DateTime.parse(json['last_login'] as String)
          : null,
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'email': email,
        'username': username,
        'role': role,
        'is_active': isActive,
        'created_at': createdAt.toIso8601String(),
        'last_login': lastLogin?.toIso8601String(),
      };
}
