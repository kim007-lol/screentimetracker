import 'dart:async';
import 'dart:math';

import 'package:flutter/material.dart';
import 'package:model_viewer_plus/model_viewer_plus.dart';
import 'package:webview_flutter/webview_flutter.dart';

import '../core/models/companion.dart';
import '../core/models/pet.dart';

/// Companion 3D (GLB) untuk Momo maupun Drako.
///
/// Model memakai skinning penuh: klip menggerakkan tulang, bukan node mesh.
/// Klip idle diputar berulang untuk Momo. Drako punya beberapa varian idle per
/// mood; widget memutar satu varian terus-menerus, lalu crossfade ke varian
/// lain setelah beberapa detik, jadi animasi tidak pernah membeku di antaranya.
/// Klip satu kali (tap, celebrate, elus, aksi spontan) memotong siklus itu dan
/// mengembalikannya setelah selesai. Perubahan klip dikirim lewat JavaScript
/// agar model tidak dimuat ulang.
class Companion3D extends StatefulWidget {
  const Companion3D({
    super.key,
    required this.pet,
    required this.stage,
    required this.mood,
    this.resting = false,
    this.height = 200,
    this.celebrateTick = 0,
    this.onTap,
    this.reactOnTap = true,
    this.living = true,
    this.greetOnLoad = false,
  });

  final PetFamily pet;
  final Stage stage;
  final Mood mood;

  /// Sleep outranks every other clip. Set from game state, never inferred.
  final bool resting;
  final double height;
  final int celebrateTick;
  final VoidCallback? onTap;
  final bool reactOnTap;

  /// Spontaneous state-aware actions (greet, look, wag, puff, bounce, walk,
  /// wing show). Sleep always outranks them.
  final bool living;

  /// Play one greeting after the model loads. At most once per widget life,
  /// so route rebuilds and tab switches do not re-trigger it.
  final bool greetOnLoad;

  @override
  State<Companion3D> createState() => _Companion3DState();
}

class _Companion3DState extends State<Companion3D> with WidgetsBindingObserver {
  static const _elementId = 'companion';

  WebViewController? _controller;
  Timer? _returnTimer;
  Timer? _loadFallback;
  Timer? _spontaneousTimer;
  Timer? _greetTimer;
  Timer? _idleTimer;
  final Random _random = Random();
  String? _lastSpontaneous;
  String? _idleCurrent;
  int _idleIndex = -1;
  int _tapCount = 0;
  bool _idleLooping = false;
  bool _greeted = false;
  bool _loaded = false;
  bool _oneShotActive = false;
  bool _foreground = true;
  bool _tickerEnabled = true;
  bool _routeCurrent = true;

  /// Camera azimuth in degrees. The user drags horizontally to inspect the
  /// pet from any side; elevation and radius stay at the stage preset so the
  /// pet never flips upside down or leaves its circle.
  static const double _orbitDegreesPerPixel = 0.8;
  double _orbitAzimuth = 0;
  String _orbitPhi = '82deg';
  String _orbitRadius = '4.8m';

