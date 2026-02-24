import 'dart:ui';

/// All CachiBot colors ported from frontend/src/stores/ui.ts and
/// frontend/src/styles/theme.less + variables.less.
class AppColors {
  AppColors._();

  // ---------------------------------------------------------------------------
  // Light mode tokens (from theme.less :root)
  // ---------------------------------------------------------------------------
  static const lightBgApp = Color(0xFFF5F5F5);
  static const lightBgInset = Color(0xFFEFEFEF);
  static const lightBgDropdown = Color(0xFFFFFFFF);
  static const lightTextPrimary = Color(0xFF1A1A1A);
  static const lightTextSecondary = Color(0xFF808080);
  static const lightTextTertiary = Color(0xFFAAAAAA);
  static const lightCardBg = Color(0xFFFFFFFF);
  static const lightInputBg = Color(0xFFFFFFFF);
  static const lightCodeBg = Color(0x0A000000); // rgba(0,0,0,0.04)

  // Light borders
  static const lightBorderPrimary = Color(0x14000000); // rgba(0,0,0,0.08)
  static const lightBorderSecondary = Color(0x1F000000); // rgba(0,0,0,0.12)

  // Light interactive
  static const lightHoverBg = Color(0x0A000000); // rgba(0,0,0,0.04)
  static const lightActiveBg = Color(0x12000000); // rgba(0,0,0,0.07)

  // Light status
  static const lightSuccessText = Color(0xFF2E7D32);
  static const lightSuccessBg = Color(0x1A4CAF50); // rgba(76,175,80,0.10)
  static const lightWarningText = Color(0xFFF57F17);
  static const lightWarningBg = Color(0x1AD4A017); // rgba(212,160,23,0.10)
  static const lightDangerText = Color(0xFFC62828);
  static const lightDangerBg = Color(0x1AE57373); // rgba(229,115,115,0.10)
  static const lightInfoText = Color(0xFF1565C0);
  static const lightInfoBg = Color(0x1A64B5F6); // rgba(100,181,246,0.10)

  // ---------------------------------------------------------------------------
  // Dark mode tokens (from theme.less .dark)
  // ---------------------------------------------------------------------------
  static const darkBgApp = Color(0xFF050505);
  static const darkBgInset = Color(0xFF0A0A0A);
  static const darkBgDropdown = Color(0xFF1A1A1B);
  static const darkTextPrimary = Color(0xFFE8E8E8);
  static const darkTextSecondary = Color(0xFF808080);
  static const darkTextTertiary = Color(0xFF555555);
  static const darkCardBg = Color(0x0DFFFFFF); // rgba(255,255,255,0.05)
  static const darkInputBg = Color(0x0DFFFFFF); // rgba(255,255,255,0.05)
  static const darkCodeBg = Color(0x0FFFFFFF); // rgba(255,255,255,0.06)

  // Dark borders
  static const darkBorderPrimary = Color(0x14FFFFFF); // rgba(255,255,255,0.08)
  static const darkBorderSecondary = Color(0x1FFFFFFF); // rgba(255,255,255,0.12)

  // Dark interactive
  static const darkHoverBg = Color(0x0DFFFFFF); // rgba(255,255,255,0.05)
  static const darkActiveBg = Color(0x14FFFFFF); // rgba(255,255,255,0.08)

  // Dark status
  static const darkSuccessText = Color(0xFF4CAF50);
  static const darkSuccessBg = Color(0x1F4CAF50); // rgba(76,175,80,0.12)
  static const darkWarningText = Color(0xFFD4A017);
  static const darkWarningBg = Color(0x1FD4A017); // rgba(212,160,23,0.12)
  static const darkDangerText = Color(0xFFE57373);
  static const darkDangerBg = Color(0x1FE57373); // rgba(229,115,115,0.12)
  static const darkInfoText = Color(0xFF64B5F6);
  static const darkInfoBg = Color(0x1F64B5F6); // rgba(100,181,246,0.12)

  // ---------------------------------------------------------------------------
  // Zinc neutral palette (from variables.less)
  // ---------------------------------------------------------------------------
  static const zinc50 = Color(0xFFFAFAFA);
  static const zinc100 = Color(0xFFF4F4F5);
  static const zinc200 = Color(0xFFE4E4E7);
  static const zinc300 = Color(0xFFD4D4D8);
  static const zinc400 = Color(0xFFA1A1AA);
  static const zinc500 = Color(0xFF71717A);
  static const zinc600 = Color(0xFF52525B);
  static const zinc700 = Color(0xFF3F3F46);
  static const zinc800 = Color(0xFF27272A);
  static const zinc900 = Color(0xFF18181B);
  static const zinc950 = Color(0xFF09090B);
}

