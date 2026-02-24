import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

/// Code block typography using JetBrains Mono to match
/// the frontend's @font-mono variable.
class CodeTheme {
  CodeTheme._();

  static TextStyle codeStyle({
    double fontSize = 13,
    Color? color,
  }) {
    return GoogleFonts.jetBrainsMono(
      fontSize: fontSize,
      height: 1.5,
      color: color,
    );
  }

  static TextStyle inlineCode({Color? color, Color? backgroundColor}) {
    return GoogleFonts.jetBrainsMono(
      fontSize: 12.5,
      height: 1.4,
      color: color,
    );
  }
}
