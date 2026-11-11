# Momo GLB dengan 5 State Animasi, plus Celebrate

## Temuan awal, jujur

File yang kamu kirim (`bayi.glb`, `remaja.glb`, `dewasa.glb`) adalah mesh statis:
1 node, 1 mesh, 0 skin, 0 bone, 0 animasi. Jadi tidak ada tulang kepala, telinga,
atau ekor yang bisa digerakkan terpisah, karena meshnya menyatu.

Yang sudah aku lakukan, bukan sekadar mengganti nama: aku menambahkan 6 klip
animasi ke dalam setiap file, dengan nama persis yang kamu minta, yang
menganimasikan root node karakter (naik turun, goyang, miring, skala napas,
putar). Klip ini langsung bisa dipanggil di kodingan lewat nama.

## Klip di setiap file

- `idle_fresh`, looping, HP > 60: napas teratur, goyang lembut kiri kanan, kepala tegak
- `idle_tired`, looping, HP 30-60: membungkuk 7-9 derajat, napas lambat dan berat, skala Y turun
- `idle_critical`, looping, HP < 30: gemetar halus cepat 1.2 detik, postur meringkuk 10 derajat
- `sleep`, looping, mode istirahat: meringkuk 10-11 derajat, napas sangat lambat 3.6 detik
- `tap_reaction`, one-shot 0.8 detik, layar disentuh: lompat kecil, miring kepala, lalu kembali ke idle
- `celebrate`, one-shot 1.8 detik, bonus: putar 360 derajat sambil melompat, untuk misi selesai atau naik level

Loop vs one-shot diatur di pemutar (Flutter / Three.js), bukan di file .glb,
karena format glTF tidak menyimpan flag loop.

## Beda gaya per tahap, sudah tertanam di klip

- Bayi: `idle_fresh` 2.4 detik, goyang canggung lebih besar, lompat tap lebih kecil
- Remaja: `idle_fresh` 2.0 detik, paling lincah, lompat tap paling tinggi
- Dewasa: `idle_fresh` 3.0 detik, gerak paling tenang dan kecil, napas dalam

## Cara pakai

Lihat `momo_glb_controller.dart`:
- Pilih file dari stage: 1 Bayi, 2 Remaja, 3 Dewasa
- Pilih klip dari HP dan isResting, seperti tabel di atas
- Saat tap, pakai `tap_reaction` 0.8 detik lalu kembali ke idle aktif
- Saat naik stage atau misi selesai, pakai `celebrate` 1.8 detik lalu kembali ke idle

## Batas yang tetap jujur

Karena mesh asli tidak punya bone, kedipan mata, kedutan telinga terpisah,
dan kibasan ekor terpisah tidak bisa dibuat dari file ini saja. Gerak itu
disimulasikan lewat goyang dan napas seluruh badan di klip di atas.
Kalau mau telinga dan ekor bergerak benar-benar terpisah, mesh harus
di-rig ulang di Blender / Mixamo dengan skinning, atau dibuat ulang
dari model yang memang punya bone terpisah, bukan dari mesh statis ini.
File .rig lama untuk Rive tetap berlaku untuk versi 2D, sedangkan untuk
3D, rig yang berlaku adalah klip-klip di dalam file .glb ini.
