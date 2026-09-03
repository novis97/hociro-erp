# Spesifikasi Modul — `hociro_upah`

**Versi:** draft 1
**Target:** Odoo 19.0 Community
**Dependency:** `hr`, `analytic` — tidak ada yang lain
**Prasyarat baca:** `docs/v19-conventions.md`

---

## 1. Ruang Lingkup

Modul ini menggantikan tiga file Excel yang berjalan sekarang:

| File sekarang | Digantikan oleh |
|---|---|
| `01__Absen_harian_tukang.xlsx` sheet ABSEN | `hociro.absensi.tukang` |
| sheet REKAP | `hociro.periode.upah` + `hociro.upah.line` |
| sheet KASBON | `hociro.pembayaran` |
| `ABSENSI_2026B_studio (Responses)` | `hociro.absensi.staf` |
| `00__STUDIO.xlsx` sheet DATABASE/TOTAL | `hociro.periode.upah` (tipe bulanan) |

**Tidak memakai** `hr_payroll` maupun OCA `payroll`. Tidak ada PPh 21, tidak ada BPJS, tidak ada slip pajak.

---

## 2. Temuan dari Data Lama yang Membentuk Desain

Poin-poin ini berasal dari pembacaan file aktual. Jangan diubah tanpa verifikasi ulang ke sumber.

1. **Absensi tukang berbutir setengah hari.** Kolom Pagi dan Siang terpisah, masing-masing bernilai 0, 0.5, atau 1. Hari kerja = (Pagi + Siang) / 2. Terverifikasi: Hendra Pagi=17, Siang=18 → 17,5 hari.
2. **Lembur bertarif flat per hari, bukan kelipatan upah.** Alfin upah 130.000, lembur 100.000. Hendra upah 200.000, lembur 100.000.
3. **Gaji staf bukan nilai tetap.** Komponen: Pokok (tetap) + Harian (× hari hadir) + Disiplin (× hari tepat waktu) + Transpor (× hari) + Lembur + Bonus.
4. **Disiplin bergantung jam datang, bukan kehadiran.** Rahmad April: hadir 21 hari, Disiplin 13 hari.
5. **Sheet KASBON adalah buku pembayaran, bukan daftar pinjaman.** Upah mingguan reguler ikut dicatat di sana dengan keterangan "Mingguan".
6. **Tidak ada jadwal angsuran.** Saldo = total upah − total seluruh pembayaran. Bisa negatif (pekerja terbayar lebih).
7. **Satu tukang, satu hari, satu proyek.** Tidak ditemukan kasus pagi di proyek A dan siang di proyek B. *Asumsi — konfirmasi ke pengawas.*

---

## 3. Model

### 3.1 `hociro.kantong`

Menggantikan kolom "sumber uang". Dipecah dari kolom lama karena isinya bercampur.

| Field | Tipe | Catatan |
|---|---|---|
| `name` | Char, required | Nama kantong |
| `kode` | Char, required, unique | AND, BKL, TMN, OPK, JBL, ILH, hff, moru |
| `tipe` | Selection | `utama` / `proyek` / `operasional` |
| `proyek_id` | Many2one `account.analytic.account` | Diisi hanya bila `tipe = proyek` |
| `active` | Boolean | Arsip, jangan hapus |

Satu kantong boleh terikat ke satu proyek, tapi pengeluaran untuk proyek A **boleh** didanai kantong proyek B. Jangan tambahkan constraint yang melarangnya.

### 3.2 `account.analytic.account` (pakai model core)

Proyek disimpan di analytic account pada Plan **Project**. Tidak membuat model proyek sendiri.

Field tambahan:

| Field | Tipe | Catatan |
|---|---|---|
| `x_trade_name` | Selection | `hociro` / `hananikasha` |
| `x_kode_lama` | Char | Nilai kolom Tempat di Excel lama, untuk migrasi |

### 3.3 `hr.employee` (extend)

| Field | Tipe | Berlaku untuk |
|---|---|---|
| `x_tipe_pekerja` | Selection `staf` / `tukang` | semua |
| `x_upah_harian` | Monetary | tukang |
| `x_tarif_lembur` | Monetary | tukang & staf — flat per hari |
| `x_gaji_pokok` | Monetary | staf |
| `x_tarif_harian` | Monetary | staf |
| `x_tarif_disiplin` | Monetary | staf |
| `x_tarif_transpor` | Monetary | staf |
| `x_batas_jam_disiplin` | Float (widget `float_time`) | staf — default 08:00 |

Tarif berubah dari waktu ke waktu (Rahmad: 80.000 di April, 85.000 di database terbaru). Nilai di sini adalah tarif **berlaku sekarang**. Riwayat tarif disimpan di `hociro.upah.line` saat periode dihitung, sehingga periode lama tidak ikut berubah kalau tarif dinaikkan.

