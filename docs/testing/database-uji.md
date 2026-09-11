# Database Uji `hociro_upah` — Seed Baseline Terdokumentasi

**Status:** Menggantikan `test_bersih_5` sebagai baseline regresi. Jangan pakai `test_bersih_5` untuk membandingkan angka — lihat §5.

Dokumen ini memuat cara membuat database uji baru dari `scripts/seed_test_data.py`, isi datanya, dan nilai yang **diharapkan** dihasilkan kalau seed ini dipakai untuk menghitung periode upah. Nilai-nilai itu dihitung dari pembacaan formula di `addons/hociro_upah/models/hociro_periode_upah.py`, bukan ditebak — tapi **belum pernah dibandingkan dengan keluaran Odoo sungguhan**. Baca §5 sebelum memakai tabel di §3/§4 sebagai kebenaran mutlak.

---

## 1. Cara menjalankan

Ditulis untuk orang yang belum pernah melakukannya. Perintah `docker compose` di bawah mengikuti pola yang sudah dipakai di `docs/setup-odoo-docker-agent3.md` §3 dan §9 — sesuaikan nama service/container kalau environment-mu berbeda.

### 1.1 Buat database kosong + pasang modul

Nama database **harus** diawali `test_` — skrip seed menolak jalan kalau tidak (lihat komentar "PENGAMAN 1" di `scripts/seed_test_data.py`). Rekomendasi nama: `test_seed_upah_v1` (alasannya di §6 dokumen ini).

```bash
cd /opt/hociro-erp
docker compose exec -T odoo \
    odoo -d test_seed_upah_v1 -i hociro_upah --stop-after-init
```

Perintah `-i` dengan nama database yang belum ada akan **membuat database itu sekaligus memasang modulnya** — tidak perlu `createdb` terpisah. Pastikan log tidak ada traceback (sama seperti checklist instalasi `v19-conventions.md` §5 poin 7).

Kalau mau memastikan tidak ada demo data yang ikut terpasang (opsional — seed ini tidak terpengaruh demo data `hr` karena hanya membuat employee baru dan tidak membaca employee yang sudah ada), tambahkan `--without-demo=all` ke perintah di atas.

### 1.2 Jalankan skrip seed lewat `odoo shell`

```bash
docker compose exec -T odoo \
    odoo shell -d test_seed_upah_v1 < repo/scripts/seed_test_data.py
```

**Wajib lewat `odoo shell`**, bukan `python3 scripts/seed_test_data.py` langsung — skrip memakai variabel `env` yang cuma tersedia di dalam sesi `odoo shell`.

Kalau berhasil, output diakhiri ringkasan:
```
=== Seed selesai di database "test_seed_upah_v1" ===
Staf dibuat: 3 (Staf A, Staf B [batas disiplin 8.0], Staf C)
Absensi staf dibuat: 159 (27 hari x 3 staf Juli + 26 hari x 3 staf Agustus)
Rentang absensi staf: 2026-07-01 s/d 2026-08-31
Tukang dibuat: 3 (Tukang 1, Tukang 2, Tukang 3 [tanpa tarif])
Absensi tukang dibuat: 36 (2 minggu x 6 hari x 3 tukang)
Rentang absensi tukang: 2026-06-01 s/d 2026-06-13
TIDAK ada hociro.periode.upah yang dibuat -- buat sesuai skenario ujimu.
```

Kalau skrip menolak jalan dengan pesan soal nama database atau data lama — baca pesannya, jangan di-*bypass*. Itu pengaman yang sengaja dipasang (lihat komentar di kode skrip).

### 1.3 Membuat periode untuk pengujian

Seed **tidak** membuat `hociro.periode.upah` — buat sendiri sesuai skenario ujimu, lewat UI atau shell. Contoh lewat shell, untuk mereproduksi baseline di §3 dan §4 dokumen ini:

