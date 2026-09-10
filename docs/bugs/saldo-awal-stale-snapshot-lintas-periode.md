# Bug: `saldo_awal` Jadi Stale Snapshot Lintas Periode Setelah Buka-Kembali

- **Status:** Terbuka (belum diperbaiki — dokumentasi temuan saja)
- **Modul:** `hociro_upah`
- **File:** `models/hociro_periode_upah.py`
- **Field terdampak:** `hociro.upah.line.saldo_awal`
- **Terkait dengan:** [`regenerate-upah-menghapus-data-manual.md`](./regenerate-upah-menghapus-data-manual.md) — lihat bagian Cross-reference di bawah
- **Ditemukan di:** database uji `test_bersih_5`, periode `Bulanan 2026-07` dan `Bulanan 2026-08`

## Deskripsi

`saldo_awal` pada `hociro.upah.line` **bukan computed field** — dia adalah snapshot statis yang diisi satu kali oleh `_prepare_line_vals()` saat periode dihitung:

```python
prev_periode = self.env['hociro.periode.upah'].search([
    ('tipe', '=', self.tipe),
    ('state', '=', 'ditutup'),
    ('tanggal_selesai', '<', self.tanggal_mulai),
], order='tanggal_selesai desc', limit=1)
saldo_awal_map = {
    line.employee_id.id: line.saldo_akhir for line in prev_periode.line_ids
}
...
'saldo_awal': saldo_awal_map.get(employee.id, 0.0),
```

Nilai ini diambil dari `saldo_akhir` periode sebelumnya **pada saat itu juga**, lalu disimpan sebagai angka statis di `hociro.upah.line` periode berikutnya. Tidak ada `@api.depends` atau mekanisme lain yang menghubungkan `saldo_awal` periode N+1 ke `saldo_akhir` periode N secara live.

Akibatnya: kalau periode sumber (N) yang sudah `ditutup` **dibuka kembali** (`action_buka_kembali()`) lalu dihitung ulang (`action_hitung_upah()`) dan hasil `saldo_akhir`-nya berubah (misalnya karena ada koreksi absensi atau — lihat bug terkait — karena data manual seperti `total_dibayar` yang hilang saat regenerate), **periode N+1 yang sudah dibuat sebelumnya tidak ikut ter-update**. `saldo_awal` di periode N+1 tetap memakai nilai lama, sehingga sekarang tidak sinkron dengan `saldo_akhir` periode N yang sebenarnya.

## Langkah Reproduksi

Melanjutkan dari state akhir pengujian [`regenerate-upah-menghapus-data-manual.md`](./regenerate-upah-menghapus-data-manual.md) dan pengujian carry-over saldo, di database `test_bersih_5`:

1. Periode `Bulanan 2026-07` sudah `ditutup`, dengan `saldo_akhir` Staf A = `6.255.000`.
2. Periode `Bulanan 2026-08` sudah dibuat & dihitung (`action_hitung_upah()`), mengambil `saldo_awal` Staf A = `6.255.000` dari `saldo_akhir` Juli di atas (carry-over ini sendiri **benar** pada saat dilakukan).
3. `action_buka_kembali()` dipanggil pada periode Juli → state `ditutup → dihitung`.
4. Line Staf A Juli diisi manual `total_dibayar = 3.000.000` → `saldo_akhir` Juli jadi `3.255.000` (`0 + 6.255.000 − 3.000.000`).
5. Satu record `hociro.absensi.staf` Staf A tanggal 2026-07-15 diedit (`status`: `hadir` → `izin`), mensimulasikan koreksi absensi setelah buka-kembali.
6. `action_hitung_upah()` dipanggil ulang pada periode Juli.
   - Line lama (id=7) di-`unlink()`, line baru dibuat (id=13) — lihat bug terkait untuk detail ini.
   - `total_dibayar` yang diisi di langkah 4 hilang (reset ke 0) — bug yang sudah didokumentasikan.
   - `hari_hadir` 27→24, `hari_disiplin` 19→16 (efek kumulatif koreksi absensi di beberapa skenario pengujian).
   - `saldo_akhir` Juli yang baru = **6.120.000**.
7. Periode Agustus **tidak disentuh sama sekali** pada langkah 3-6 di atas, dan tidak ada trigger apa pun yang menjalankannya ulang.

### Tabel nilai lengkap (Staf A)

| Titik | line_id Juli | total_dibayar Juli | saldo_akhir Juli | saldo_awal Agustus (tersimpan) |
|---|---|---|---|---|
| Sebelum buka kembali (Juli `ditutup`) | 7 | 0 | 6.255.000 | 6.255.000 |
| Setelah `action_buka_kembali()` | 7 | 0 | 6.255.000 (belum berubah) | 6.255.000 |
| Setelah isi manual `total_dibayar=3.000.000` | 7 | 3.000.000 | **3.255.000** | 6.255.000 |
| Setelah koreksi absensi 15 Juli + `action_hitung_upah()` ulang | **13** (id baru) | 0 (hilang lagi) | **6.120.000** | **6.255.000 (tidak berubah — STALE)** |

**Hasil akhir:**

| | Nilai |
|---|---|
| `Agustus.saldo_awal` (Staf A, snapshot lama) | 6.255.000 |
| `Juli.saldo_akhir` (Staf A, versi terbaru setelah buka-tutup-hitung ulang) | 6.120.000 |
| **Selisih** | **135.000** |
| Sinkron? | **Tidak** |

