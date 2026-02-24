import 'user.dart';

class LoginRequest {
  const LoginRequest({
    required this.identifier,
    required this.password,
  });

  final String identifier;
  final String password;

  Map<String, dynamic> toJson() => {
        'identifier': identifier,
        'password': password,
      };
}

class LoginResponse {
  const LoginResponse({
    required this.accessToken,
    required this.refreshToken,
    required this.tokenType,
    required this.user,
  });

  final String accessToken;
  final String refreshToken;
  final String tokenType;
  final User user;

  factory LoginResponse.fromJson(Map<String, dynamic> json) {
    return LoginResponse(
      accessToken: json['access_token'] as String,
      refreshToken: json['refresh_token'] as String,
      tokenType: json['token_type'] as String,
      user: User.fromJson(json['user'] as Map<String, dynamic>),
    );
  }
}

class RefreshResponse {
  const RefreshResponse({
    required this.accessToken,
    required this.tokenType,
  });

  final String accessToken;
  final String tokenType;

  factory RefreshResponse.fromJson(Map<String, dynamic> json) {
    return RefreshResponse(
      accessToken: json['access_token'] as String,
      tokenType: json['token_type'] as String,
    );
  }
}

class AuthModeResponse {
  const AuthModeResponse({
    required this.mode,
    this.loginUrl,
  });

  final String mode;
  final String? loginUrl;

  factory AuthModeResponse.fromJson(Map<String, dynamic> json) {
    return AuthModeResponse(
      mode: json['mode'] as String,
      loginUrl: json['login_url'] as String?,
    );
  }
}

class SetupRequest {
  const SetupRequest({
    required this.email,
    required this.username,
    required this.password,
  });

  final String email;
  final String username;
  final String password;

  Map<String, dynamic> toJson() => {
        'email': email,
        'username': username,
        'password': password,
      };
}

class SetupStatusResponse {
  const SetupStatusResponse({required this.setupRequired});

  final bool setupRequired;

  factory SetupStatusResponse.fromJson(Map<String, dynamic> json) {
    return SetupStatusResponse(
      setupRequired: json['setup_required'] as bool,
    );
  }
}
