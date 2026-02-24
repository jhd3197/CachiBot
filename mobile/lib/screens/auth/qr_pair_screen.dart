import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:mobile_scanner/mobile_scanner.dart';

import '../../models/auth.dart';
import '../../providers/auth_provider.dart';
import '../../providers/service_providers.dart';

/// QR code scanner screen for mobile device pairing.
///
/// Scans a `cachibot://pair?url=...&token=...&urls=...` URI, probes each
/// candidate URL for reachability, redeems the token, and navigates home.
class QrPairScreen extends ConsumerStatefulWidget {
  const QrPairScreen({super.key});

  @override
  ConsumerState<QrPairScreen> createState() => _QrPairScreenState();
}

class _QrPairScreenState extends ConsumerState<QrPairScreen> {
  final MobileScannerController _scannerController = MobileScannerController();
  bool _isProcessing = false;
  String? _error;
  String? _status;

  @override
  void dispose() {
    _scannerController.dispose();
    super.dispose();
  }

  /// Try to reach [url]/api/health with a short timeout.
  Future<bool> _isReachable(String url) async {
    try {
      final dio = Dio(BaseOptions(
        baseUrl: url,
        connectTimeout: const Duration(seconds: 3),
        receiveTimeout: const Duration(seconds: 3),
      ));
      final resp = await dio.get('/api/health');
      return resp.statusCode == 200;
    } catch (_) {
      return false;
    }
  }

  /// Probe all candidate URLs in parallel and return the first reachable one.
  Future<String?> _findReachableUrl(List<String> urls) async {
    if (urls.isEmpty) return null;
    // Fire all probes concurrently
    final futures = urls.map((url) async {
      final ok = await _isReachable(url);
      return ok ? url : null;
    }).toList();

    for (final future in futures) {
      final result = await future;
      if (result != null) return result;
    }
    return null;
  }

  Future<void> _onDetect(BarcodeCapture capture) async {
    if (_isProcessing) return;

    for (final barcode in capture.barcodes) {
      final raw = barcode.rawValue;
      if (raw == null || !raw.startsWith('cachibot://pair')) continue;

      setState(() {
        _isProcessing = true;
        _error = null;
        _status = 'Reading QR code...';
      });

      try {
        final uri = Uri.parse(raw);
        final primaryUrl = uri.queryParameters['url'];
        final token = uri.queryParameters['token'];
        // Collect all candidate URLs (primary + extras)
        final extraUrls = uri.queryParametersAll['urls'] ?? [];

        if (primaryUrl == null || token == null) {
          setState(() {
            _error = 'Invalid QR code format';
            _isProcessing = false;
            _status = null;
          });
          return;
        }

        // Build deduplicated candidate list: primary first, then extras
        final candidates = <String>[primaryUrl];
        for (final u in extraUrls) {
          if (u.isNotEmpty && !candidates.contains(u)) {
            candidates.add(u);
          }
        }

        // Connectivity pre-check
        setState(() => _status = 'Checking connectivity (${candidates.length} addresses)...');

        final reachableUrl = await _findReachableUrl(candidates);
        if (reachableUrl == null) {
          setState(() {
            _error =
                'Cannot reach the server. Make sure your phone is on the same network.\n\nTried: ${candidates.join(', ')}';
            _isProcessing = false;
            _status = null;
          });
          return;
        }

        // Redeem the pairing token on the reachable URL
        setState(() => _status = 'Pairing with $reachableUrl...');

        final dio = Dio(BaseOptions(
          baseUrl: reachableUrl,
          connectTimeout: const Duration(seconds: 10),
          receiveTimeout: const Duration(seconds: 10),
        ));

        final response = await dio.post(
          '/api/auth/mobile-pair/redeem',
          data: {'token': token},
        );

        final loginData = response.data as Map<String, dynamic>;
        final loginResponse = LoginResponse.fromJson(loginData);

        // Save credentials
        final storage = ref.read(secureStorageProvider);
        await storage.saveServerUrl(reachableUrl);
        await storage.saveTokens(
          accessToken: loginResponse.accessToken,
          refreshToken: loginResponse.refreshToken,
        );

        // Update API client base URL
        final client = ref.read(apiClientProvider);
        client.setBaseUrl(reachableUrl);

        // Restore full session (loads user profile)
        await ref.read(authProvider.notifier).restoreSession();

        if (mounted) {
          context.go('/');
        }
      } on DioException catch (e) {
        final detail = e.response?.data is Map
            ? (e.response!.data as Map)['detail']?.toString()
            : null;
        setState(() {
          _error = detail ?? 'Failed to pair: ${e.message}';
          _isProcessing = false;
          _status = null;
        });
      } catch (e) {
        setState(() {
          _error = 'An unexpected error occurred: $e';
          _isProcessing = false;
          _status = null;
        });
      }
      return;
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Scan QR Code'),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () => context.go('/login'),
        ),
      ),
      body: Column(
        children: [
          Expanded(
            child: _isProcessing
                ? Center(
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const CircularProgressIndicator(),
                        const SizedBox(height: 16),
                        Text(
                          _status ?? 'Pairing...',
                          style: theme.textTheme.bodyLarge,
                          textAlign: TextAlign.center,
                        ),
                      ],
                    ),
                  )
                : MobileScanner(
                    controller: _scannerController,
                    onDetect: _onDetect,
                  ),
          ),
          if (_error != null)
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(16),
              color: theme.colorScheme.errorContainer,
              child: Column(
                children: [
                  Text(
                    _error!,
                    style: TextStyle(color: theme.colorScheme.onErrorContainer),
                    textAlign: TextAlign.center,
                  ),
                  const SizedBox(height: 8),
                  TextButton(
                    onPressed: () {
                      setState(() {
                        _error = null;
                        _isProcessing = false;
                        _status = null;
                      });
                    },
                    child: const Text('Try Again'),
                  ),
                ],
              ),
            ),
          SafeArea(
            top: false,
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                children: [
                  Icon(
                    Icons.qr_code_scanner,
                    size: 32,
                    color: theme.colorScheme.onSurface.withValues(alpha: 0.5),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    'Point your camera at the QR code shown\nin your CachiBot web settings',
                    textAlign: TextAlign.center,
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: theme.colorScheme.onSurface.withValues(alpha: 0.6),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}
