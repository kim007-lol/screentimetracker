# Paket Drako 3D Final, rig per-joint v2, 3 model lengkap

Drako, naga api merah dan emas, quadruped, 4 kaki menapak di tanah, bukan berdiri tegak.

## Isi folder ini, 3 model

- `drako_bayi.glb`, rig per-joint, dari `drako_bayi_6lite.glb` (Meshy 6 Lite, bertekstur)
- `drako_remaja.glb`, rig per-joint, dari `drako_remaja_6lite.glb` (Meshy 6 Lite, bertekstur)
- `drako_dewasa.glb`, rig per-joint, dari `drako_dewasa_6lite.glb` (Meshy 6 Lite, 20 kredit, bertekstur)
- `drako_3d.rig`, definisi rig v2, posisi joint per model, daftar klip, desain idle auto-cycle, hasil verifikasi
- `drako_glb_controller.dart`, pemilih file dari stage (1 Bayi, 2 Remaja, 3 Dewasa), pemilih klip dari HP, dan siklus varian idle
- `drako_bayi.png`, `drako_remaja.png`, `drako_dewasa.png`, gambar acuan v3 untuk Meshy
- `joints.json`, koordinat joint mentah per model

Dewasa: postur mesh-nya horizontal (tulang belakang sejajar tanah, kepala di +Z, sayap membentang di X), beda proporsi dari bayi yang duduk tegak. Joint dewasa dihitung dari klaster mesh dewasa sendiri, dan bind pose-nya persis, lihat bagian verifikasi. Detail orientasi ada di `drako_3d.rig`.

Tidak dipakai: model Meshy Frontier / 7.1. Model 7.1 Drako memang dibuat di Meshy, tapi unduhannya terkunci Pro dan tidak pernah diunduh, jadi tidak ada file 7.1 di sini. Sumber 6 Lite asli tidak ditimpa, tetap di `paket-drako-3d/`.

## Joint, 24 per model

Root, Hips, Spine, Chest, Neck, Head, Horn_L, Horn_R, Wing_L, Wing_L_Tip, Wing_R, Wing_R_Tip, LegFL, PawFL, LegFR, PawFR, LegBL, PawBL, LegBR, PawBR, Tail_1, Tail_2, Tail_3, Tail_Tip.

Posisi joint dihitung per model dari klaster vertex mesh itu sendiri, bukan satu template tetap. Detail dan koordinat lengkap ada di `drako_3d.rig`.

Skinning: bobot jarak halus, `exp(-(distance/0.18)^2)`, 4 joint teratas per vertex, jumlah bobot 1.0. Bind pose tidak mengubah mesh. Khusus dewasa ditambah 8 putaran smoothing bobot antar vertex bertetangga pada representasi top-4, supaya tidak ada lompatan bobot tajam yang bikin gerakan patah: lompatan maksimum antar tetangga turun dari 0.2893 ke 0.2219, p99 dari 0.1009 ke 0.0653.

## Klip, 21 per model, semua per-joint, bukan root saja

Standar, nama sama dengan Momo supaya kodingan bisa dipakai ulang:
- `idle_fresh` (HP > 60), `idle_tired` (HP 30-60), `idle_critical` (HP < 30), `sleep` (isResting), `tap_reaction` (tap, one-shot 0.8 detik), `celebrate` (misi/level, one-shot 1.8 detik, root berputar 360 derajat)

Idle auto-cycle, sesuai permintaan Hakim, idle tidak boleh satu loop yang diulang terus:
- Fresh: `idle_fresh`, `idle_fresh_a` breathing, `idle_fresh_b` look around, `idle_fresh_c` wing flutter, `idle_fresh_d` tail wag and head tilt
- Tired: `idle_tired`, `idle_tired_a` heavy breath, `idle_tired_b` head droop and wing droop, `idle_tired_c` tail drag
- Critical: `idle_critical`, `idle_critical_a` tremble, `idle_critical_b` cower, `idle_critical_c` tail tremble
- Aturan di controller: pilih varian acak, putar sekali, jeda acak 0.5-2.0 detik, pilih varian lain yang berbeda, selama state tidak berubah. Sentuhan, celebrate, atau perubahan state langsung memotong siklus.

Ekstra, diatur oleh Kim:
- `wing_flap`, `tail_wag`, `head_look`, `fire_puff` (gerakan kepala/dada saja, tidak ada mesh api baru), `happy_bounce`

Gaya per tahap: Bayi canggung lambat (durasi loop x 1.2, amplitudo 1.0), Remaja lincah (durasi x 1.0, amplitudo 1.25), Dewasa megah dan tenang (durasi loop terpanjang, idle_fresh 3.2 detik, sleep 4.2 detik, amplitudo 0.85).

## Cara gerakkan satu bagian saja

Three.js, lewat nama joint: `Wing_L`, `Wing_L_Tip`, `Tail_3`, `Head`, dan seterusnya, lihat `drako_3d.rig` bagian `how_to_move_one_part_alone`. Di model viewer biasa hanya klip penuh yang bisa dipilih, bukan joint tunggal.

## Verifikasi yang sudah lolos

- Reload pygltflib: 25 node, 1 skin, 24 joint, mesh node skin = 0, 0 bufferView di luar buffer, bobot jumlah 1.0000 di ketiga model
- Putar Wing_L_Tip 20 derajat: Bayi sayap 0.0456 vs badan 0.0000, Remaja sayap 0.0218 vs badan 0.0008, Dewasa sayap 0.0420 (n=3439) vs badan 0.0000 (n=30010)
- Putar Tail_3 20 derajat: Bayi ekor 0.0150 vs badan 0.0000, Remaja ekor 0.0342 vs badan 0.0000, Dewasa ekor 0.0188 (n=3845) vs badan 0.0000
- Dewasa, bind pose: kesalahan posisi maksimum 5.2e-08, mesh tidak bergeser sama sekali saat diam
- Dewasa, sampling animasi: semua 21 klip disampling skinning penuh di 25 titik waktu. Tidak ada spike, rasio langkah maksimum terhadap median terburuk 2.04 (happy_bounce), langkah rotasi joint terbesar 9.7 derajat per langkah, dan 0 vertex yang terflag bergerak jauh dari tetangganya di semua klip. Rincian per klip ada di `drako_3d.rig`.

## Batas jujur

- Tail_Tip adalah titik kontrol di luar ujung mesh, jadi tidak ada vertex dengan bobot Tail_Tip > 0.5 (mean 0.006). Gerakan ujung ekor yang tajam tetap lewat Tail_3.
- Wing_R_Tip Bayi juga tidak ada vertex dengan bobot > 0.5, sayap kanan Bayi lebih menyatu dengan badan. Sayap kanan tetap bergerak lewat Wing_R.
- Mesh tetap satu primitive menyatu, jadi tidak ada mesh mata, mulut, atau api terpisah untuk kedip atau semburan api sendiri. Itu butuh mesh wajah terpisah atau morph target.
- Posisi joint adalah estimasi dari klaster vertex, bukan tulang artis dari rig asli Meshy, dan semua koordinat tercatat di rig supaya bisa dikoreksi di Blender.
- Dewasa: posisi LegBL/LegBR estimasi paling lemah di model ini, klaster kaki belakang menyatu dengan kolom ekor sehingga wilayah pengaruhnya lebih sempit dari kaki depan. Rincian lengkap ada di `drako_3d.rig` bagian honest_limits.