// =============================================================================
// Accent color palettes — exact port of frontend/src/stores/ui.ts lines 12-104
// =============================================================================

enum PresetColor {
  green,
  pink,
  blue,
  purple,
  orange,
  red,
  cyan,
  yellow,
  teal,
  indigo,
  rose,
  amber,
  lime,
}

class ColorPalette {
  const ColorPalette({
    required this.name,
    required this.shade50,
    required this.shade100,
    required this.shade200,
    required this.shade300,
    required this.shade400,
    required this.shade500,
    required this.shade600,
    required this.shade700,
    required this.shade800,
    required this.shade900,
    required this.shade950,
  });

  final String name;
  final Color shade50;
  final Color shade100;
  final Color shade200;
  final Color shade300;
  final Color shade400;
  final Color shade500;
  final Color shade600;
  final Color shade700;
  final Color shade800;
  final Color shade900;
  final Color shade950;

  Color operator [](int shade) {
    switch (shade) {
      case 50:
        return shade50;
      case 100:
        return shade100;
      case 200:
        return shade200;
      case 300:
        return shade300;
      case 400:
        return shade400;
      case 500:
        return shade500;
      case 600:
        return shade600;
      case 700:
        return shade700;
      case 800:
        return shade800;
      case 900:
        return shade900;
      case 950:
        return shade950;
      default:
        return shade500;
    }
  }
}

