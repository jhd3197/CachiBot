import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import 'app_colors.dart';

class AppTheme {
  AppTheme._();

  static ThemeData light({required ColorPalette accent}) {
    final colorScheme = ColorScheme.light(
      primary: accent.shade600,
      onPrimary: Colors.white,
      primaryContainer: accent.shade100,
      onPrimaryContainer: accent.shade900,
      secondary: AppColors.zinc600,
      onSecondary: Colors.white,
      secondaryContainer: AppColors.zinc100,
      onSecondaryContainer: AppColors.zinc900,
      surface: AppColors.lightBgApp,
      onSurface: AppColors.lightTextPrimary,
      surfaceContainerLowest: Colors.white,
      surfaceContainerLow: AppColors.lightBgApp,
      surfaceContainer: const Color(0xFFF0F0F0),
      surfaceContainerHigh: AppColors.lightBgInset,
      surfaceContainerHighest: AppColors.zinc200,
      error: AppColors.lightDangerText,
      onError: Colors.white,
      errorContainer: AppColors.lightDangerBg,
      outline: AppColors.lightBorderSecondary,
      outlineVariant: AppColors.lightBorderPrimary,
      shadow: Colors.black,
      inverseSurface: AppColors.zinc900,
      onInverseSurface: AppColors.zinc50,
    );

    return _buildTheme(colorScheme, accent, Brightness.light);
  }

  static ThemeData dark({required ColorPalette accent}) {
    final colorScheme = ColorScheme.dark(
      primary: accent.shade500,
      onPrimary: Colors.white,
      primaryContainer: accent.shade900,
      onPrimaryContainer: accent.shade100,
      secondary: AppColors.zinc400,
      onSecondary: AppColors.zinc900,
      secondaryContainer: AppColors.zinc800,
      onSecondaryContainer: AppColors.zinc100,
      surface: AppColors.darkBgApp,
      onSurface: AppColors.darkTextPrimary,
      surfaceContainerLowest: Colors.black,
      surfaceContainerLow: AppColors.darkBgApp,
      surfaceContainer: AppColors.darkBgInset,
      surfaceContainerHigh: const Color(0xFF141414),
      surfaceContainerHighest: AppColors.zinc800,
      error: AppColors.darkDangerText,
      onError: Colors.black,
      errorContainer: AppColors.darkDangerBg,
      outline: AppColors.darkBorderSecondary,
      outlineVariant: AppColors.darkBorderPrimary,
      shadow: Colors.black,
      inverseSurface: AppColors.zinc100,
      onInverseSurface: AppColors.zinc900,
    );

    return _buildTheme(colorScheme, accent, Brightness.dark);
  }

  static ThemeData _buildTheme(
    ColorScheme colorScheme,
    ColorPalette accent,
    Brightness brightness,
  ) {
    final isLight = brightness == Brightness.light;
    final textTheme = GoogleFonts.interTextTheme(
      isLight ? ThemeData.light().textTheme : ThemeData.dark().textTheme,
    );

    return ThemeData(
      useMaterial3: true,
      brightness: brightness,
      colorScheme: colorScheme,
      textTheme: textTheme,
      scaffoldBackgroundColor: colorScheme.surface,
      appBarTheme: AppBarTheme(
        backgroundColor: colorScheme.surface,
        foregroundColor: colorScheme.onSurface,
        elevation: 0,
        scrolledUnderElevation: 0.5,
        centerTitle: false,
        titleTextStyle: textTheme.titleLarge?.copyWith(
          color: colorScheme.onSurface,
          fontWeight: FontWeight.w600,
        ),
      ),
      cardTheme: CardThemeData(
        color: isLight ? AppColors.lightCardBg : AppColors.darkBgDropdown,
        elevation: isLight ? 0.5 : 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
          side: BorderSide(
            color: colorScheme.outlineVariant,
            width: 1,
          ),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: isLight ? AppColors.lightInputBg : AppColors.darkInputBg,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: BorderSide(color: colorScheme.outline),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: BorderSide(color: colorScheme.outlineVariant),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: BorderSide(color: accent.shade500, width: 2),
        ),
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
        hintStyle: textTheme.bodyMedium?.copyWith(
          color: isLight ? AppColors.lightTextTertiary : AppColors.darkTextTertiary,
        ),
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: accent.shade600,
          foregroundColor: Colors.white,
          elevation: 0,
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 14),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(10),
          ),
          textStyle: textTheme.labelLarge?.copyWith(fontWeight: FontWeight.w600),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: colorScheme.onSurface,
          side: BorderSide(color: colorScheme.outlineVariant),
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 14),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(10),
          ),
        ),
      ),
      navigationBarTheme: NavigationBarThemeData(
        backgroundColor: isLight ? Colors.white : AppColors.darkBgInset,
        indicatorColor: accent.shade500.withValues(alpha: 0.15),
        iconTheme: WidgetStateProperty.resolveWith((states) {
          if (states.contains(WidgetState.selected)) {
            return IconThemeData(color: accent.shade600);
          }
          return IconThemeData(
            color: isLight ? AppColors.lightTextSecondary : AppColors.darkTextSecondary,
          );
        }),
        labelTextStyle: WidgetStateProperty.resolveWith((states) {
          if (states.contains(WidgetState.selected)) {
            return textTheme.labelSmall?.copyWith(
              color: accent.shade600,
              fontWeight: FontWeight.w600,
            );
          }
          return textTheme.labelSmall?.copyWith(
            color: isLight ? AppColors.lightTextSecondary : AppColors.darkTextSecondary,
          );
        }),
        elevation: isLight ? 1 : 0,
        surfaceTintColor: Colors.transparent,
      ),
      dividerTheme: DividerThemeData(
        color: colorScheme.outlineVariant,
        thickness: 1,
        space: 1,
      ),
      segmentedButtonTheme: SegmentedButtonThemeData(
        style: ButtonStyle(
          backgroundColor: WidgetStateProperty.resolveWith((states) {
            if (states.contains(WidgetState.selected)) {
              return accent.shade500;
            }
            return Colors.transparent;
          }),
          foregroundColor: WidgetStateProperty.resolveWith((states) {
            if (states.contains(WidgetState.selected)) {
              return Colors.white;
            }
            return colorScheme.onSurface;
          }),
          side: WidgetStateProperty.all(
            BorderSide(color: colorScheme.outlineVariant),
          ),
        ),
      ),
    );
  }
}
