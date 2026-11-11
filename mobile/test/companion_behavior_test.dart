import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:model_viewer_plus/model_viewer_plus.dart';
import 'package:screentime_companion/core/models/companion.dart';
import 'package:screentime_companion/core/models/pet.dart';
import 'package:screentime_companion/widgets/companion_3d.dart';
import 'package:webview_flutter/webview_flutter.dart';

import 'lifecycle_webview_fake.dart';

void main() {
  Future<(LifecycleWebViewPlatform, ModelViewer)> pumpCompanion(
    WidgetTester tester, {
    PetFamily pet = PetFamily.momo,
    Stage stage = Stage.bayi,
    Mood mood = Mood.segar,
    bool resting = false,
    bool greetOnLoad = false,
    bool living = true,
    VoidCallback? onTap,
  }) async {
    final platform = LifecycleWebViewPlatform();
    WebViewPlatform.instance = platform;
    await tester.pumpWidget(MaterialApp(
      home: Scaffold(
        body: Center(
          child: Companion3D(
            pet: pet,
            stage: stage,
            mood: mood,
            resting: resting,
            greetOnLoad: greetOnLoad,
            living: living,
            onTap: onTap,
          ),
        ),
      ),
    ));
    final model = tester.widget<ModelViewer>(find.byType(ModelViewer));
    final controller = WebViewController();
    model.onWebViewCreated!(controller);
    model.javascriptChannels!.single.onMessageReceived(
      const JavaScriptMessage(message: 'loaded'),
    );
    await tester.pump();
    return (platform, model);
  }

  for (final pet in PetFamily.values) {
    testWidgets('${pet.label}: sleep blocks tap reactions but keeps onTap',
        (tester) async {
      var taps = 0;
      final platform = LifecycleWebViewPlatform();
      WebViewPlatform.instance = platform;
      await tester.pumpWidget(MaterialApp(
        home: Scaffold(
          body: Center(
            child: Companion3D(
              pet: pet,
              stage: Stage.bayi,
              mood: Mood.segar,
              resting: true,
              onTap: () => taps++,
            ),
          ),
        ),
      ));
      final model = tester.widget<ModelViewer>(find.byType(ModelViewer));
      model.onWebViewCreated!(WebViewController());
      model.javascriptChannels!.single.onMessageReceived(
        const JavaScriptMessage(message: 'loaded'),
      );
      await tester.pump();
      platform.scripts.clear();

      await tester.tap(find.byType(Companion3D));
      await tester.pump();
      expect(taps, 1);
      expect(
        platform.scripts.where((s) =>
            s.contains('tap_reaction') || s.contains('wing_show')),
        isEmpty,
      );
      await tester.pumpWidget(const SizedBox.shrink());
    });

    testWidgets('${pet.label}: celebrate is ignored while sleeping',
        (tester) async {
      late StateSetter update;
      var tick = 0;
      final platform = LifecycleWebViewPlatform();
      WebViewPlatform.instance = platform;
      await tester.pumpWidget(MaterialApp(
        home: Scaffold(
          body: StatefulBuilder(
            builder: (context, setState) {
              update = setState;
              return Companion3D(
                pet: pet,
                stage: Stage.bayi,
                mood: Mood.segar,
                resting: true,
                celebrateTick: tick,
              );
            },
          ),
        ),
      ));
      final model = tester.widget<ModelViewer>(find.byType(ModelViewer));
      model.onWebViewCreated!(WebViewController());
      model.javascriptChannels!.single.onMessageReceived(
        const JavaScriptMessage(message: 'loaded'),
      );
      await tester.pump();
      platform.scripts.clear();
      tick = 1;
      update(() {});
      await tester.pump();
      expect(
        platform.scripts.where((s) => s.contains('celebrate')),
        isEmpty,
      );
      await tester.pumpWidget(const SizedBox.shrink());
    });
  }

  testWidgets('entering sleep cancels an active one-shot immediately',
      (tester) async {
    late StateSetter update;
    var resting = false;
    final platform = LifecycleWebViewPlatform();
    WebViewPlatform.instance = platform;
    await tester.pumpWidget(MaterialApp(
      home: Scaffold(
        body: StatefulBuilder(
          builder: (context, setState) {
            update = setState;
            return Companion3D(
              pet: PetFamily.momo,
              stage: Stage.bayi,
              mood: Mood.segar,
              resting: resting,
            );
          },
        ),
      ),
    ));
    final model = tester.widget<ModelViewer>(find.byType(ModelViewer));
    model.onWebViewCreated!(WebViewController());
    model.javascriptChannels!.single.onMessageReceived(
      const JavaScriptMessage(message: 'loaded'),
    );
    await tester.pump();

    await tester.tap(find.byType(Companion3D));
    await tester.pump();
    expect(platform.scripts.last, contains('tap_reaction'));

    resting = true;
    update(() {});
    await tester.pump();
    expect(platform.scripts.last, contains("animationName='sleep'"));
    expect(platform.scripts.last, contains('v.play()'));

    platform.scripts.clear();
    await tester.pump(const Duration(seconds: 3));
    expect(
      platform.scripts.where((s) => s.contains('idle_fresh') || s.contains('walk')),
      isEmpty,
    );
    await tester.pumpWidget(const SizedBox.shrink());
  });

  testWidgets('Momo greeting plays once after load and not on repeat load',
      (tester) async {
    final (platform, model) = await pumpCompanion(
      tester,
      greetOnLoad: true,
      living: false,
    );
    platform.scripts.clear();
    await tester.pump(const Duration(milliseconds: 1600));
    expect(
      platform.scripts.where((s) => s.contains("animationName='greet'")),
      hasLength(1),
    );

    await tester.pump(const Duration(milliseconds: 2200));
    platform.scripts.clear();
    model.javascriptChannels!.single.onMessageReceived(
      const JavaScriptMessage(message: 'loaded'),
    );
    await tester.pump(const Duration(milliseconds: 1600));
    expect(
      platform.scripts.where((s) => s.contains("animationName='greet'")),
      isEmpty,
    );
    await tester.pumpWidget(const SizedBox.shrink());
  });

  testWidgets('living Momo eventually chooses a spontaneous rig clip',
      (tester) async {
    final (platform, _) = await pumpCompanion(tester);
    platform.scripts.clear();
    await tester.pump(const Duration(seconds: 22));
    expect(
      platform.scripts.where((s) =>
          s.contains("animationName='greet'") ||
          s.contains("animationName='look_around'") ||
          s.contains("animationName='groom'") ||
          s.contains("animationName='stretch'") ||
          s.contains("animationName='walk'")),
      isNotEmpty,
    );
    await tester.pumpWidget(const SizedBox.shrink());
  });

  testWidgets('living Drako eventually chooses a spontaneous rig clip',
      (tester) async {
    final (platform, _) = await pumpCompanion(
      tester,
      pet: PetFamily.drako,
    );
    platform.scripts.clear();
    await tester.pump(const Duration(seconds: 22));
    final vocabulary = PetBehavior.weightsFor(
      family: PetFamily.drako,
      mood: Mood.segar,
      stage: Stage.bayi,
    ).keys;
    expect(
      platform.scripts.where(
        (s) => vocabulary.any((clip) => s.contains("animationName='$clip'")),
      ),
      isNotEmpty,
    );
    await tester.pumpWidget(const SizedBox.shrink());
  });

  testWidgets('Drako idle loops a variant then crossfades to another',
      (tester) async {
    final (platform, _) = await pumpCompanion(
      tester,
      pet: PetFamily.drako,
      stage: Stage.dewasa,
      living: false,
    );
    final firstScript = platform.scripts.lastWhere(
      (s) => s.contains("animationName='"),
    );
    final firstClip = RegExp(r"animationName='([^']+)'")
        .firstMatch(firstScript)!
        .group(1)!;
    expect(
      PetRegistry.drako.idleClipsFor(Mood.segar),
      contains(firstClip),
    );
    // The variant loops for the whole hold; no one-shot freeze at its end.
    expect(firstScript, contains('v.play()'));
    expect(firstScript, isNot(contains('repetitions:1')));

    final duration =
        PetRegistry.drako.durationOf(Stage.dewasa, firstClip);
    platform.scripts.clear();
    await tester.pump(duration);
    expect(
      platform.scripts.where((s) => s.contains("animationName='idle_")),
      isEmpty,
    );
    // The hold is 6-12 s, so a different variant arrives after that window.
    await tester.pump(const Duration(seconds: 13));
    final secondScripts = platform.scripts
        .where((s) => s.contains("animationName='idle_"))
        .toList();
    expect(secondScripts, isNotEmpty);
    final secondClip = RegExp(r"animationName='([^']+)'")
        .firstMatch(secondScripts.first)!
        .group(1)!;
    expect(secondClip, isNot(firstClip));
    expect(
      PetRegistry.drako.idleClipsFor(Mood.segar),
      contains(secondClip),
    );
    await tester.pumpWidget(const SizedBox.shrink());
  });

  testWidgets('Drako alternates a quick tap reaction with a wing show',
      (tester) async {
    final (platform, _) = await pumpCompanion(
      tester,
      pet: PetFamily.drako,
      living: false,
    );
    platform.scripts.clear();

    await tester.tap(find.byType(Companion3D));
    await tester.pump();
    expect(platform.scripts.last, contains("animationName='tap_reaction'"));

    await tester.pump(const Duration(milliseconds: 800));
    platform.scripts.clear();
    await tester.tap(find.byType(Companion3D));
    await tester.pump();
    expect(platform.scripts.last, contains("animationName='wing_show'"));
    expect(platform.scripts.last, contains('v.play({repetitions:1})'));
    await tester.pumpWidget(const SizedBox.shrink());
  });

  testWidgets('Drako greet plays once after load', (tester) async {
    final (platform, _) = await pumpCompanion(
      tester,
      pet: PetFamily.drako,
      greetOnLoad: true,
      living: false,
    );
    platform.scripts.clear();
    await tester.pump(const Duration(milliseconds: 1600));
    expect(
      platform.scripts.where((s) => s.contains("animationName='greet'")),
      hasLength(1),
    );
    await tester.pumpWidget(const SizedBox.shrink());
  });

  for (final pet in PetFamily.values) {
    testWidgets('${pet.label}: horizontal drag rotates the pet', (tester) async {
      final (platform, _) = await pumpCompanion(tester, pet: pet, living: false);
      platform.scripts.clear();

      await tester.drag(find.byType(Companion3D), const Offset(-140, 0));
      await tester.pump();

      final orbits = platform.scripts
          .where((s) => s.contains('v.cameraOrbit='))
          .toList();
      expect(orbits, isNotEmpty);
      expect(orbits.last, contains('jumpCameraToGoal'));
      expect(orbits.last, isNot(contains("v.cameraOrbit='0.0deg")));
      // A drag must not fire a tap reaction.
      expect(
        platform.scripts.where((s) => s.contains("animationName='tap_")),
        isEmpty,
      );
      await tester.pumpWidget(const SizedBox.shrink());
    });
  }

  testWidgets('tap still reacts after the pet is rotated', (tester) async {
    final (platform, _) = await pumpCompanion(
      tester,
      pet: PetFamily.drako,
      living: false,
    );
    await tester.drag(find.byType(Companion3D), const Offset(-120, 0));
    await tester.pump();
    platform.scripts.clear();

    await tester.tap(find.byType(Companion3D));
    await tester.pump();
    expect(platform.scripts.last, contains("animationName='tap_reaction'"));
    await tester.pumpWidget(const SizedBox.shrink());
  });
}
