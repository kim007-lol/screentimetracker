// Momo GLB controller, Flutter
// Pakai package model_viewer_plus (web view) atau flutter_3d_controller
// yang mendukung pemilihan animationName di file .glb.
// Klip di dalam .glb, nama persis, sudah diverifikasi:
// idle_fresh, idle_tired, idle_critical, sleep, tap_reaction, celebrate
// Loop vs one-shot diatur di pemutar, bukan di file .glb:
// idle_fresh, idle_tired, idle_critical, sleep = loop
// tap_reaction, celebrate = one-shot, lalu kembali ke idle aktif

String momoGlbForStage(int stage) {
  switch (stage) {
    case 1: return 'assets/3d/momo_bayi.glb';
    case 2: return 'assets/3d/momo_remaja.glb';
    case 3: return 'assets/3d/momo_dewasa.glb';
    default: return 'assets/3d/momo_bayi.glb';
  }
}

String momoClipForHp({required double hp, required bool isResting}) {
  if (isResting) return 'sleep';
  if (hp < 30) return 'idle_critical';
  if (hp <= 60) return 'idle_tired';
  return 'idle_fresh';
}

// Contoh pemakaian dengan model_viewer_plus:
// ModelViewer(
//   src: momoGlbForStage(stage),
//   animationName: isTapped ? 'tap_reaction' : momoClipForHp(hp: hp, isResting: isResting),
//   autoRotate: false,
// )
// Saat tap: set animationName = 'tap_reaction', lalu setelah 0.8 detik
// kembalikan ke momoClipForHp(). Saat naik stage atau selesai misi:
// animationName = 'celebrate', lalu setelah 1.8 detik kembali ke idle.
// Perbedaan gaya per tahap sudah tertanam di klipnya:
// Bayi: idle_fresh lebih lambat dan canggung, goyangan 2.4 detik
// Remaja: idle_fresh lincah 2.0 detik, tap_reaction lompat lebih tinggi
// Dewasa: idle_fresh tenang 3.0 detik, gerak lebih halus dan kecil

// Per-joint control (v2 rig, bukan root saja):
// Three.js: gltf.scene.getObjectByName('Ear_L').rotation.z += 0.35;
// Three.js: gltf.scene.getObjectByName('Tail_3').rotation.y += 0.35;
// Unity: transform.Find('Root/Hips/Spine/Chest/Neck/Head/Ear_L')
// Unity: transform.Find('Root/Hips/Tail_1/Tail_2/Tail_3')
// Joint names persis ada di momo_3d.rig v2, 22 joint per model.
