import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:model_viewer_plus/model_viewer_plus.dart';
import 'package:screentime_companion/core/models/companion.dart';
import 'package:screentime_companion/core/models/pet.dart';
import 'package:screentime_companion/widgets/companion_3d.dart';
import 'package:webview_flutter/webview_flutter.dart';

import 'lifecycle_webview_fake.dart';

void main() {
  for (final pet in PetFamily.values) {
    testWidgets(
        '${pet.label}: pauses for inactive tab, app background, and covered route',
        (tester) async {
      final controller = LifecycleWebViewPlatform();
      WebViewPlatform.instance = controller;
      final navigator = GlobalKey<NavigatorState>();
      var enabled = true;
      late StateSetter update;
      await tester.pumpWidget(MaterialApp(
        navigatorKey: navigator,
        home: StatefulBuilder(builder: (context, setState) {
          update = setState;
          return TickerMode(
            enabled: enabled,
            child: Companion3D(
              pet: pet,
              stage: Stage.bayi,
              mood: Mood.segar,
            ),
          );
        }),
      ));
      final model = tester.widget<ModelViewer>(find.byType(ModelViewer));
      model.onWebViewCreated!(WebViewController());
      model.javascriptChannels!.single.onMessageReceived(
        const JavaScriptMessage(message: 'loaded'),
      );
      await tester.pump();
      controller.scripts.clear();

      update(() => enabled = false);
      await tester.pump();
      expect(controller.scripts.last, contains('v.pause()'));

      controller.scripts.clear();
      // A late load event must not restart a hidden animation.
      model.javascriptChannels!.single.onMessageReceived(
        const JavaScriptMessage(message: 'loaded'),
      );
      await tester.pump();
      expect(
        controller.scripts.where((s) => s.contains('v.play(')),
        isEmpty,
      );

      update(() => enabled = true);
      await tester.pump();
      expect(controller.scripts.last, contains('v.play('));

      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
      await tester.pump();
      expect(controller.scripts.last, contains('v.pause()'));

      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
      await tester.pump();
      expect(controller.scripts.last, contains('v.play('));

      showDialog<void>(
        context: navigator.currentContext!,
        builder: (_) => const AlertDialog(content: Text('Cover')),
      );
      await tester.pump();
      expect(controller.scripts.last, contains('v.pause()'));

      navigator.currentState!.pop();
      await tester.pump(const Duration(milliseconds: 400));
      expect(controller.scripts.last, contains('v.play('));
      await tester.pumpWidget(const SizedBox.shrink());
    });
  }
}
