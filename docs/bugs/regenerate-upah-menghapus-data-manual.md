# Bug: `action_hitung_upah()` Menghapus Data Manual Saat Regenerate

- **Status:** Terbuka (belum diperbaiki — dokumentasi temuan saja)
- **Modul:** `hociro_upah`
- **File:** `models/hociro_periode_upah.py`
- **Fungsi:** `HociroPeriodeUpah.action_hitung_upah()` (baris 69–80), dipicu ulang oleh `_prepare_line_vals()` (baris 94–137)
- **Ditemukan di:** database uji `test_bersih_5`, periode `Bulanan 2026-07`

## Deskripsi

Setiap kali `action_hitung_upah()` dipanggil ulang pada periode yang sama — misalnya karena user mengoreksi absensi setelah periode sudah dihitung — seluruh `hociro.upah.line` milik periode tersebut **dihapus total (`unlink()`) lalu dibuat ulang dari nol**:

```python
def action_hitung_upah(self):
    for rec in self:
        ...
        rec.line_ids.unlink()          # menghapus SEMUA line lama, termasuk input manual
        vals_list = rec._prepare_line_vals()
        if vals_list:
            self.env['hociro.upah.line'].create(vals_list)   # line baru, id berbeda
        rec.state = 'dihitung'
```

`_prepare_line_vals()` hanya mengisi field yang bisa diturunkan dari sumber lain: `periode_id`, `employee_id`, `saldo_awal` (dari periode sebelumnya yang berstatus `ditutup`), `total_dibayar=0.0` (hardcoded), dan snapshot tarif dari `hr.employee`. Field yang **hanya bisa diisi manual oleh user** — `bonus`, `hari_lembur_staf`, `total_dibayar` — tidak pernah dibaca kembali dari line lama sebelum di-unlink, sehingga nilainya hilang tanpa peringatan apa pun ke user.

## Langkah Reproduksi

Dilakukan di database `test_bersih_5` (modul `hociro_upah` terinstal, skema lengkap), dengan 3 `hr.employee` dummy bertipe `staf` dan absensi Juli 2026 sudah diisi (lihat riwayat sesi untuk detail seed data).

1. Buat periode `hociro.periode.upah` dengan `tipe='bulanan'`, `tanggal_mulai=2026-07-01`, `tanggal_selesai=2026-07-31`, lalu jalankan `action_hitung_upah()`.
   - Menghasilkan 3 `hociro.upah.line` (satu per staf). Line Staf A: id=1, `upah_kotor=6.525.000`, `bonus=0`, `hari_lembur_staf=0`, `total_dibayar=0`, `saldo_akhir=6.525.000`.
2. **Skenario A — bonus & lembur manual:**
   - Isi manual pada line Staf A: `bonus=50.000`, `hari_lembur_staf=2`.
   - `upah_kotor` naik jadi `6.675.000` (sesuai formula: `+ hari_lembur_staf×tarif_lembur + bonus` = `+2×50.000 +50.000`). ✅ Benar di titik ini.
   - Edit satu record `hociro.absensi.staf` milik Staf A (tanggal 2026-07-01: `status` `hadir` → `izin`), mensimulasikan koreksi absensi setelah periode dihitung.
   - Jalankan `action_hitung_upah()` lagi pada periode yang sama.
   - **Hasil:** line lama (id=1) di-`unlink()`, line baru dibuat (id=4). `bonus` dan `hari_lembur_staf` pada line baru = **0** (hilang), padahal sebelumnya diisi 50.000 dan 2. `hari_hadir` 27→26, `hari_disiplin` 19→18 (efek koreksi absensi, ini benar), `upah_kotor` jadi `6.390.000` (turun bukan cuma karena absensi, tapi juga karena bonus & lembur manual lenyap).
3. **Skenario B — total_dibayar manual:**
   - Lanjut dari line Staf A hasil langkah 2 (id=4, `total_dibayar=0`, `saldo_akhir=6.390.000`).
   - Isi manual `total_dibayar=3.000.000` pada line id=4. `saldo_akhir` otomatis jadi `3.390.000` (`saldo_awal 0 + upah_kotor 6.390.000 − total_dibayar 3.000.000`). ✅ Benar.
   - Edit record absensi Staf A lain (tanggal 2026-07-08: `status` `hadir` → `izin`).
   - Jalankan `action_hitung_upah()` lagi.
   - **Hasil:** line id=4 di-`unlink()`, line baru dibuat (id=7). `total_dibayar` pada line baru = **0** (hilang, padahal sebelumnya 3.000.000). `hari_hadir` 26→25, `upah_kotor` jadi `6.255.000`. `saldo_akhir` yang dilaporkan sistem = `6.255.000`.
   - **Nilai yang seharusnya benar** kalau `total_dibayar=3.000.000` tetap dipertahankan: `saldo_akhir = 0 + 6.255.000 − 3.000.000 = 3.255.000`.
   - **Selisih: tepat 3.000.000** — persis sebesar pembayaran yang hilang.