/// All 13 accent color palettes from the web app.
const Map<PresetColor, ColorPalette> accentColors = {
  PresetColor.green: ColorPalette(
    name: 'Green',
    shade50: Color(0xFFF0FDF4),
    shade100: Color(0xFFDCFCE7),
    shade200: Color(0xFFBBF7D0),
    shade300: Color(0xFF86EFAC),
    shade400: Color(0xFF4ADE80),
    shade500: Color(0xFF22C55E),
    shade600: Color(0xFF16A34A),
    shade700: Color(0xFF15803D),
    shade800: Color(0xFF166534),
    shade900: Color(0xFF14532D),
    shade950: Color(0xFF052E16),
  ),
  PresetColor.pink: ColorPalette(
    name: 'Pink',
    shade50: Color(0xFFFDF2F8),
    shade100: Color(0xFFFCE7F3),
    shade200: Color(0xFFFBCFE8),
    shade300: Color(0xFFF9A8D4),
    shade400: Color(0xFFF472B6),
    shade500: Color(0xFFEC4899),
    shade600: Color(0xFFDB2777),
    shade700: Color(0xFFBE185D),
    shade800: Color(0xFF9D174D),
    shade900: Color(0xFF831843),
    shade950: Color(0xFF500724),
  ),
  PresetColor.blue: ColorPalette(
    name: 'Blue',
    shade50: Color(0xFFEFF6FF),
    shade100: Color(0xFFDBEAFE),
    shade200: Color(0xFFBFDBFE),
    shade300: Color(0xFF93C5FD),
    shade400: Color(0xFF60A5FA),
    shade500: Color(0xFF3B82F6),
    shade600: Color(0xFF2563EB),
    shade700: Color(0xFF1D4ED8),
    shade800: Color(0xFF1E40AF),
    shade900: Color(0xFF1E3A8A),
    shade950: Color(0xFF172554),
  ),
  PresetColor.purple: ColorPalette(
    name: 'Purple',
    shade50: Color(0xFFFAF5FF),
    shade100: Color(0xFFF3E8FF),
    shade200: Color(0xFFE9D5FF),
    shade300: Color(0xFFD8B4FE),
    shade400: Color(0xFFC084FC),
    shade500: Color(0xFFA855F7),
    shade600: Color(0xFF9333EA),
    shade700: Color(0xFF7C3AED),
    shade800: Color(0xFF6B21A8),
    shade900: Color(0xFF581C87),
    shade950: Color(0xFF3B0764),
  ),
  PresetColor.orange: ColorPalette(
    name: 'Orange',
    shade50: Color(0xFFFFF7ED),
    shade100: Color(0xFFFFEDD5),
    shade200: Color(0xFFFED7AA),
    shade300: Color(0xFFFDBA74),
    shade400: Color(0xFFFB923C),
    shade500: Color(0xFFF97316),
    shade600: Color(0xFFEA580C),
    shade700: Color(0xFFC2410C),
    shade800: Color(0xFF9A3412),
    shade900: Color(0xFF7C2D12),
    shade950: Color(0xFF431407),
  ),
  PresetColor.red: ColorPalette(
    name: 'Red',
    shade50: Color(0xFFFEF2F2),
    shade100: Color(0xFFFEE2E2),
    shade200: Color(0xFFFECACA),
    shade300: Color(0xFFFCA5A5),
    shade400: Color(0xFFF87171),
    shade500: Color(0xFFEF4444),
    shade600: Color(0xFFDC2626),
    shade700: Color(0xFFB91C1C),
    shade800: Color(0xFF991B1B),
    shade900: Color(0xFF7F1D1D),
    shade950: Color(0xFF450A0A),
  ),
  PresetColor.cyan: ColorPalette(
    name: 'Cyan',
    shade50: Color(0xFFECFEFF),
    shade100: Color(0xFFCFFAFE),
    shade200: Color(0xFFA5F3FC),
    shade300: Color(0xFF67E8F9),
    shade400: Color(0xFF22D3EE),
    shade500: Color(0xFF06B6D4),
    shade600: Color(0xFF0891B2),
    shade700: Color(0xFF0E7490),
    shade800: Color(0xFF155E75),
    shade900: Color(0xFF164E63),
    shade950: Color(0xFF083344),
  ),
  PresetColor.yellow: ColorPalette(
    name: 'Yellow',
    shade50: Color(0xFFFEFCE8),
    shade100: Color(0xFFFEF9C3),
    shade200: Color(0xFFFEF08A),
    shade300: Color(0xFFFDE047),
    shade400: Color(0xFFFACC15),
    shade500: Color(0xFFEAB308),
    shade600: Color(0xFFCA8A04),
    shade700: Color(0xFFA16207),
    shade800: Color(0xFF854D0E),
    shade900: Color(0xFF713F12),
    shade950: Color(0xFF422006),
  ),
  PresetColor.teal: ColorPalette(
    name: 'Teal',
    shade50: Color(0xFFF0FDFA),
    shade100: Color(0xFFCCFBF1),
    shade200: Color(0xFF99F6E4),
    shade300: Color(0xFF5EEAD4),
    shade400: Color(0xFF2DD4BF),
    shade500: Color(0xFF14B8A6),
    shade600: Color(0xFF0D9488),
    shade700: Color(0xFF0F766E),
    shade800: Color(0xFF115E59),
    shade900: Color(0xFF134E4A),
    shade950: Color(0xFF042F2E),
  ),
  PresetColor.indigo: ColorPalette(
    name: 'Indigo',
    shade50: Color(0xFFEEF2FF),
    shade100: Color(0xFFE0E7FF),
    shade200: Color(0xFFC7D2FE),
    shade300: Color(0xFFA5B4FC),
    shade400: Color(0xFF818CF8),
    shade500: Color(0xFF6366F1),
    shade600: Color(0xFF4F46E5),
    shade700: Color(0xFF4338CA),
    shade800: Color(0xFF3730A3),
    shade900: Color(0xFF312E81),
    shade950: Color(0xFF1E1B4B),
  ),
  PresetColor.rose: ColorPalette(
    name: 'Rose',
    shade50: Color(0xFFFFF1F2),
    shade100: Color(0xFFFFE4E6),
    shade200: Color(0xFFFECDD3),
    shade300: Color(0xFFFDA4AF),
    shade400: Color(0xFFFB7185),
    shade500: Color(0xFFF43F5E),
    shade600: Color(0xFFE11D48),
    shade700: Color(0xFFBE123C),
    shade800: Color(0xFF9F1239),
    shade900: Color(0xFF881337),
    shade950: Color(0xFF4C0519),
  ),
  PresetColor.amber: ColorPalette(
    name: 'Amber',
    shade50: Color(0xFFFFFBEB),
    shade100: Color(0xFFFEF3C7),
    shade200: Color(0xFFFDE68A),
    shade300: Color(0xFFFCD34D),
    shade400: Color(0xFFFBBF24),
    shade500: Color(0xFFF59E0B),
    shade600: Color(0xFFD97706),
    shade700: Color(0xFFB45309),
    shade800: Color(0xFF92400E),
    shade900: Color(0xFF78350F),
    shade950: Color(0xFF451A03),
  ),
  PresetColor.lime: ColorPalette(
    name: 'Lime',
    shade50: Color(0xFFF7FEE7),
    shade100: Color(0xFFECFCCB),
    shade200: Color(0xFFD9F99D),
    shade300: Color(0xFFBEF264),
    shade400: Color(0xFFA3E635),
    shade500: Color(0xFF84CC16),
    shade600: Color(0xFF65A30D),
    shade700: Color(0xFF4D7C0F),
    shade800: Color(0xFF3F6212),
    shade900: Color(0xFF365314),
    shade950: Color(0xFF1A2E05),
  ),
};