  PetProfile get _profile => widget.pet.profile;
  bool get _active => _foreground && _tickerEnabled && _routeCurrent;
  bool get _resting => widget.resting;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    final lifecycle = WidgetsBinding.instance.lifecycleState;
    _foreground = lifecycle == null || lifecycle == AppLifecycleState.resumed;
    _resetOrbit();
    _armFallback();
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _tickerEnabled = TickerMode.of(context);
    // isCurrent also changes for non-opaque routes such as dialogs.
    _routeCurrent = ModalRoute.isCurrentOf(context) ?? true;
    _syncPlayback();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    _foreground = state == AppLifecycleState.resumed;
    _syncPlayback();
  }

  /// [forceIdle] is used when the controller arrives after the first build:
  /// idle may already be armed, but its script has not reached the model yet.
  void _syncPlayback({bool forceIdle = false}) {
    if (!_active) {
      _cancelPlayback();
      _run("var v=document.getElementById('$_elementId');if(v){v.pause();}");
      return;
    }
    if (!_oneShotActive) _startIdle(force: forceIdle);
    _scheduleSpontaneous();
    _scheduleGreeting();
  }

  /// A hidden, sleeping, or replaced pet must not keep a timer that could
  /// wake it on another route.
  void _cancelPlayback() {
    _returnTimer?.cancel();
    _returnTimer = null;
    _spontaneousTimer?.cancel();
    _spontaneousTimer = null;
    _greetTimer?.cancel();
    _greetTimer = null;
    _idleTimer?.cancel();
    _idleTimer = null;
    _oneShotActive = false;
    _idleCurrent = null;
    _idleLooping = false;
  }

  /// Bila event load tidak pernah datang, poster tetap dilepas agar UI tidak macet.
  void _armFallback() {
    _loadFallback?.cancel();
    _loadFallback = Timer(const Duration(seconds: 8), () {
      if (mounted && !_loaded) setState(() => _loaded = true);
    });
  }

  @override
  void didUpdateWidget(covariant Companion3D old) {
    super.didUpdateWidget(old);
    if (old.pet != widget.pet || old.stage != widget.stage) {
      _loaded = false;
      _controller = null;
      _cancelPlayback();
      _resetOrbit();
      _armFallback();
      return;
    }
    if (old.mood != widget.mood || old.resting != widget.resting) {
      // A mood or sleep change replaces any one-shot immediately: sleep must
      // never finish a tap or celebration in the background.
      _cancelPlayback();
      if (_active) {
        _startIdle(force: true);
        _scheduleSpontaneous();
        _scheduleGreeting();
      }
      return;
    }
    if (old.celebrateTick != widget.celebrateTick) {
      if (!_resting) {
        final clip = _profile.celebrateClip;
        _playOneShot(clip, _profile.durationOf(widget.stage, clip));
      }
    } else if (old.living != widget.living) {
      if (widget.living) {
        _scheduleSpontaneous();
      } else {
        _spontaneousTimer?.cancel();
        _spontaneousTimer = null;
      }
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _run("var v=document.getElementById('$_elementId');if(v){v.pause();}");
    _cancelPlayback();
    _loadFallback?.cancel();
    super.dispose();
  }

  void _run(String js) {
    _controller?.runJavaScript(js).catchError((Object _) {});
  }

  /// Read the stage preset once; only its azimuth is user-controlled.
  void _resetOrbit() {
    final parts = _profile.look(widget.stage).cameraOrbit.trim().split(
          RegExp(r'\s+'),
        );
    _orbitAzimuth = _angleOf(parts.first);
    _orbitPhi = parts.length > 1 ? parts[1] : '82deg';
    _orbitRadius = parts.length > 2 ? parts[2] : '4.8m';
  }

  static double _angleOf(String token) =>
      double.tryParse(token.replaceAll('deg', '')) ?? 0;

  String get _orbitValue {
    final wrapped = ((_orbitAzimuth % 360) + 360) % 360;
    return '${wrapped.toStringAsFixed(1)}deg $_orbitPhi $_orbitRadius';
  }

  void _applyOrbit() {
    _run(
      "var v=document.getElementById('$_elementId');"
      "if(v){v.cameraOrbit='$_orbitValue';"
      "if(v.jumpCameraToGoal)v.jumpCameraToGoal();}",
    );
  }

  void _handleOrbitDrag(DragUpdateDetails details) {
    _orbitAzimuth =
        (_orbitAzimuth + details.delta.dx * _orbitDegreesPerPixel) % 360;
    _applyOrbit();
  }

  void _playLoop(String clip) {
    if (!_active) return;
    _run(
      "var v=document.getElementById('$_elementId');"
      "if(v){v.animationName='$clip';v.play();}",
    );
  }

  /// Momo loops one idle clip. Drako cycles variants with a short breath
  /// between them, never repeating the same variant twice in a row.
  void _startIdle({bool force = false}) {
    if (!_active) return;
    if (_resting) {
      _idleTimer?.cancel();
      _idleTimer = null;
      if (force || _idleCurrent != _profile.sleepClip || !_idleLooping) {
        _idleCurrent = _profile.sleepClip;
        _idleLooping = true;
        _playLoop(_profile.sleepClip);
      }
      return;
    }
    final clips = _profile.idleClipsFor(widget.mood);
    if (clips.isEmpty) return;
    if (clips.length == 1) {
      _idleTimer?.cancel();
      _idleTimer = null;
      if (force || _idleCurrent != clips.first || !_idleLooping) {
        _idleCurrent = clips.first;
        _idleLooping = true;
        _playLoop(clips.first);
      }
      return;
    }
    if (!force && _idleTimer != null) return;
    _idleTimer?.cancel();
    _playIdleStep();
  }

  void _playIdleStep() {
    _idleTimer?.cancel();
    _idleTimer = null;
    if (!_active || _resting || _oneShotActive) return;
    final clips = _profile.idleClipsFor(widget.mood);
    if (clips.isEmpty) return;
    var index = _random.nextInt(clips.length);
    if (clips.length > 1 && index == _idleIndex) {
      index = (index + 1) % clips.length;
    }
    _idleIndex = index;
    final clip = clips[index];
    _idleCurrent = clip;
    _idleLooping = true;
    _playLoop(clip);
    // Loop the variant continuously; after the hold, crossfade to another one.
    // There is never a frozen gap between variants.
    final hold = PetBehavior.idleHold(family: widget.pet, random: _random);
    _idleTimer = Timer(hold, _playIdleStep);
  }

  void _playOneShot(
    String clip,
    Duration length, {
    VoidCallback? then,
  }) {
    if (!_active || _resting) return;
    _idleTimer?.cancel();
    _idleTimer = null;
    _idleCurrent = null;
    _idleLooping = false;
    _oneShotActive = true;
    _run(
      "var v=document.getElementById('$_elementId');"
      "if(v){v.animationName='$clip';v.play({repetitions:1});}",
    );
    _returnTimer?.cancel();
    _returnTimer = Timer(length, () {
      _oneShotActive = false;
      if (!mounted) return;
      if (_active) _startIdle(force: true);
      then?.call();
    });
  }

  /// One greeting per widget life, after the model has settled.
  void _scheduleGreeting() {
    if (_greeted || !widget.greetOnLoad || !_loaded) return;
    if (!_active || _resting || !mounted) return;
    _greeted = true;
    _greetTimer?.cancel();
    _greetTimer = Timer(const Duration(milliseconds: 1600), () {
      if (!mounted || !_active || _resting) return;
      final clip = _profile.greetClip;
      _playOneShot(
        clip,
        _profile.durationOf(widget.stage, clip),
        then: _scheduleSpontaneous,
      );
    });
  }

  void _scheduleSpontaneous() {
    _spontaneousTimer?.cancel();
    _spontaneousTimer = null;
    if (!widget.living || !_loaded || !_active || _resting) return;
    final delay = PetBehavior.nextDelay(
      family: widget.pet,
      mood: widget.mood,
      stage: widget.stage,
      random: _random,
    );
    _spontaneousTimer = Timer(delay, () {
      if (!mounted || !_active || _resting || _oneShotActive) {
        _scheduleSpontaneous();
        return;
      }
      final clip = PetBehavior.choose(
        family: widget.pet,
        mood: widget.mood,
        stage: widget.stage,
        previous: _lastSpontaneous,
        random: _random,
      );
      if (clip == null) {
        _scheduleSpontaneous();
        return;
      }
      _lastSpontaneous = clip;
      _playOneShot(
        clip,
        _profile.durationOf(widget.stage, clip),
        then: _scheduleSpontaneous,
      );
    });
  }

  void _handleTap() {
    if (widget.reactOnTap && !_resting) {
      final clip = PetBehavior.tapClip(
        family: widget.pet,
        resting: false,
        tapCount: _tapCount,
      );
      if (clip != null) {
        _tapCount++;
        _playOneShot(
          clip,
          _profile.durationOf(widget.stage, clip),
          then: _scheduleSpontaneous,
        );
      }
    }
    widget.onTap?.call();
  }

  void _handlePet() {
    final clip = PetBehavior.pettingClip(
      family: widget.pet,
      resting: _resting,
    );
    if (widget.reactOnTap && clip != null) {
      _playOneShot(
        clip,
        _profile.durationOf(widget.stage, clip),
        then: _scheduleSpontaneous,
      );
    }
  }

  void _onLoaded() {
    if (!mounted) return;
    _loadFallback?.cancel();
    if (!_loaded) setState(() => _loaded = true);
    _applyOrbit();
    _syncPlayback();
  }

  static const _bridgeJs = '''
(function(){
  var t=setInterval(function(){
    var v=document.getElementById('$_elementId');
    if(v){
      clearInterval(t);
      if(v.loaded){PetBridge.postMessage('loaded');}
      v.addEventListener('load',function(){PetBridge.postMessage('loaded');});
    }
  },50);
})();
''';

  IconData get _placeholderIcon => switch (widget.pet) {
    PetFamily.momo => Icons.pets_rounded,
    PetFamily.drako => Icons.local_fire_department_rounded,
  };

  @override
  Widget build(BuildContext context) {
    final primary = Theme.of(context).colorScheme.primary;
    final english = Localizations.localeOf(context).languageCode == 'en';
    final look = _profile.look(widget.stage);
    final initialClip = PetBehavior.baseClip(
      family: widget.pet,
      mood: widget.mood,
      resting: widget.resting,
    );
    final name = widget.pet.label;
    return SizedBox(
      height: widget.height,
      width: widget.height * 1.05,
      child: Stack(
        alignment: Alignment.center,
        children: [
          // Placeholder netral selama model dimuat. Tidak memakai potret PNG:
          // companion yang tampil selalu model GLB yang sama.
          Positioned.fill(
            child: AnimatedOpacity(
              opacity: _loaded ? 0 : 1,
              duration: const Duration(milliseconds: 350),
              child: Center(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(
                      _placeholderIcon,
                      size: widget.height * 0.24,
                      color: primary.withValues(alpha: 0.35),
                    ),
                    const SizedBox(height: 10),
                    TickerMode(
                      enabled: !_loaded,
                      child: SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(
                          strokeWidth: 2,
                          color: primary,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
          Positioned.fill(
            child: ModelViewer(
              key: ValueKey('${widget.pet.storageValue}-${widget.stage.name}'),
              id: _elementId,
              src: look.asset,
              alt: english
                  ? '$name, 3D companion'
                  : '$name, companion 3D',
              // Flutter visibility owns playback, including a late model load.
              autoPlay: false,
              animationName: initialClip,
              animationCrossfadeDuration: 250,
              // Framing differs per pet and stage; Drako's baby/teen heads sit
              // much higher than the adult silhouette.
              cameraOrbit: look.cameraOrbit,
              cameraTarget: look.cameraTarget,
              fieldOfView: '26deg',
              cameraControls: false,
              disableZoom: true,
              disablePan: true,
              disableTap: true,
              interactionPrompt: InteractionPrompt.none,
              loading: Loading.eager,
              reveal: Reveal.auto,
              shadowIntensity: 0.7,
              shadowSoftness: 0.8,
              exposure: 1.05,
              debugLogging: false,
              relatedJs: _bridgeJs,
              javascriptChannels: {
                JavascriptChannel(
                  'PetBridge',
                  onMessageReceived: (_) => _onLoaded(),
                ),
              },
              onWebViewCreated: (c) {
                if (!mounted) return;
                _controller = c;
                _syncPlayback(forceIdle: true);
              },
            ),
          ),
          // Lapisan sentuh di atas WebView supaya tap selalu terbaca.
          Positioned.fill(
            child: Semantics(
              button: true,
              label: english
                  ? 'Rotate, tap, or hold $name'
                  : 'Putar, sentuh, atau elus $name',
              hint: english
                  ? 'Drag sideways to rotate'
                  : 'Geser ke samping untuk memutar',
              onLongPress: _handlePet,
              child: GestureDetector(
                behavior: HitTestBehavior.opaque,
                onTap: _handleTap,
                onLongPress: _handlePet,
                onHorizontalDragUpdate: _handleOrbitDrag,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