Semua nilai di atas diverifikasi dua kali: lewat Odoo shell (`env['hociro.upah.line']`) dan lewat query SQL langsung ke Postgres (independen dari cache ORM), hasilnya konsisten.

## Dampak

**Cascading inconsistency yang berpotensi lebih luas dari yang teruji.** Pada pengujian ini hanya ada satu periode "di depan" (Agustus), dan sudah terbukti tidak sinkron. Kalau ada rantai periode lebih panjang (mis. Juli → Agustus → September → Oktober, masing-masing sudah dihitung berurutan), membuka-kembali Juli dan mengubah `saldo_akhir`-nya berpotensi membuat **semua periode setelahnya** (bukan cuma yang persis berikutnya) tidak sinkron — karena `saldo_awal` Agustus yang stale akan menghasilkan `saldo_akhir` Agustus yang juga salah, yang kalau di-carry-over ke September (via mekanisme yang sama) akan mewariskan kesalahan itu terus menjalar ke depan. *(Catatan: skenario rantai lebih dari 2 periode belum diuji langsung dalam sesi ini — ini proyeksi berdasarkan cara kerja `_prepare_line_vals()` yang sama persis dipakai di setiap periode, bukan hasil pengujian empiris.)*

**Tidak ada `UserError`, warning, atau indikator apa pun** yang memberi tahu user bahwa:
- Periode yang mereka buka-kembali punya periode lain "di depannya" yang sudah bergantung pada `saldo_akhir`-nya.
- Setelah `action_hitung_upah()` ulang, periode-periode di depan itu sekarang menyimpan `saldo_awal` yang stale/salah.

Efek gabungan dengan bug `total_dibayar` yang hilang (lihat cross-reference): kombinasi keduanya membuat selisih saldo bisa terjadi di dua tempat sekaligus — di periode yang dibuka-kembali (karena data manual hilang) **dan** di periode-periode setelahnya (karena snapshot stale) — tanpa ada satu pun sinyal error ke user.

## Cross-Reference

Bug ini **berbeda root cause** dari [`regenerate-upah-menghapus-data-manual.md`](./regenerate-upah-menghapus-data-manual.md):

- **Bug lain (`regenerate-upah-menghapus-data-manual.md`):** root cause di `action_hitung_upah()` yang melakukan `unlink()` + `create()` pada `hociro.upah.line`, sehingga field manual (`bonus`, `hari_lembur_staf`, `total_dibayar`) yang tidak diisi ulang oleh `_prepare_line_vals()` jadi hilang. Ini bug **di dalam satu periode**.
- **Bug ini:** root cause di `saldo_awal` yang merupakan snapshot statis (bukan computed), sehingga tidak ada propagasi saat periode sumbernya dihitung ulang dengan hasil berbeda. Ini bug **lintas periode / cascading**.

Namun **keduanya dipicu oleh alur yang sama persis**: *"buka kembali periode yang sudah ditutup, lalu hitung ulang"*. Alur ini tampaknya tidak pernah dipertimbangkan sebagai operasi yang aman secara data saat modul ini didesain — kedua bug baru muncul begitu alur buka-kembali-hitung-ulang benar-benar dijalankan dalam pengujian, bukan cuma alur linear "hitung sekali, tutup, lanjut ke periode berikutnya".

## Opsi Perbaikan (Menunggu Keputusan Desain — JANGAN dipatch dulu)

Tiga opsi berikut hanya didaftarkan untuk didiskusikan; belum ada yang diimplementasikan dan belum ada rekomendasi final di dokumen ini:

**a. `saldo_awal` jadi computed field (bukan stored snapshot)**
Dihitung live dari `saldo_akhir` periode sebelumnya setiap kali dibaca/dipakai (`compute`, dengan atau tanpa `store=True` + `@api.depends` yang benar ke periode sebelumnya). Paling konsisten secara data, tapi perlu hati-hati dengan `@api.depends` lintas record/model (dependency ke `line_ids.saldo_akhir` milik periode *lain*), dan perlu pertimbangan performa kalau rantai periode panjang.

**b. Blokir `action_buka_kembali()` kalau sudah ada periode lebih baru yang dependen ke `saldo_akhir` periode ini**
Butuh definisi "dependen" yang jelas dulu — apakah cukup "ada periode dengan `tipe` sama dan `tanggal_mulai` lebih besar", atau harus dicek benar-benar sudah memakai `saldo_akhir` periode ini sebagai `saldo_awal`-nya (yang berarti butuh field pelacak asal snapshot, tidak ada saat ini). Paling sederhana untuk dicegah, tapi paling membatasi fleksibilitas operasional (user mungkin memang perlu koreksi periode lama).

**c. Saat periode dibuka-kembali-dihitung-ulang, trigger cascade recompute otomatis ke semua periode setelahnya**
Paling kompleks (perlu traversal berantai + penanganan periode yang statusnya sudah `ditutup` juga di rantai berikutnya, yang berarti perlu buka-kembali-hitung ulang-tutup lagi secara otomatis atau ditolak), tapi paling "benar" secara data — hasil akhirnya konsisten dengan opsi (a) tanpa mengubah `saldo_awal` jadi computed field.

## Yang Belum Dilakukan

Tidak ada perubahan kode pada laporan ini — murni dokumentasi temuan dari pengujian di `test_bersih_5`. Keputusan opsi mana yang dipakai (atau kombinasinya) perlu didiskusikan dan dikonfirmasi sebelum implementasi dimulai.
