import 'package:cachibot_mobile/widgets/common/boot_screen.dart';
import 'package:cachibot_mobile/widgets/common/loading.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('CachiSpinner renders with a Loading semantics label',
      (WidgetTester tester) async {
    tester.ensureSemantics();
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(body: Center(child: CachiSpinner())),
      ),
    );

    expect(find.byType(CachiSpinner), findsOneWidget);
    expect(find.bySemanticsLabel('Loading'), findsOneWidget);
  });

  testWidgets('CachiSpinner with delayMs hides then shows',
      (WidgetTester tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: Center(child: CachiSpinner(delayMs: 100)),
        ),
      ),
    );

    // Before the delay the ring is not painted, but the space is held.
    expect(find.byType(CachiSpinner), findsOneWidget);
    expect(find.byType(CustomPaint), findsNothing);

    await tester.pump(const Duration(milliseconds: 150));

    expect(find.byType(CustomPaint), findsOneWidget);
  });

  testWidgets('CachiSkeleton renders placeholder blocks',
      (WidgetTester tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: CachiSkeleton(width: 120, height: 12),
        ),
      ),
    );

    expect(find.byType(CachiSkeleton), findsOneWidget);
  });

  testWidgets('CachiSkeletonList renders generic rows',
      (WidgetTester tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(body: CachiSkeletonList(itemCount: 3)),
      ),
    );

    expect(find.byType(CachiSkeletonList), findsOneWidget);
    expect(find.byType(CachiSkeleton), findsWidgets);
  });

  testWidgets('BootScreen shows the wordmark, spinner and status',
      (WidgetTester tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: BootScreen(status: 'Restoring session...'),
      ),
    );

    expect(find.text('Cachi'), findsOneWidget);
    expect(find.text('Bot'), findsOneWidget);
    expect(find.text('Restoring session...'), findsOneWidget);
    expect(find.byType(CachiSpinner), findsOneWidget);
  });
}
