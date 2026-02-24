import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/constants/app_constants.dart';
import '../../providers/auth_provider.dart';
import '../../providers/service_providers.dart';

class LoginScreen extends ConsumerStatefulWidget {
  const LoginScreen({super.key});

  @override
  ConsumerState<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends ConsumerState<LoginScreen> {
  final _serverUrlController = TextEditingController();
  final _emailController = TextEditingController();
  final _usernameController = TextEditingController();
  final _passwordController = TextEditingController();
  bool _obscurePassword = true;
  bool _isSetupMode = false;

  @override
  void initState() {
    super.initState();
    _loadSavedServerUrl();
  }

  void _loadSavedServerUrl() {
    final storage = ref.read(secureStorageProvider);
    final savedUrl = storage.getServerUrl();
    _serverUrlController.text = savedUrl ?? 'http://192.168.1.100:5870';
  }

  @override
  void dispose() {
    _serverUrlController.dispose();
    _emailController.dispose();
    _usernameController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  Future<void> _handleSignIn() async {
    final serverUrl = _serverUrlController.text.trim();
    if (serverUrl.isEmpty) return;

    if (_isSetupMode) {
      await ref.read(authProvider.notifier).setup(
            _emailController.text.trim(),
            _usernameController.text.trim(),
            _passwordController.text,
            serverUrl,
          );
    } else {
      await ref.read(authProvider.notifier).login(
            _emailController.text.trim(),
            _passwordController.text,
            serverUrl,
          );
    }
  }

  Future<void> _checkServer() async {
    final serverUrl = _serverUrlController.text.trim();
    if (serverUrl.isEmpty) return;

    await ref.read(authProvider.notifier).checkSetupRequired(serverUrl);
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final authState = ref.watch(authProvider);

    // Update setup mode when server responds
    if (authState.setupRequired != null) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted && _isSetupMode != authState.setupRequired!) {
          setState(() => _isSetupMode = authState.setupRequired!);
        }
      });
    }

    // Show errors as snackbar
    ref.listen<AuthState>(authProvider, (prev, next) {
      if (next.errorMessage != null && prev?.errorMessage != next.errorMessage) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(next.errorMessage!),
            behavior: SnackBarBehavior.floating,
          ),
        );
        ref.read(authProvider.notifier).clearError();
      }
      // Navigate on successful auth
      if (next.isAuthenticated && !(prev?.isAuthenticated ?? false)) {
        context.go('/');
      }
    });

    return Scaffold(
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.symmetric(horizontal: 32),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                // App icon
                Container(
                  width: 80,
                  height: 80,
                  decoration: BoxDecoration(
                    color: theme.colorScheme.primaryContainer,
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: Icon(
                    Icons.smart_toy,
                    size: 40,
                    color: theme.colorScheme.primary,
                  ),
                ),
                const SizedBox(height: 16),
                Text(
                  AppConstants.appName,
                  style: theme.textTheme.headlineMedium?.copyWith(
                    fontWeight: FontWeight.w700,
                  ),
                ),
                const SizedBox(height: 8),
                Text(
                  _isSetupMode
                      ? 'Create your admin account'
                      : 'Connect to your CachiBot server',
                  style: theme.textTheme.bodyMedium?.copyWith(
                    color: theme.colorScheme.onSurface.withValues(alpha: 0.6),
                  ),
                ),
                const SizedBox(height: 40),

                // Server URL
                TextField(
                  controller: _serverUrlController,
                  decoration: InputDecoration(
                    labelText: 'Server URL',
                    hintText: 'http://192.168.1.100:5870',
                    prefixIcon: const Icon(Icons.dns_outlined),
                    suffixIcon: IconButton(
                      icon: const Icon(Icons.refresh),
                      tooltip: 'Check server',
                      onPressed: authState.isLoading ? null : _checkServer,
                    ),
                  ),
                  keyboardType: TextInputType.url,
                  enabled: !authState.isLoading,
                ),
                const SizedBox(height: 16),

                // Username field (setup mode only)
                if (_isSetupMode) ...[
                  TextField(
                    controller: _usernameController,
                    decoration: const InputDecoration(
                      labelText: 'Username',
                      hintText: 'admin',
                      prefixIcon: Icon(Icons.person_outlined),
                    ),
                    enabled: !authState.isLoading,
                  ),
                  const SizedBox(height: 16),
                ],

                // Email
                TextField(
                  controller: _emailController,
                  decoration: InputDecoration(
                    labelText: _isSetupMode ? 'Email' : 'Email or Username',
                    hintText: 'you@example.com',
                    prefixIcon: const Icon(Icons.email_outlined),
                  ),
                  keyboardType: TextInputType.emailAddress,
                  enabled: !authState.isLoading,
                ),
                const SizedBox(height: 16),

                // Password
                TextField(
                  controller: _passwordController,
                  decoration: InputDecoration(
                    labelText: 'Password',
                    prefixIcon: const Icon(Icons.lock_outlined),
                    suffixIcon: IconButton(
                      icon: Icon(
                        _obscurePassword
                            ? Icons.visibility_off
                            : Icons.visibility,
                      ),
                      onPressed: () =>
                          setState(() => _obscurePassword = !_obscurePassword),
                    ),
                  ),
                  obscureText: _obscurePassword,
                  enabled: !authState.isLoading,
                  onSubmitted: (_) => _handleSignIn(),
                ),
                const SizedBox(height: 32),

                // Sign in / Setup button
                SizedBox(
                  width: double.infinity,
                  child: ElevatedButton(
                    onPressed: authState.isLoading ? null : _handleSignIn,
                    child: authState.isLoading
                        ? const SizedBox(
                            width: 20,
                            height: 20,
                            child: CircularProgressIndicator(
                              strokeWidth: 2,
                              color: Colors.white,
                            ),
                          )
                        : Text(_isSetupMode ? 'Create Account' : 'Sign In'),
                  ),
                ),
                const SizedBox(height: 16),

                // QR Code pairing button
                SizedBox(
                  width: double.infinity,
                  child: OutlinedButton.icon(
                    onPressed: authState.isLoading
                        ? null
                        : () => context.go('/qr-pair'),
                    icon: const Icon(Icons.qr_code_scanner),
                    label: const Text('Scan QR Code'),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
