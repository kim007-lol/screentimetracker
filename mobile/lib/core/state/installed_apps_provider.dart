import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'app_state.dart';

/// Aplikasi yang punya ikon launcher di perangkat ini. Tidak memerlukan izin
/// akses pemakaian; hanya PackageManager.
final installedAppsProvider =
    FutureProvider.autoDispose<List<Map<String, String>>>(
      (ref) => ref.read(usageServiceProvider).installedApps(),
    );