### 3.4 `hociro.absensi.tukang`

| Field | Tipe | Catatan |
|---|---|---|
| `tanggal` | Date, required | |
| `employee_id` | Many2one `hr.employee`, required | domain `x_tipe_pekerja = tukang` |
| `proyek_id` | Many2one `account.analytic.account` | domain Plan = Project |
| `sesi_pagi` | Selection `0` / `0.5` / `1` | default `1` |
| `sesi_siang` | Selection `0` / `0.5` / `1` | default `1` |
| `lembur` | Float | dalam satuan hari, umumnya 0 / 0.5 / 1 |
| `hari_kerja` | Float, compute, store | `(pagi + siang) / 2` |
| `pengawas_id` | Many2one `res.users` | default user saat ini |
| `state` | Selection `draft` / `dikuatkan` | |
| `catatan` | Char | untuk kasus seperti "ikut b Dedek" |

**Constraint:** unik pada (`tanggal`, `employee_id`).

**Alur:** input oleh pengawas → `draft`. Dikuatkan → `dikuatkan`. Hanya baris `dikuatkan` yang masuk perhitungan upah. Ini memindahkan proses "pengakuan kuli dikuatkan catatan pengawas" yang sudah berjalan, bukan membuat prosedur baru.

**Wizard input massal:** pilih tanggal + proyek → tampil daftar tukang aktif → centang dan isi pagi/siang sekaligus. Tanpa ini pengawas tidak akan memakai sistem.

### 3.5 `hociro.absensi.staf`

| Field | Tipe | Catatan |
|---|---|---|
| `tanggal` | Date, required | |
| `employee_id` | Many2one, required | domain `x_tipe_pekerja = staf` |
| `status` | Selection | `hadir` / `izin` / `sakit` / `cuti` / `alfa` — memetakan H/I/S/C di Excel |
| `jam_masuk` | Float (`float_time`) | |
| `dapat_disiplin` | Boolean, compute, store | `status = hadir AND jam_masuk <= x_batas_jam_disiplin` |
| `foto` | Image | menggantikan foto jempol di Google Form |
| `proyek_id` | Many2one | **OPEN ITEM — lihat §6** |

**Constraint:** unik pada (`tanggal`, `employee_id`).

### 3.6 `hociro.pembayaran`

Menggantikan sheet KASBON. Mencatat **seluruh** uang keluar ke pekerja, apa pun bentuknya.

| Field | Tipe | Catatan |
|---|---|---|
| `tanggal` | Date, required | |
| `employee_id` | Many2one, required | |
| `kategori` | Selection, required | `mingguan`, `bulanan`, `berangkat`, `tambahan`, `kasbon`, `pelunasan`, `harian`, `uang_makan`, `uang_lembur`, `lainnya` |
| `jumlah` | Monetary, required | |
| `kantong_id` | Many2one `hociro.kantong` | dari kolom "sumber uang" |
| `metode_bayar` | Selection | `cash` / `transfer` / `ewallet` |
| `proyek_id` | Many2one | opsional |
| `catatan` | Char | untuk anotasi seperti "(200 kasbon; 300 grek)" |

Kolom lama "sumber uang" berisi campuran kantong dan metode bayar. Saat migrasi, `cash`/`tf-bri`/`tf-gopay` masuk ke `metode_bayar`, sisanya ke `kantong_id`.

### 3.7 `hociro.periode.upah` dan `hociro.upah.line`

**Periode:**

| Field | Tipe |
|---|---|
| `name` | Char |
| `tipe` | Selection `mingguan` / `bulanan` |
| `tanggal_mulai`, `tanggal_selesai` | Date |
| `state` | Selection `draft` / `dihitung` / `ditutup` |
| `line_ids` | One2many |

Mingguan untuk tukang, ditutup tiap Sabtu. Bulanan untuk staf, ditutup akhir bulan.

**Line — tukang:**

| Field | Sumber |
|---|---|
| `hari_kerja` | Σ `hociro.absensi.tukang.hari_kerja` yang `dikuatkan` dalam periode |
| `hari_lembur` | Σ `lembur` |
| `tarif_harian`, `tarif_lembur` | disalin dari employee saat hitung |
| `upah_kotor` | `hari_kerja × tarif_harian + hari_lembur × tarif_lembur` |

**Line — staf:**

| Field | Rumus |
|---|---|
| `hari_hadir` | jumlah absensi berstatus `hadir` |
| `hari_disiplin` | jumlah absensi `dapat_disiplin = True` |
| `upah_kotor` | `gaji_pokok + (hari_hadir × tarif_harian) + (hari_disiplin × tarif_disiplin) + (hari_hadir × tarif_transpor) + (hari_lembur × tarif_lembur) + bonus` |

