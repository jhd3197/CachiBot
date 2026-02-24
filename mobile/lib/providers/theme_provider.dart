import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../core/constants/app_constants.dart';
import '../core/theme/app_colors.dart';
import '../core/theme/app_theme.dart';

// ---------------------------------------------------------------------------
// SharedPreferences provider
// ---------------------------------------------------------------------------

final sharedPreferencesProvider = Provider<SharedPreferences>((ref) {
  throw UnimplementedError('Override in ProviderScope with actual instance');
});

// ---------------------------------------------------------------------------
// Theme mode (light / dark / system)
// ---------------------------------------------------------------------------

final themeModeProvider = StateNotifierProvider<ThemeModeNotifier, ThemeMode>(
  (ref) => ThemeModeNotifier(ref.watch(sharedPreferencesProvider)),
);

class ThemeModeNotifier extends StateNotifier<ThemeMode> {
  ThemeModeNotifier(this._prefs) : super(_load(_prefs));

  final SharedPreferences _prefs;

  static ThemeMode _load(SharedPreferences prefs) {
    final value = prefs.getString(AppConstants.keyThemeMode);
    switch (value) {
      case 'light':
        return ThemeMode.light;
      case 'dark':
        return ThemeMode.dark;
      default:
        return ThemeMode.system;
    }
  }

  Future<void> setThemeMode(ThemeMode mode) async {
    state = mode;
    await _prefs.setString(AppConstants.keyThemeMode, mode.name);
  }
}

// ---------------------------------------------------------------------------
// Accent color (one of the 13 presets)
// ---------------------------------------------------------------------------

final accentColorProvider = StateNotifierProvider<AccentColorNotifier, PresetColor>(
  (ref) => AccentColorNotifier(ref.watch(sharedPreferencesProvider)),
);

class AccentColorNotifier extends StateNotifier<PresetColor> {
  AccentColorNotifier(this._prefs) : super(_load(_prefs));

  final SharedPreferences _prefs;

  static PresetColor _load(SharedPreferences prefs) {
    final value = prefs.getString(AppConstants.keyAccentColor);
    if (value == null) return PresetColor.green;
    return PresetColor.values.firstWhere(
      (c) => c.name == value,
      orElse: () => PresetColor.green,
    );
  }

  Future<void> setAccentColor(PresetColor color) async {
    state = color;
    await _prefs.setString(AppConstants.keyAccentColor, color.name);
  }
}

// ---------------------------------------------------------------------------
// Derived palette
// ---------------------------------------------------------------------------

final accentPaletteProvider = Provider<ColorPalette>((ref) {
  final preset = ref.watch(accentColorProvider);
  return accentColors[preset]!;
});

// ---------------------------------------------------------------------------
// Derived ThemeData
// ---------------------------------------------------------------------------

final lightThemeProvider = Provider<ThemeData>((ref) {
  final palette = ref.watch(accentPaletteProvider);
  return AppTheme.light(accent: palette);
});

final darkThemeProvider = Provider<ThemeData>((ref) {
  final palette = ref.watch(accentPaletteProvider);
  return AppTheme.dark(accent: palette);
});