```python
# Periode Bulanan Juli 2026
juli = env['hociro.periode.upah'].create({
    'tipe': 'bulanan',
    'tanggal_mulai': '2026-07-01',
    'tanggal_selesai': '2026-07-31',
})
juli.action_hitung_upah()
juli.action_tutup_periode()   # WAJIB ditutup sebelum Agustus dihitung -- lihat catatan predecessor lock di §3

# Periode Bulanan Agustus 2026
agustus = env['hociro.periode.upah'].create({
    'tipe': 'bulanan',
    'tanggal_mulai': '2026-08-01',
    'tanggal_selesai': '2026-08-31',
})
agustus.action_hitung_upah()
```

Pola yang sama berlaku untuk periode Mingguan (§4): buat, hitung, **tutup**, baru buat periode berikutnya. Sejak issue #2 (predecessor lock), `action_hitung_upah()` pada periode kedua akan ditolak `UserError` kalau periode pertama belum ditutup — ini bukan bug, itu guard yang sedang bekerja.

---

## 2. Isi data

### 2.1 Staf (3 orang), absensi Juli & Agustus 2026, Senin–Sabtu

| Nama | `x_gaji_pokok` | `x_tarif_harian` | `x_tarif_disiplin` | `x_tarif_transpor` | `x_tarif_lembur` | `x_batas_jam_disiplin` |
|---|---:|---:|---:|---:|---:|---:|
| Staf A | 2.000.000 | 50.000 | 15.000 | 10.000 | 100.000 | 8.5 (default) |
| Staf B | 2.000.000 | 50.000 | 15.000 | 10.000 | 100.000 | **8.0 (override)** |
| Staf C | 2.500.000 | 60.000 | 15.000 | 12.000 | 120.000 | 8.5 (default) |

Pola `jam_masuk` per hari-dalam-minggu, **sama untuk ketiga staf** — yang membedakan hasil disiplin cuma cutoff masing-masing:

| Hari | `jam_masuk` | Lolos 8.5 (A, C)? | Lolos 8.0 (B)? |
|---|---:|:---:|:---:|
| Senin | 8.0 | ✅ | ✅ |
| Selasa | 8.3 | ✅ | ❌ |
| Rabu | 8.5 | ✅ (pas di batas) | ❌ |
| Kamis | 8.6 | ❌ | ❌ |
| Jumat | 7.5 | ✅ | ✅ |
| Sabtu | 9.0 | ❌ | ❌ |

Semua absensi `status = 'hadir'` (tidak ada sakit/izin/cuti/alfa di seed ini — variasi yang diuji adalah cutoff disiplin, bukan status kehadiran).

Rentang: **2026-07-01 s/d 2026-08-31**, 27 hari kerja (Senin–Sabtu) di Juli, 26 hari di Agustus. Total **159 record** `hociro.absensi.staf` (53 hari × 3 staf).

### 2.2 Tukang (3 orang), absensi dua minggu berurutan Juni 2026

| Nama | `x_upah_harian` | `x_tarif_lembur` | Catatan |
|---|---:|---:|---|
| Tukang 1 | 150.000 | 30.000 | |
| Tukang 2 | 140.000 | 28.000 | |
| Tukang 3 | — (tidak diisi) | — (tidak diisi) | Meniru Wak Andi / Anak Bang Dedek (§-1 `session-log.md`) — tukang tanpa tarif |

Minggu 1: **2026-06-01 (Senin) s/d 2026-06-06 (Sabtu)**. Minggu 2: **2026-06-08 (Senin) s/d 2026-06-13 (Sabtu)**. Semua absensi `sesi_pagi='1'`, `sesi_siang='1'` (hari_kerja = 1.0/hari), `state='dikuatkan'`. Satu pengecualian: Tukang 1 dan Tukang 2 punya `lembur=1.0` pada Sabtu 6 Juni (minggu 1) untuk menguji `tarif_lembur`; semua hari lain `lembur=0.0`. Tukang 3 tidak pernah lembur.

Total **36 record** `hociro.absensi.tukang` (2 minggu × 6 hari × 3 tukang).

---