**Bersama:**

| Field | Rumus |
|---|---|
| `saldo_awal` | `saldo_akhir` periode sebelumnya |
| `total_dibayar` | Σ `hociro.pembayaran` untuk pekerja ini dalam rentang periode |
| `saldo_akhir` | `saldo_awal + upah_kotor − total_dibayar` |

Saldo negatif berarti pekerja sudah dibayar melebihi upahnya. Kondisi ini nyata di data lama (Hendra −1.500.000, Heri −200.000) dan **harus ditampilkan menonjol**, bukan disembunyikan.

**Peringatan wajib:** tampilkan indikator merah bila `saldo_akhir < -(2 × tarif_harian × 6)`. Sistem tidak memblokir pembayaran — keputusan tetap di tangan pemilik — tapi angkanya harus terlihat.

---

## 4. Laporan Minimum

1. **Rekap periode** — pivot: pekerja × hari kerja × upah × dibayar × saldo. Pengganti sheet REKAP.
2. **Biaya tenaga kerja per proyek** — pivot: proyek × bulan × total upah. Belum pernah ada di Excel; ini nilai tambah pertama yang terasa buat klien.
3. **Mutasi kantong** — pivot: kantong × bulan × total keluar. Menjawab pertanyaan "kantong mana yang terpakai untuk apa".
4. **Saldo berjalan per pekerja** — list dengan saldo terkini, diurut menaik agar yang paling minus muncul di atas.

---

## 5. Migrasi Data

Sumber: `Salinan_01__Absen_harian_tukang.xlsx` dan tujuh file studio.

Urutan:
1. Master kantong dan proyek dibuat manual lebih dulu, termasuk pemetaan `x_kode_lama`
2. Master pekerja + tarif
3. Absensi tukang — parsing per blok bulan, langsung berstatus `dikuatkan`
4. Pembayaran dari sheet KASBON
5. Rekonsiliasi: saldo hasil sistem harus sama dengan kolom SISA di Excel

**Catatan penting untuk langkah 5:** total di sheet REKAP salah. Rumus SUM berhenti sebelum baris 17 sehingga Tukang Baru 2, Ihsan, Anak B Dedek, dan Bg Aje tidak terhitung. Angka acuan yang benar adalah Rp84.090.000 (upah) dan Rp84.450.000 (dibayar), bukan Rp68.370.000 dan Rp70.070.000. Jangan pakai angka Excel sebagai target rekonsiliasi.

---

## 6. Open Item — Harus Diputuskan Sebelum Coding

**6.1 Pemetaan Tempat lama ke proyek.** Nilai berikut belum punya padanan di daftar proyek: Travel (45×), Gudang (18×), Pango (4×), Pak Karno (3×), Roti (2×), TMN. Perlu diputuskan mana yang jadi proyek, mana yang jadi kategori non-proyek (mis. kegiatan internal).

**6.2 Trade name per proyek.** Dugaan awal, perlu dikoreksi:

| Hociro (desain) | Hananikasha (konstruksi) |
|---|---|
| Desain Auditorium FKM | Finishing Moru |
| Hukum Unmuha | Finishing Bukulah |
| Bappeda Jantho | SP. Jambo Tape |
| Kerria (?) | Rumah Lampineung |
| Hilani (?) | Kosan Tanggul |
| | Rumah Geuceu |
| | Nasgor AM PM |

**6.3 Apakah absensi staf perlu dimensi proyek?** Google Form sekarang hanya mencatat nama, tanggal, keterangan, dan foto — tanpa proyek. Menambahkan proyek berarti perilaku baru bagi staf studio dan berisiko ditolak. Tanpa itu, biaya tenaga kerja desain tidak bisa dialokasikan ke proyek.

Saran: jangan tambahkan di Fase 1. Jalankan dulu apa adanya, tunjukkan laporan biaya proyek untuk sisi konstruksi, lalu ajukan penambahan setelah klien merasakan manfaatnya.

**6.4 Daftar kantong lengkap.** Kode AND, TMN, ILH, hff belum diketahui artinya. Perlu dikonfirmasi ke klien sebelum master kantong dibuat.

---

## 7. Yang TIDAK Dibangun di Fase Ini

- Perhitungan PPh 21 dan BPJS
- Slip gaji berformat pajak
- Integrasi ke jurnal akuntansi — pembayaran dicatat di modul ini dulu, penjurnalan menyusul di fase berikutnya
- Absensi berbasis lokasi atau biometrik
- Portal self-service pekerja

---

*Dokumen ini adalah input untuk Agent 2. Perubahan desain hanya lewat Agent 1.*