Semua nilai di atas sudah diverifikasi dua kali: sekali lewat Odoo shell (`env['hociro.upah.line']`), sekali lagi lewat query SQL langsung ke Postgres (independen dari cache ORM), hasilnya konsisten.

## Ringkasan Temuan

| # | Temuan | Bukti |
|---|---|---|
| 1 | `bonus` reset ke 0 setelah regenerate | 50.000 → 0 |
| 2 | `hari_lembur_staf` reset ke 0 setelah regenerate | 2 → 0 |
| 3 | `total_dibayar` reset ke 0 setelah regenerate | 3.000.000 → 0 |
| 4 | `saldo_akhir` menjadi salah, sebesar tepat nilai `total_dibayar` yang hilang | seharusnya 3.255.000, sistem melaporkan 6.255.000 (selisih 3.000.000) |
| 5 | ID `hociro.upah.line` berubah setiap regenerate (record lama dihapus, bukan diupdate) | id Staf A: 1 → 4 → 7 pada periode yang sama |
| 6 | Recompute `hari_hadir`/`hari_disiplin`/`upah_kotor` mengikuti absensi terbaru | bekerja benar — bukan bug |

## Dampak

### Finansial
Pembayaran yang sudah dicatat (`total_dibayar`) hilang diam-diam setiap kali periode di-regenerate setelah pembayaran diinput. Staf yang sudah dibayar akan terlihat seolah masih berhutang penuh (`saldo_akhir` naik kembali ke nilai sebelum dibayar). Bonus dan lembur manual yang sudah disetujui juga hilang, sehingga `upah_kotor` yang dilaporkan lebih kecil dari yang seharusnya dibayarkan.

### Referensial
Karena line lama di-`unlink()` (bukan diupdate), ID `hociro.upah.line` berubah setiap regenerate. Ini berisiko memutus referensi dari record lain yang menunjuk ke line spesifik (mis. bukti pembayaran, lampiran, atau modul kasbon di masa depan — lihat catatan TODO di bawah).

### Silent failure
Tidak ada `UserError`, warning, atau konfirmasi apa pun ke user saat regenerate menimpa data manual yang sudah ada. `action_hitung_upah()` bisa dipanggil ulang tanpa hambatan pada periode berstatus `dihitung` (state normal sebelum `ditutup`), sehingga user tidak tahu data hilang kecuali mengecek manual satu per satu.

## Catatan: TODO Existing di Kode

Kode sudah punya catatan TODO yang relevan langsung dengan bug ini, di `models/hociro_periode_upah.py` baris 190–197 pada definisi field `total_dibayar`:

```python
# TODO: ganti jadi computed field setelah hociro.pembayaran dibangun
# Saat ini diinput manual sebagai bridge dari Excel lama
total_dibayar = fields.Monetary(
    string='Total Dibayar',
    currency_field='currency_id',
    default=0.0,
    help='Diisi manual. Akan otomatis dari pembayaran setelah modul kasbon jadi.',
)
```

Ini menunjukkan bahwa sifat "manual" dari `total_dibayar` sudah disadari sebagai kondisi sementara (bridge), dan rencana jangka panjangnya adalah menjadikannya computed field begitu modul `hociro.pembayaran` (kasbon) dibangun — yang mana secara alami akan menghilangkan sumber bug ini untuk `total_dibayar` (karena nilainya akan dihitung ulang dari record pembayaran, bukan disimpan sebagai state manual yang rawan ter-unlink). Namun TODO ini **tidak mencakup** `bonus` dan `hari_lembur_staf`, yang punya masalah persis sama dan belum ada rencana perbaikan tercatat di kode.

## Yang Belum Dilakukan

Tidak ada perubahan kode pada laporan ini — murni dokumentasi temuan dari pengujian di `test_bersih_5`. Opsi perbaikan (mis. mengubah `action_hitung_upah()`/`_prepare_line_vals()` untuk update line existing per `employee_id` alih-alih unlink+create, sambil membawa forward `bonus`/`hari_lembur_staf`/`total_dibayar` dari line lama) belum diimplementasikan dan sebaiknya dikonfirmasi desainnya dulu sebelum dikerjakan.
