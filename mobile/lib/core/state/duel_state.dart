import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/duel_snapshot.dart';
import 'app_state.dart';

/// Menyimpan maksimal 5 kode duel teman di perangkat. Tidak ada akun,
/// tidak ada server, dan tidak ada data app detail yang ikut dibagikan.
class DuelNotifier extends Notifier<List<DuelSnapshot>> {
  static const _key = 'duelPeers';

  @override
  List<DuelSnapshot> build() {
    final prefs = ref.read(sharedPrefsProvider);
    final raw = prefs.getStringList(_key) ?? const <String>[];
    final peers = <String, DuelSnapshot>{};
    for (final code in raw) {
      final peer = DuelSnapshot.tryDecode(code);
      if (peer == null) continue;
      peers.remove(peer.name);
      peers[peer.name] = peer;
      if (peers.length > maxPeers) peers.remove(peers.keys.first);
    }
    return peers.values.toList();
  }

  static const maxPeers = 5;

  /// Invalid code or full board returns false; existing names can be updated.
  /// Never silently evict a friend to add another.
  bool addCode(String code) {
    final snapshot = DuelSnapshot.tryDecode(code);
    if (snapshot == null) return false;
    if (state.length >= maxPeers &&
        !state.any((peer) => peer.name == snapshot.name)) {
      return false;
    }
    final next = [
      ...state.where((peer) => peer.name != snapshot.name),
      snapshot,
    ];
    _persist(next);
    state = next;
    return true;
  }

  void remove(String name) {
    final next = state.where((peer) => peer.name != name).toList();
    _persist(next);
    state = next;
  }

  void clear() {
    ref.read(sharedPrefsProvider).remove(_key);
    state = const [];
  }

  void _persist(List<DuelSnapshot> peers) {
    ref
        .read(sharedPrefsProvider)
        .setStringList(_key, peers.map((peer) => peer.encode()).toList());
  }
}

final duelPeersProvider = NotifierProvider<DuelNotifier, List<DuelSnapshot>>(
  DuelNotifier.new,
);
