import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/date_symbol_data_local.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'core/state/app_state.dart';
import 'features/onboarding/onboarding_screen.dart';
import 'features/rest/rest_screen.dart';
import 'widgets/main_shell.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // intl butuh data locale sebelum DateFormat('EEEE, d MMMM', 'id_ID') dipakai.
  await initializeDateFormatting('id_ID');
  await initializeDateFormatting('en_US');

  final prefs = await SharedPreferences.getInstance();
  runApp(
    ProviderScope(
      overrides: [sharedPrefsProvider.overrideWithValue(prefs)],
      child: const ScreenTimeApp(),
    ),
  );
}

/// Akar aplikasi: tema aktif, bahasa pilihan pengguna, dan gerbang onboarding.
class ScreenTimeApp extends ConsumerStatefulWidget {
  const ScreenTimeApp({super.key});

  @override
  ConsumerState<ScreenTimeApp> createState() => _ScreenTimeAppState();
}

class _ScreenTimeAppState extends ConsumerState<ScreenTimeApp>
    with WidgetsBindingObserver {
  final GlobalKey<NavigatorState> _navigatorKey = GlobalKey<NavigatorState>();
  bool _active = true;
  bool _drainingAction = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) unawaited(_refreshEnvironment());
    });
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    final active = state == AppLifecycleState.resumed;
    if (active == _active) return;
    _active = active;
    if (active) {
      unawaited(_onResumed());
    } else {
      unawaited(ref.read(usageProvider.notifier).setForeground(false));
    }
  }

  Future<void> _onResumed() async {
    await ref.read(usageProvider.notifier).setForeground(true);
    if (mounted) await _refreshEnvironment();
  }

  /// Re-read permissions and drain a stale overlay action. The action is always
  /// consumed, but it can only open a flow the current consent still allows.
  Future<void> _refreshEnvironment() async {
    ref.invalidate(permissionStatusProvider);
    ref.read(gameProvider.notifier).ensureCurrentDay();
    if (_drainingAction) return;
    _drainingAction = true;
    try {
      final action = await ref
          .read(usageServiceProvider)
          .consumePendingAction();
      if (!mounted || action == null) return;
      final game = ref.read(gameProvider);
      if (!game.onboarded || !game.collectionEnabled) return;
      if (action == 'rest') {
        await _navigatorKey.currentState?.push<void>(
          MaterialPageRoute(builder: (_) => const RestScreen()),
        );
      }
    } catch (error) {
      debugPrint('Pending action failed: $error');
    } finally {
      _drainingAction = false;
    }
  }

  @override
  Widget build(BuildContext context) {
    final tokens = ref.watch(tokensProvider);
    final lang = ref.watch(gameProvider.select((s) => s.language));
    final onboarded = ref.watch(gameProvider.select((s) => s.onboarded));

    final overlayStyle = tokens.brightness == Brightness.dark
        ? SystemUiOverlayStyle.light
        : SystemUiOverlayStyle.dark;

    return MaterialApp(
      title: 'Screen Time Tracker',
      debugShowCheckedModeBanner: false,
      navigatorKey: _navigatorKey,
      theme: tokens.toThemeData(),
      locale: Locale(lang == 'en' ? 'en' : 'id'),
      supportedLocales: const [Locale('id'), Locale('en')],
      localizationsDelegates: const [
        GlobalMaterialLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
      ],
      builder: (context, child) => AnnotatedRegion<SystemUiOverlayStyle>(
        value: overlayStyle.copyWith(
          statusBarColor: Colors.transparent,
          systemNavigationBarColor: tokens.surface,
        ),
        child: child ?? const SizedBox.shrink(),
      ),
      home: onboarded ? const MainShell() : const OnboardingScreen(),
    );
  }
}
