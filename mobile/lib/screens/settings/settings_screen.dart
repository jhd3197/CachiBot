import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:local_auth/local_auth.dart';
import 'package:package_info_plus/package_info_plus.dart';

import '../../core/theme/app_colors.dart';
import '../../models/server_info.dart';
import '../../providers/auth_provider.dart';
import '../../providers/service_providers.dart';
import '../../providers/theme_provider.dart';
import '../../services/database/app_database.dart';

class SettingsScreen extends ConsumerStatefulWidget {
  const SettingsScreen({super.key});

  @override
  ConsumerState<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends ConsumerState<SettingsScreen> {
  ServerInfo? _serverInfo;
  String _appVersion = '';
  int _cachedMessageCount = 0;
  bool _biometricAvailable = false;
  bool _biometricEnabled = false;

  @override
  void initState() {
    super.initState();
    _loadInfo();
  }

  Future<void> _loadInfo() async {
    // App version
    final packageInfo = await PackageInfo.fromPlatform();
    if (mounted) {
      setState(() {
        _appVersion = '${packageInfo.version}+${packageInfo.buildNumber}';
      });
    }

    // Biometric availability
    final auth = LocalAuthentication();
    try {
      final available = await auth.canCheckBiometrics || await auth.isDeviceSupported();
      final enabled = ref.read(authProvider.notifier).isBiometricEnabled;
      if (mounted) {
        setState(() {
          _biometricAvailable = available;
          _biometricEnabled = enabled;
        });
      }
    } catch (_) {}

    // Server info
    try {
      final botService = ref.read(botServiceProvider);
      final info = await botService.getHealth();
      if (mounted) setState(() => _serverInfo = info);
    } catch (_) {}

    // Cache size
    try {
      final dao = await ref.read(chatDaoProvider.future);
      final count = await dao.countCachedMessages();
      if (mounted) setState(() => _cachedMessageCount = count);
    } catch (_) {}
  }

  Future<void> _toggleBiometric(bool value) async {
    if (value) {
      // Verify biometric works before enabling
      final auth = LocalAuthentication();
      try {
        final didAuth = await auth.authenticate(
          localizedReason: 'Verify to enable biometric lock',
          options: const AuthenticationOptions(biometricOnly: false),
        );
        if (!didAuth) return;
      } catch (_) {
        return;
      }
    }

    await ref.read(authProvider.notifier).setBiometricLock(value);
    setState(() => _biometricEnabled = value);
  }

  Future<void> _clearCache() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Clear Local Cache'),
        content: Text(
          'This will delete $_cachedMessageCount cached messages. '
          'You\'ll need an internet connection to reload them.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Clear'),
          ),
        ],
      ),
    );

    if (confirmed != true) return;

    try {
      final dao = await ref.read(chatDaoProvider.future);
      await dao.clearAllData();
      setState(() => _cachedMessageCount = 0);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Cache cleared')),
        );
      }
    } catch (_) {}
  }

  Future<void> _switchServer() async {
    // Clear tokens but keep local cache
    final storage = ref.read(secureStorageProvider);
    await storage.clearTokens();
    ref.read(authProvider.notifier).logout();
    if (mounted) context.go('/login');
  }

  Future<void> _forgetServer() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Forget Server'),
        content: const Text(
          'This will clear all saved data including tokens and local cache. '
          'You\'ll need to log in again.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(context, true),
            style: TextButton.styleFrom(
              foregroundColor: Theme.of(context).colorScheme.error,
            ),
            child: const Text('Forget'),
          ),
        ],
      ),
    );

    if (confirmed != true) return;

    try {
      final dao = await ref.read(chatDaoProvider.future);
      await dao.clearAllData();
    } catch (_) {}

    await AppDatabase.reset();

    final storage = ref.read(secureStorageProvider);
    await storage.clearTokens();
    await ref.read(authProvider.notifier).logout();
    if (mounted) context.go('/login');
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final themeMode = ref.watch(themeModeProvider);
    final selectedAccent = ref.watch(accentColorProvider);
    final authState = ref.watch(authProvider);
    final storage = ref.watch(secureStorageProvider);
    final serverUrl = storage.getServerUrl();

    return Scaffold(
      appBar: AppBar(
        title: const Text('Settings'),
      ),
      body: ListView(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        children: [
          // ---- Server ----
          _SectionHeader(title: 'Server', theme: theme),
          const SizedBox(height: 12),
          Card(
            child: Column(
              children: [
                ListTile(
                  leading: const Icon(Icons.dns_outlined),
                  title: const Text('Connected to'),
                  subtitle: Text(serverUrl ?? 'Not connected'),
                ),
                if (authState.user != null)
                  ListTile(
                    leading: const Icon(Icons.person_outlined),
                    title: Text(authState.user!.username),
                    subtitle: Text(authState.user!.email),
                  ),
                if (_serverInfo != null)
                  ListTile(
                    leading: const Icon(Icons.info_outline),
                    title: const Text('Server version'),
                    subtitle: Text(
                      '${_serverInfo!.version} (${_serverInfo!.build})',
                    ),
                  ),
                const Divider(height: 1),
                Row(
                  children: [
                    Expanded(
                      child: TextButton.icon(
                        onPressed: _switchServer,
                        icon: const Icon(Icons.swap_horiz, size: 18),
                        label: const Text('Switch Server'),
                      ),
                    ),
                    Expanded(
                      child: TextButton.icon(
                        onPressed: _forgetServer,
                        icon: Icon(Icons.delete_outline,
                            size: 18, color: theme.colorScheme.error),
                        label: Text(
                          'Forget Server',
                          style: TextStyle(color: theme.colorScheme.error),
                        ),
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
          const SizedBox(height: 24),

          // ---- Theme mode ----
          _SectionHeader(title: 'Appearance', theme: theme),
          const SizedBox(height: 12),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Theme', style: theme.textTheme.bodyMedium),
                  const SizedBox(height: 12),
                  SizedBox(
                    width: double.infinity,
                    child: SegmentedButton<ThemeMode>(
                      segments: const [
                        ButtonSegment(
                          value: ThemeMode.light,
                          icon: Icon(Icons.light_mode, size: 18),
                          label: Text('Light'),
                        ),
                        ButtonSegment(
                          value: ThemeMode.system,
                          icon: Icon(Icons.brightness_auto, size: 18),
                          label: Text('System'),
                        ),
                        ButtonSegment(
                          value: ThemeMode.dark,
                          icon: Icon(Icons.dark_mode, size: 18),
                          label: Text('Dark'),
                        ),
                      ],
                      selected: {themeMode},
                      onSelectionChanged: (selected) {
                        ref
                            .read(themeModeProvider.notifier)
                            .setThemeMode(selected.first);
                      },
                    ),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 24),

          // ---- Accent color ----
          _SectionHeader(title: 'Accent Color', theme: theme),
          const SizedBox(height: 12),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Wrap(
                spacing: 12,
                runSpacing: 12,
                children: PresetColor.values.map((preset) {
                  final palette = accentColors[preset]!;
                  final isSelected = preset == selectedAccent;

                  return GestureDetector(
                    onTap: () {
                      ref
                          .read(accentColorProvider.notifier)
                          .setAccentColor(preset);
                    },
                    child: AnimatedContainer(
                      duration: const Duration(milliseconds: 200),
                      width: 40,
                      height: 40,
                      decoration: BoxDecoration(
                        color: palette.shade500,
                        shape: BoxShape.circle,
                        border: Border.all(
                          color: isSelected
                              ? theme.colorScheme.onSurface
                              : Colors.transparent,
                          width: 2.5,
                        ),
                        boxShadow: isSelected
                            ? [
                                BoxShadow(
                                  color: palette.shade500
                                      .withValues(alpha: 0.4),
                                  blurRadius: 8,
                                  spreadRadius: 1,
                                ),
                              ]
                            : null,
                      ),
                      child: isSelected
                          ? const Icon(Icons.check,
                              color: Colors.white, size: 20)
                          : null,
                    ),
                  );
                }).toList(),
              ),
            ),
          ),
          const SizedBox(height: 24),

          // ---- Security ----
          if (_biometricAvailable) ...[
            _SectionHeader(title: 'Security', theme: theme),
            const SizedBox(height: 12),
            Card(
              child: SwitchListTile(
                secondary: const Icon(Icons.fingerprint),
                title: const Text('Biometric Lock'),
                subtitle: const Text(
                  'Require fingerprint or face to open the app',
                ),
                value: _biometricEnabled,
                onChanged: _toggleBiometric,
              ),
            ),
            const SizedBox(height: 24),
          ],

          // ---- Data ----
          _SectionHeader(title: 'Data', theme: theme),
          const SizedBox(height: 12),
          Card(
            child: Column(
              children: [
                ListTile(
                  leading: const Icon(Icons.storage_outlined),
                  title: const Text('Cached Messages'),
                  subtitle: Text('$_cachedMessageCount messages stored locally'),
                ),
                const Divider(height: 1),
                ListTile(
                  leading: Icon(Icons.delete_sweep_outlined,
                      color: theme.colorScheme.error),
                  title: Text(
                    'Clear Local Cache',
                    style: TextStyle(color: theme.colorScheme.error),
                  ),
                  onTap: _clearCache,
                ),
              ],
            ),
          ),
          const SizedBox(height: 24),

          // ---- About ----
          _SectionHeader(title: 'About', theme: theme),
          const SizedBox(height: 12),
          Card(
            child: Column(
              children: [
                ListTile(
                  leading: const Icon(Icons.info_outline),
                  title: const Text('CachiBot Mobile'),
                  subtitle: Text('v$_appVersion'),
                ),
                if (serverUrl != null)
                  ListTile(
                    leading: const Icon(Icons.link),
                    title: const Text('Server'),
                    subtitle: Text(serverUrl),
                  ),
                if (_serverInfo != null)
                  ListTile(
                    leading: const Icon(Icons.memory),
                    title: const Text('Server Platform'),
                    subtitle: Text(
                      '${_serverInfo!.platform} • Python ${_serverInfo!.python} • ${_serverInfo!.distribution}',
                    ),
                  ),
              ],
            ),
          ),
          const SizedBox(height: 24),

          // ---- Log Out ----
          SizedBox(
            width: double.infinity,
            child: OutlinedButton.icon(
              onPressed: () async {
                await ref.read(authProvider.notifier).logout();
                if (context.mounted) context.go('/login');
              },
              icon: const Icon(Icons.logout),
              label: const Text('Log Out'),
              style: OutlinedButton.styleFrom(
                foregroundColor: theme.colorScheme.error,
                side: BorderSide(color: theme.colorScheme.error),
              ),
            ),
          ),
          const SizedBox(height: 32),
        ],
      ),
    );
  }
}

class _SectionHeader extends StatelessWidget {
  const _SectionHeader({required this.title, required this.theme});

  final String title;
  final ThemeData theme;

  @override
  Widget build(BuildContext context) {
    return Text(
      title,
      style: theme.textTheme.titleSmall?.copyWith(
        color: theme.colorScheme.primary,
        fontWeight: FontWeight.w600,
      ),
    );
  }
}
