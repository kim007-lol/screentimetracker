# Momo GLB: rig 22 joint dan animasi lokal

## Status file

Setiap `momo_*.glb` berisi satu skin dengan 22 joint: Root, Hips, Spine, Chest,
Neck, Head, Ear_L/R, Arm_L/Forearm_L/Paw_L, Arm_R/Forearm_R/Paw_R, Leg/Foot L/R,
Tail_1..3 + Tail_Tip, plus dua node morph kelopak mata (Blink_L/R). Total 25 node,
3 mesh, 1 skin.

## Klip di setiap file

| Klip | Durasi | Untuk | Ciri |
| --- | --- | --- | --- |
| `idle_fresh` | 8 s, loop | HP > 60 | telinga berkedut, ekor bergoyang, tangan kanan melambai kecil, kedip, kepala miring tipis |
| `idle_tired` | 8 s, loop | HP 30-60 | postur membungkuk, telinga terkulai, ekor lambat, kedip lebih lama, satu tangan terangkat pelan |
| `idle_critical` | 3 s, loop | HP < 30 | postur meringkuk, ekor hampir diam, telinga menegang, kedip cepat, tangan kanan gemetar kecil |
| `sleep` | 8 s, loop | mode istirahat | mata tertutup, tubuh paling rendah, ekor dan telinga nyaris diam |
| `tap_reaction` | 1 s, one-shot | layar disentuh | tangan kanan + lengan + paw terangkat 22°/10°/14°, telinga naik, kedip kejut |
| `celebrate` | 2 s, one-shot | naik level / misi | lompat dan putar 360°, tidak diubah oleh rework |
| `greet` | 2 s, one-shot | pill baru tampil, lalu spontan | kepala menengadah dan mengangguk, telinga tegak, ekor bergoyang, satu kedip |
| `look_around` | 3 s, one-shot | spontan saat tenang | menoleh kiri, jeda, menoleh kanan, kembali; telinga mengikuti, ekor bergoyang |
| `groom` | 3,2 s, one-shot | spontan, lebih sering saat bayi | kepala menunduk ke paw kanan yang diam, dua kali usap, mata setengah tertutup |
| `stretch` | 2,6 s, one-shot | spontan | dada menurun, punggung melengkung, kepala naik lalu turun; lengan hanya bergeser sedikit |
| `walk` | 1,2 s, loop | spontan, lebih sering saat remaja | jalan di tempat dengan kaki bergantian; jendela pill ikut meluncur dua siklus |
| `petting` | 2 s, one-shot | maskot dibelai | mata menutup, kepala menyandar ke sentuhan, telinga rileks, ekor melingkar pelan |

Postur per mood tetap dipertahankan dari keyframe pertama tiap klip: punggung
membungkuk, leher turun, telinga terkulai, dan posisi Hips lebih rendah saat
lelah/kritis/tidur. Yang dihapus adalah gerak seluruh badan yang dulu menarik
mesh: `Chest.scale` dibekukan di (1,1,1) dan `Hips.translation` tidak lagi
memantul. Jadi wajah dan badan tidak ikut tertarik saat tangan atau telinga
bergerak.

Enam klip spontan dipilih `PetBehavior` memakai bobot per mood dan tahap:
HP segar boleh memutar semuanya, lelah tidak lagi berjalan, kritis hanya
menoleh dan berdandan, dan tidur menghentikan semuanya. Satu klip tidak
diulang dua kali berturut-turut. Di pill, jeda antar-klip 6-60 detik dan
`walk` menggeser jendela pill selama dua siklus agar langkah dan perpindahan
sinkron.

## Sumber dan cara membuat ulang

- `tools/glb_anim_report.py` membaca struktur GLB, daftar channel, jumlah key,
  nilai awal/akhir, dan sumbu rotasi. Pakai untuk audit cepat.
- `tools/rework_glb_idle.py` menulis ulang buffer animasi di tempat tanpa
  mengubah JSON, bufferView, accessor, atau ukuran file. Skrip ini yang
  menghasilkan klip di atas; `celebrate` sengaja dilewati.

Contoh:

```bash
python tools/rework_glb_idle.py mobile/assets/3d/momo_bayi.glb \
  mobile/assets/3d/momo_remaja.glb mobile/assets/3d/momo_dewasa.glb
python tools/glb_anim_report.py mobile/assets/3d/momo_bayi.glb
```

Backup file sebelum rework disimpan di `%TEMP%/momo_glb_backup` (script hanya
membuat backup sekali, bukan menimpa backup lama).

## Cara pakai di Flutter

`momo_glb_controller.dart` memilih file dari stage (bayi/remaja/dewasa) dan
nama klip dari HP + `isResting`. Loop vs one-shot diatur pemutar, bukan format
glTF. Setelah `tap_reaction` atau `celebrate` selesai, pemutar kembali ke klip
idle yang aktif.

Di luar Flutter, pill memakai `PetLife` + `PetWebRenderer` dengan aturan yang
sama. `PetLife` memilih klip, `PetWebRenderer.setHeadFrame` memindahkan kamera
antara bingkai kepala dan badan penuh tanpa memuat ulang rig, dan renderer
hanya di-`hold` (frame terakhir tetap tampil) saat panel terbuka; `pause`
penuh dipakai ketika jendela pill benar-benar tersembunyi.

## Batas

Rig dan bobot skin dibuat otomatis dari mesh; tidak ada animasi wajah per otot
selain morph kelopak mata. Kibasan ekor memakai rotasi berantai, bukan simulasi
fisik. Klip `celebrate` masih memutar seluruh model dengan sengaja.