## 3. Nilai yang diharapkan — Periode Bulanan (staf)

Dihitung dari `_compute_hari_staf()`, `_compute_upah_kotor()`, `_compute_saldo_akhir()` di `hociro_periode_upah.py`, dengan formula staf:

```
upah_kotor = tarif_pokok + (hari_hadir × tarif_harian) + (hari_disiplin × tarif_disiplin)
             + (hari_hadir × tarif_transpor) + (hari_lembur_staf × tarif_lembur) + bonus
saldo_akhir = saldo_awal + upah_kotor - total_dibayar
```

`hari_lembur_staf`, `bonus`, dan `total_dibayar` selalu 0 di baseline ini (seed tidak mengisinya, dan `_prepare_line_vals()` tidak menyalin nilai manual — lihat issue #1/#4).

**Prasyarat urutan:** periode Juli harus dihitung dan **ditutup** (`action_tutup_periode()`) sebelum periode Agustus dihitung — kalau tidak, predecessor lock (issue #2) akan menolak dengan `UserError`. Ini bukan bug.

### Bulanan 2026-07 (tanggal_mulai=2026-07-01, tanggal_selesai=2026-07-31)

| Karyawan | `hari_hadir` | `hari_disiplin` | `upah_kotor` | `saldo_awal` | `saldo_akhir` |
|---|---:|---:|---:|---:|---:|
| Staf A | 27 | 18 | 3.890.000 | 0 | **3.890.000** |
| Staf B | 27 | 9 | 3.755.000 | 0 | **3.755.000** |
| Staf C | 27 | 18 | 4.714.000 | 0 | **4.714.000** |

`saldo_awal = 0` untuk ketiganya karena ini periode Bulanan pertama di database uji ini (tidak ada periode `ditutup` sebelumnya dengan `tipe='bulanan'`).

### Bulanan 2026-08 (tanggal_mulai=2026-08-01, tanggal_selesai=2026-08-31)

**Prasyarat: periode Bulanan 2026-07 di atas sudah dihitung DAN ditutup.**

| Karyawan | `hari_hadir` | `hari_disiplin` | `upah_kotor` | `saldo_awal` | `saldo_akhir` |
|---|---:|---:|---:|---:|---:|
| Staf A | 26 | 17 | 3.815.000 | 3.890.000 | **7.705.000** |
| Staf B | 26 | 9 | 3.695.000 | 3.755.000 | **7.450.000** |
| Staf C | 26 | 17 | 4.627.000 | 4.714.000 | **9.341.000** |

`saldo_awal` Agustus = `saldo_akhir` Juli persis (carry-over) — ini test paling penting untuk guard nilai manual issue #1 (lihat `docs/session-log.md` §-6): `saldo_awal` bukan-nol di sini adalah kondisi **normal**, bukan yang harus diblokir.

---

## 4. Nilai yang diharapkan — Periode Mingguan (tukang)

Formula tukang:

```
upah_kotor = (hari_kerja × tarif_harian) + (hari_lembur × tarif_lembur)
saldo_akhir = saldo_awal + upah_kotor - total_dibayar
```

**Prasyarat urutan:** periode Minggu 1 harus dihitung dan **ditutup** sebelum Minggu 2 dihitung (predecessor lock, sama seperti staf).

### Mingguan 1 (tanggal_mulai=2026-06-01, tanggal_selesai=2026-06-06)

| Karyawan | `hari_kerja` | `hari_lembur` | `upah_kotor` | `saldo_awal` | `saldo_akhir` |
|---|---:|---:|---:|---:|---:|
| Tukang 1 | 6.0 | 1.0 | 930.000 | 0 | **930.000** |
| Tukang 2 | 6.0 | 1.0 | 868.000 | 0 | **868.000** |
| Tukang 3 | 6.0 | 0.0 | 0 | 0 | **0** |

Tukang 3 tetap dapat line (hadir tercatat) walau `upah_kotor` nol karena tidak punya tarif — bukan bug, sama seperti kasus Wak Andi/Anak Bang Dedek.

### Mingguan 2 (tanggal_mulai=2026-06-08, tanggal_selesai=2026-06-13)

**Prasyarat: Mingguan 1 di atas sudah dihitung DAN ditutup.**

| Karyawan | `hari_kerja` | `hari_lembur` | `upah_kotor` | `saldo_awal` | `saldo_akhir` |
|---|---:|---:|---:|---:|---:|
| Tukang 1 | 6.0 | 0.0 | 900.000 | 930.000 | **1.830.000** |
| Tukang 2 | 6.0 | 0.0 | 840.000 | 868.000 | **1.708.000** |
| Tukang 3 | 6.0 | 0.0 | 0 | 0 | **0** |

---

## 5. Status verifikasi tabel nilai (§3, §4) — BACA SEBELUM MEMAKAI

**Status: dihitung dari pembacaan formula di kode, diverifikasi silang secara terprogram, TAPI belum pernah dibandingkan dengan keluaran Odoo sungguhan. Menunggu konfirmasi Agent 3 pada seed run pertama.**

### Apa artinya "diverifikasi silang secara terprogram" — dan apa yang BUKAN artinya

Mesin yang dipakai menulis dokumen ini tidak punya Odoo/Docker terpasang. Semua angka di §3 dan §4 dihitung dua kali secara manual: sekali langsung saat menulis tabel, sekali lagi lewat skrip Python terpisah yang **menulis ulang** logika `_compute_hari_staf()`, `_compute_dapat_disiplin()`, `_compute_upah_kotor()`, dan `_compute_saldo_akhir()` berdasarkan pembacaan kode `hociro_periode_upah.py` dan `hociro_absensi_staf.py`.

Kedua hitungan itu cocok satu sama lain. **Itu bukan bukti keduanya benar** — itu cuma bukti konsisten secara internal. Skrip verifikasinya adalah implementasi ulang dari pembacaan yang sama atas kode yang sama; kalau pembacaannya keliru (salah tanda `<=` vs `<`, salah field yang dipetakan, salah asumsi urutan operasi), skrip verifikasinya akan keliru dengan cara yang identik dan tetap menghasilkan angka yang "cocok". Ini **tidak pernah dijalankan lewat kode modul yang sebenarnya** (tidak ada Odoo yang jalan di mesin ini) — jadi belum ada yang membuktikan pembacaannya benar, cuma bahwa pembacaannya konsisten dengan dirinya sendiri.

### Formula yang ditulis ulang (bukan dijalankan) — titik paling mungkin menyimpang

- **`dapat_disiplin`** (`hociro_absensi_staf.py:41-48`): `status == 'hadir' AND jam_masuk > 0 AND jam_masuk <= batas`, `batas = x_batas_jam_disiplin or 8.5`. Titik rawan: operator `<=` di batas atas (bukan `<`), dan fallback `or 8.5` kalau field kosong/`0.0` (bukan hanya kalau `None`).
- **`_compute_hari_staf`** (`hociro_periode_upah.py:369-381`): `hari_hadir` = jumlah absensi `status='hadir'` dalam rentang tanggal periode (inklusif di kedua ujung, `>=` dan `<=`); `hari_disiplin` = jumlah yang `dapat_disiplin=True`. Titik rawan: batas tanggal inklusif/eksklusif.
- **`_compute_hari_kerja_tukang`** (`hociro_periode_upah.py:348-361`): `hari_kerja` = jumlah `hociro.absensi.tukang.hari_kerja` (masing-masing `(sesi_pagi+sesi_siang)/2`) untuk absensi `state='dikuatkan'` dalam rentang tanggal; `hari_lembur` = jumlah field `lembur`.
- **`_compute_upah_kotor`** (`hociro_periode_upah.py:388-405`): formula staf dan tukang seperti dikutip di §3/§4. Titik rawan: urutan/kelengkapan suku penjumlahan, dan asumsi `hari_lembur_staf`/`bonus`/`total_dibayar` selalu 0 di baseline ini (benar berdasarkan pembacaan `_prepare_line_vals()`, tapi belum diuji langsung).
- **`_compute_saldo_akhir`** (`hociro_periode_upah.py:407-410`): `saldo_awal + upah_kotor - total_dibayar`. Titik rawan: sumber `saldo_awal` untuk periode kedua — diasumsikan persis `saldo_akhir` periode sebelumnya lewat `_prepare_line_vals()` (`hociro_periode_upah.py:221-228`), termasuk asumsi periode pertama harus `ditutup` dulu (predecessor lock, issue #2).

### Aturan wajib kalau angka Odoo berbeda dari tabel

**Kalau hasil hitung Odoo sungguhan berbeda dari tabel di §3/§4, JANGAN langsung mengubah tabelnya supaya cocok.** Selisihnya harus diselidiki dulu — kemungkinan besar itu kode yang salah (bug), bukan tabelnya yang salah. Tabel baru boleh ditandai terverifikasi setelah salah satu dari dua hal ini:

1. Selisihnya **nol** — hasil Odoo cocok persis dengan tabel, atau
2. Selisihnya **dijelaskan** — ada alasan yang dipahami dan didokumentasikan kenapa angkanya berbeda (mis. field default yang ternyata beda dari asumsi), bukan sekadar ditimpa.

### Yang juga belum diverifikasi (butuh Odoo berjalan)

- [ ] Checklist §5 poin 7 `v19-conventions.md` untuk skrip ini — instalasi modul ke database baru via `-i hociro_upah --stop-after-init` sudah rutin dipakai untuk modul ini, tapi belum dijalankan ulang khusus untuk memverifikasi seed berjalan tanpa error di atasnya.
- [ ] Apakah `env['hr.employee'].create()` di skrip seed berhasil tanpa field wajib tambahan yang tidak terlihat dari kode `hociro_upah` (mis. field wajib dari modul `hr` core yang tidak dioverride di sini).

**Setelah Agent 3 menjalankan seed dan menghitung keempat periode di §3/§4:** laporkan balik apakah angka `hari_hadir`, `hari_disiplin`/`hari_lembur`, `upah_kotor`, `saldo_awal`, `saldo_akhir` di UI/shell cocok persis dengan tabel. Kalau cocok (selisih nol), ganti judul §5 ini jadi "Diverifikasi 2026-xx-xx oleh Agent 3, cocok persis dengan Odoo sungguhan." Kalau tidak cocok, **investigasi dulu** (lihat "titik paling mungkin menyimpang" di atas), lalu catat angka sebenarnya berdampingan dengan yang diharapkan di tabel — jangan menimpa tabelnya begitu saja, supaya selisihnya tetap kelihatan sampai penyebabnya jelas.

---

## 6. Kenapa `test_bersih_5` ditinggalkan

`docs/session-log.md` §-6 mencatat bahwa guard nilai manual (issue #1) menangkap `saldo_awal` Staf A di periode Bulanan 2026-08 `test_bersih_5` yang salah 135.000 — sisa stale saldo dari skenario buka-kembali yang dipakai untuk menemukan bug successor lock (issue #2) di sesi 2026-09-10. `§-2` sempat mencatat carry-over saldo di database itu "terverifikasi LOLOS", dan itu benar untuk keadaan saat dicatat, tapi tidak lagi benar untuk keadaannya sekarang. Database uji yang isinya hasil pengujian manual bertahun-tahun — dengan periode dibuka-tutup berulang kali lewat skenario yang berbeda-beda — tidak bisa dipercaya sebagai pembanding regresi, dan tidak ada yang tahu apa lagi yang sudah bergeser di dalamnya selain yang kebetulan ketahuan lewat guard baru ini. Seed di dokumen ini menggantikannya: dibuat dari nol, sekali jalan, dengan setiap angka yang dihasilkannya terdokumentasi dan bisa dihitung ulang dari formula kode kapan pun.
