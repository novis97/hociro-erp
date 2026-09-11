# Session Log — 2026-09-03 s/d 2026-09-11

Catatan status kerja di repo `hociro-erp`, ditulis di akhir sesi supaya sesi berikutnya (siapa pun yang melanjutkan — manusia atau agent) tidak perlu membaca ulang seluruh transkrip.

---

## -6. Update 2026-09-11 — Guard issue #1 + #2 diimplementasikan dan terverifikasi; `test_bersih_5` tidak lagi valid sebagai baseline

**Konteks:** dua sesi — Agent 2 (dev lokal) menulis implementasi, Agent 3 (VPS) mengujinya di database salinan terisolasi. Issue #2 tuntas sepenuhnya. Issue #1 tertutup sebagian; sisanya menunggu issue #4.

### Implementasi

Dua commit, keduanya hanya menyentuh `addons/hociro_upah/models/hociro_periode_upah.py`:

- **`54f9dad`** (issue #2) — predecessor lock (`_get_pendahulu_belum_ditutup`, `_check_predecessor_lock`), successor lock (`_get_penerus`, `_check_successor_lock`), guard di `action_buka_kembali()`, line saldo-only untuk karyawan archived, dan pemindahan `vals_list = _prepare_line_vals()` ke atas `unlink()`.
- **`11bb807`** (issue #1) — guard nilai manual `_check_nilai_manual()` + `_format_rupiah()`, dan `float_compare` ditambahkan ke import dari `odoo.tools`.

Struktur `action_hitung_upah()` sekarang: guard `state == 'ditutup'` (sudah ada sebelumnya) → predecessor lock → successor lock → `_prepare_line_vals()` → guard nilai manual → `unlink()` → `create()` → `state = 'dihitung'`. **Keempat guard dievaluasi sebelum satu line pun dihapus.**

Pemindahan `_prepare_line_vals()` diletakkan di commit issue #2 walaupun kebutuhannya berasal dari issue #1, supaya method itu tidak direstrukturisasi dua kali antar commit. Keputusan Agent 2, disetujui — riwayat git yang rapi per nomor issue tidak sebanding dengan kode yang dibongkar-pasang untuk memenuhinya.

### Keputusan desain: guard nilai manual pakai perbandingan, bukan "≠ 0"

Dua field yang dijaga: **`total_dibayar`** dan **`saldo_awal`**. Bukan tiga. `hari_lembur_staf` dikeluarkan karena tidak pernah dirender di view mana pun sehingga tidak bisa terisi siapa pun; `bonus` dikeluarkan karena akan pindah ke `hociro.upah.penyesuaian` (issue #4).

Aturannya: blokir kalau nilai tersimpan **berbeda dari nilai yang akan dihasilkan `_prepare_line_vals()`** untuk karyawan itu, dibandingkan dengan `float_compare(..., precision_rounding=currency.rounding)`.

Bukan "≠ 0", dan ini penting. Untuk `total_dibayar` hasil prepare selalu nol jadi kedua aturan setara. Tapi `saldo_awal` bukan-nol adalah **kondisi normal** periode kedua dan seterusnya (hasil carry-over yang sah) — aturan "≠ 0" akan menyala hampir selalu dan tombol Hitung Ulang praktis tidak bisa dipakai. Gejalanya bukan error, jadi tidak akan tertangkap checklist §5 dan baru ketemu saat user memakainya.

`float_compare` dipakai, bukan operator `!=` mentah pada float, karena selisih pembulatan akan memicu false positive.

### Hasil uji (Agent 3, database salinan `test_guard_1_2`)

Isolasi: clone `repo-prototipe` dipindahkan dari branch prototipe ke `main` (`git checkout main && git reset --hard origin/main`, verifikasi `11bb807` → `54f9dad` → `50e9b7a`), database salinan dibuat `createdb -T test_bersih_5`, container `odoo:19.0` sekali pakai. `/opt/hociro-erp/repo` tidak pernah pindah branch — dia bind-mounted ke Odoo production.

**Checklist §5 poin instalasi: LOLOS.** `odoo -u hociro_upah` sukses, 0.24s, 289 queries, tanpa traceback. Tidak ada `ImportError` pada `float_compare`/`float_is_zero` — satu-satunya asumsi API yang belum diverifikasi sebelumnya, sekarang tertutup.

| Uji | Hasil |
|---|---|
| B — guard nilai manual menyala saat seharusnya | LOLOS. `total_dibayar` Rp 1.500.000 → `UserError` "Staf A (Dummy) — Total Dibayar: Rp 1.500.000", line id `[13,14,15]` identik sebelum/sesudah. `saldo_awal` ditimpa 9.999.999 → pesan memuat **dua** pelanggaran sekaligus, dengan format "Rp 9.999.999 (hitungan otomatis: Rp 6.555.000)". Line id `[10,11,12]` identik. |
| C — successor lock | LOLOS. Penerus ber-line → `action_hitung_upah()` dan `action_buka_kembali()` keduanya `UserError` menyebut nama penerus. Penerus **kosong** → sukses, tidak diblokir. Tanpa penerus → sukses. Setelah penerus diisi line → baru diblokir. |
| D — predecessor lock | LOLOS. Pendahulu `draft` → `UserError` menyebut namanya, `line_ids` tetap `[]`. Setelah pendahulu ditutup → sukses, 3 line dibuat (id 22-24). Periode pertama tanpa pendahulu → tidak diblokir. |
| E — line saldo-only | LOLOS. Staf C archived dengan `saldo_akhir` 11.460.000 → tetap dapat line: `hari_hadir=0`, `upah_kotor=0`, `saldo_awal=11.460.000`. Staf B archived dengan `saldo_akhir=0` → tidak dapat line. |
| F — skenario asli bug doc | LOLOS. `total_dibayar` 3.000.000 + koreksi absensi: dulu terhapus diam-diam, sekarang `UserError`, line id tetap 13, nilai tetap tersimpan. |

### Uji A: guard menangkap kerusakan data lama, bukan gagal

Uji A (periode kedua dengan `saldo_awal` carry-over normal harus **tidak** terblokir) awalnya dilaporkan gagal. Penyebabnya bukan guard.

Di `test_bersih_5`, Staf A di Bulanan 2026-08 punya `saldo_awal` tersimpan **6.255.000**, sementara `saldo_akhir` Staf A di Bulanan 2026-07 adalah **6.120.000**. Selisih 135.000. Staf B dan C cocok persis.

Itu **stale saldo yang tertinggal dari bug #2 sendiri** — sisa skenario buka-kembali yang dipakai untuk menemukan bug itu di sesi 2026-09-10 (§-2). Jadi guard baru mendeteksi kerusakan data yang ditinggalkan bug lama, di database yang sudah ada sebelum guard-nya ditulis.

Diagnostik Agent 3 memisahkan kedua penyebab: setelah `saldo_awal` Staf A dinetralkan ke 6.120.000, `action_hitung_upah()` pada periode yang sama **sukses** dengan hasil identik sebelum/sesudah. Guard-nya benar; datanya yang rusak.

### PENTING: `test_bersih_5` tidak lagi valid sebagai baseline regresi

§-2 mencatat carry-over saldo di `test_bersih_5` "diuji dan LOLOS". Itu benar untuk keadaan Juli→Agustus **sebelum** skenario buka-kembali dijalankan, tapi **tidak benar untuk keadaannya sekarang** — `saldo_awal` Staf A di periode Agustus salah 135.000.

Sesi berikutnya yang memakai `test_bersih_5` sebagai baseline perbandingan akan mendapat angka yang salah, dan kemungkinan menyimpulkan ada regresi di kode padahal datanya yang rusak.

Opsi yang belum diputuskan: netralkan `saldo_awal` Staf A ke 6.120.000 (satu `UPDATE`, memulihkan konsistensi), atau buat database uji baru dari nol dengan seed yang terdokumentasi. Yang kedua lebih bersih tapi berarti kehilangan data uji yang sudah ada. **Belum dikerjakan — jangan pakai `test_bersih_5` sebagai pembanding angka sebelum ini diselesaikan.**

### Temuan: line saldo-only menutup celah di guard nilai manual

`_check_nilai_manual()` memakai `prepared_by_employee.get(line.employee_id.id, {})`, jadi karyawan yang punya line sekarang tapi tidak ada di `vals_list` akan mendapat `prepared_saldo_awal = 0.0` — dan kalau `saldo_awal` line-nya bukan-nol, guard menyala dengan pesan "hitungan otomatis: Rp 0" yang tidak menjelaskan bahwa karyawan itu akan keluar dari periode.

Diuji dengan tukang sintetis, dua periode mingguan berurutan, absensi periode kedua dikoreksi (`dikuatkan` → `draft`). **Celahnya tidak muncul**: line saldo-only dari issue #2 menangkapnya lebih dulu — karyawan dengan `saldo_akhir` bukan-nol selalu dapat line, jadi selalu ada di `vals_list`, jadi `.get(..., {})` tidak pernah jatuh ke default. `prepared_saldo_awal` terisi benar (150.000 = 150.000, cocok), guard tidak menyala.

**Dua guard yang dirancang untuk masalah berbeda saling menutup celah satu sama lain. Ini kebetulan, bukan desain — dan justru karena kebetulan, harus ditulis.** Kalau nanti line saldo-only dihapus atau kondisinya diubah (mis. saat implementasi issue #4 menyentuh `_prepare_line_vals()`), celah itu terbuka lagi dan tidak ada yang tahu kaitannya.

Batas yang masih berlaku: celah itu tetap bisa muncul kalau `saldo_akhir` periode pendahulu **sendiri** sudah stale — yaitu varian Uji A, bukan lubang independen. Dan jalur itu sekarang tertutup oleh successor lock.

### Status issue

- **Issue #2 — tuntas.** Bisa ditutup. Semua AC terverifikasi, tidak ada sisa.
- **Issue #1 — tertutup sebagian, tetap OPEN.** Guard melindungi `total_dibayar` (bridge sampai `hociro.pembayaran`) dan `saldo_awal`. Akar masalahnya — hasil kalkulasi dan input manusia disimpan di record yang sama — baru hilang setelah `hociro.upah.penyesuaian` (issue #4). Tutup setelah #4 selesai.

### Berikutnya

Urutan yang dikunci di §-4 tidak berubah: **issue #4** (`hociro.upah.penyesuaian`), lalu issue #3 (`hociro.parameter.karyawan`).

Prasyarat issue #4 sudah tuntas semua (§-5). Yang perlu diingat saat implementasi:
- Komentar di kode prototipe baris 20-23 **salah** dan harus dikoreksi (§-5).
- **Jangan** `ondelete='cascade'` pada `line_id` — hanya untuk `periode_id` (§-5).
- Constraint unik `(periode_id, employee_id)` masuk scope, bentuknya `models.Constraint` bukan `_sql_constraints` (§-5).
- Issue #4 menyentuh `_prepare_line_vals()`; jangan sampai mengubah kondisi line saldo-only tanpa menyadari kaitannya dengan guard nilai manual (lihat temuan di atas).

Aturan parkir `x_batas_jam_disiplin` **tetap berlaku** sampai issue #3 selesai.

### Catatan clone di VPS

`/opt/hociro-erp/repo-prototipe` sekarang di branch **`main`** (sebelumnya `prototipe/penyesuaian-line-id`). Branch prototipe masih ada di origin. Clone ini dipakai ulang untuk uji-uji berikutnya supaya `repo/` tidak pernah pindah branch — **bukan sisa yang terlupakan.**

Database `test_guard_1_2` sudah di-drop.

---

## -5. Update 2026-09-11 — Prasyarat issue #4 tuntas: nol migrasi, constraint unik masuk scope, mekanisme `line_id` terbukti

**Konteks:** dua sesi terpisah (Agent 3 di VPS untuk verifikasi data + uji prototipe, Agent 2 di dev lokal untuk komentar issue + branch prototipe). Semua prasyarat sebelum implementasi issue #4 sekarang tuntas. Tidak ada perubahan kode di `main`.

### Verifikasi data production (`hociro_prod`)

Satu-satunya periode di production: **id=1, Mingguan 2026-W24** (2026-06-14 s/d 2026-06-20), state `dihitung`, 7 line. **Tidak ada periode bertipe `bulanan` di production** — periode bulanan sejauh ini hanya ada di `test_bersih_5`.

Seluruh 7 line: `bonus` = 0, `total_dibayar` = 0, `saldo_awal` = 0. Nol data manual.

→ **Issue #4 tidak butuh langkah migrasi data.** Bagian "Migrasi" dihapus dari scope-nya.

Catatan: **Wak Andi** dan **Anak Bang Dedek** muncul dengan `saldo_akhir` = 0 karena belum punya tarif (lihat §-1). Konsekuensi yang sudah diketahui: begitu Mr. Ricoh memberi tarif mereka, W24 harus dihitung ulang — dan saat itu guard issue #1 serta predecessor/successor lock issue #2 sudah berlaku, jadi jalurnya akan berbeda dari sekarang.

### Temuan: `(periode_id, employee_id)` tidak dijamin unik

Tidak ada unique constraint pada `(periode_id, employee_id)` di `hociro.upah.line` — tidak di Postgres (hanya PK pada `id` + FK biasa), tidak di model. Faktanya nol duplikat di `hociro_prod` maupun `test_bersih_5`, dan `_prepare_line_vals()` tidak bisa menghasilkan duplikat lewat jalur normal karena `employees` berasal dari recordset yang otomatis terdeduplikasi (`mapped()` / `search()`). Tapi itu jaminan **by convention**, bukan struktural: `create()` langsung, import, atau modul lain bisa menghasilkan duplikat.

Ini bukan detail kebersihan. `line_id` computed pada `hociro.upah.penyesuaian` melakukan lookup berdasarkan `(periode, employee)`. Dua line berarti lookup mengembalikan salah satu secara arbitrer, dan penyesuaian menempel ke line yang mungkin bukan yang dilihat user — gejalanya "bonus tidak muncul" atau "muncul di baris yang salah", tanpa error, tanpa jejak.

→ **Constraint unik masuk scope issue #4.** Bentuknya **`models.Constraint`, bukan `_sql_constraints`** (dihapus di Odoo 19 — lihat `v19-conventions.md` §1.9, sudah pernah memicu warning di modul ini). Mengikuti pola `hociro_absensi_tukang.py:46` / `hociro_absensi_staf.py:36`. Nol duplikat di kedua database berarti migrasi constraint harus lolos di percobaan pertama.

### Branch prototipe

Branch **`prototipe/penyesuaian-line-id`** dibuat Agent 2 dari `main` dan di-push ke origin. **Tidak di-merge**, `main` tetap di `92e34be`. Isinya minimal: model `hociro.upah.penyesuaian` (`periode_id`, `employee_id`, `nilai`, `line_id` computed store), `penyesuaian_ids` One2many di `hociro.upah.line`, pemanggilan recompute eksplisit setelah `create()` di `action_hitung_upah()`, satu baris access rights. Tanpa view, tanpa jenis `koreksi`, tanpa perhitungan `upah_kotor` — hanya secukupnya untuk mengamati mekanismenya.

Checklist §5 `v19-conventions.md` poin grep lolos semua. Poin instalasi dijalankan Agent 3 di VPS (mesin dev tidak punya Odoo/Docker lokal).

### Uji mekanisme `line_id` — LOLOS

Dijalankan di **database salinan `test_prototipe`** (dibuat `createdb -T` dari `test_bersih_5`), lewat **container `odoo:19.0` sekali pakai** (`--rm`) yang mount `repo-prototipe/addons` → `/mnt/extra-addons`, join network `hociro-erp_default`. Alasan isolasi ini: `/opt/hociro-erp/repo` bind-mounted ke Odoo production, jadi `git checkout` branch di situ akan membuat kode dan skema `hociro_prod` tidak sinkron. Dan `test_bersih_5` tidak dipakai langsung karena memuat hasil verifikasi carry-over saldo (§-2) yang harus tetap utuh sebagai referensi.

Periode uji: id=2, tipe `bulanan`, state `dihitung` (data `test_bersih_5`, bukan production).

| Tahap | Nilai |
|---|---|
| Line lama sebelum hitung ulang | id=10, employee_id=2 (Staf A) |
| `penyesuaian.line_id` setelah create | 10 — cocok |
| Line baru setelah `action_hitung_upah()` | id=22 |
| Line lama id=10 masih ada? | tidak, sudah terhapus |
| `line_id` di kolom DB mentah, dibaca `cr.execute()` **sebelum** disentuh Python | **22** |
| `_compute_line_id()` dipanggil manual | 22 (sama) |
| `employee_id` pada penyesuaian | 2 (Staf A), tidak berpindah |

Pembacaan lewat SQL mentah itu penting: dia menutup kemungkinan bahwa recompute terpicu oleh akses ORM di skrip ujinya sendiri. Nilainya sudah benar di database sebelum Python menyentuh record itu.

**Catatan: percobaan pertama crash `MissingError`** karena skrip uji menyimpan referensi recordset lama melintasi `action_hitung_upah()` lalu mengaksesnya. Itu bug di skrip uji, bukan di prototipe; transaksi ter-rollback penuh dan diverifikasi bersih sebelum diulang dengan skrip yang menyimpan `employee_id` sebagai integer biasa.

### Temuan perilaku ORM yang membatalkan asumsi di issue #4

Issue #4 menyatakan pemanggilan recompute eksplisit setelah `create()` **wajib**, dengan alasan `line_id` bergantung pada `periode_id`/`employee_id` yang tidak berubah saat line dibuat ulang. **Asumsi itu salah.** Odoo ternyata tetap memicu recompute pada field Many2one computed+stored saat record yang ditunjuknya di-`unlink`, terlepas dari `@api.depends` yang dideklarasikan. Dugaan mekanismenya: ORM menandai field computed+stored yang menunjuk ke record terhapus sebagai "to recompute" (bukan sekadar `SET NULL` di level FK), lalu memicu compute ulang pada flush berikutnya — di sini terpicu oleh `create()` line baru dalam `action_hitung_upah()` yang sama.

**Konsekuensi untuk implementasi — pemanggilan eksplisit tetap dipertahankan**, tapi statusnya berubah dari "wajib" jadi "jaring pengaman yang idempoten". Alasannya: perilaku di atas adalah detail internal ORM, tidak terdokumentasi, dan bisa berubah di versi Odoo berikutnya. Uji membuktikan `_compute_line_id()` manual menghasilkan nilai sama (22), jadi memanggilnya tidak merugikan.

**Komentar di kode prototipe baris 20-23 SALAH dan harus dikoreksi saat implementasi penuh** — komentar itu menyatakan recompute "sengaja tidak bisa menangkap" kasus line lama dihapus/line baru dibuat. Komentar yang salah lebih berbahaya daripada tidak ada komentar.

### Catatan FK `line_id`

`line_id` terbentuk sebagai FK dengan **`ON DELETE SET NULL`** (default Odoo untuk Many2one non-required). Ini perilaku yang diinginkan: penyesuaian tidak ikut terhapus saat line di-unlink, dia jadi NULL sementara lalu terisi ulang.

**Jangan menambahkan `ondelete='cascade'` pada `line_id`** di implementasi penuh — kalau iya, penyesuaian terhapus bersama line dan seluruh mekanismenya gagal. `ondelete='cascade'` hanya untuk `periode_id`.

### Sisa yang sengaja dibiarkan di VPS dan origin

- **`/opt/hociro-erp/repo-prototipe`** — clone kedua, branch `prototipe/penyesuaian-line-id`. Dibiarkan, mungkin masih dibutuhkan. **Bukan sisa yang terlupakan.**
- Branch **`prototipe/penyesuaian-line-id`** di origin — dibiarkan sampai implementasi penuh selesai, baru dibuang.
- Database `test_prototipe` **sudah di-drop** setelah uji.

### Pembersihan git di VPS

`/opt/hociro-erp/repo` sebelumnya diverge dari `origin/main` (2 commit lokal vs 4 di origin) — sisa dari `git am` di mesin lain yang mengubah hash. Diverifikasi dulu bahwa isi kedua commit lokal sudah ada di origin (`git diff HEAD origin/main` pada kedua file: bug doc nol perbedaan; session-log hanya dua baris yang memang sengaja diganti — judul lama dan baris penutup lama), baru `git reset --hard origin/main`. Sekarang sinkron di `92e34be`, working tree bersih.

`reset --hard` aman di sini hanya karena dua hal yang keduanya sudah terverifikasi: working tree bersih, dan isi commit lokal sudah ada di origin. Bukan perintah yang boleh jadi kebiasaan.

### Status

**Semua prasyarat issue #4 tuntas.** Implementasi penuh bisa dimulai. Urutan yang sudah dikunci di §-4 tidak berubah: issue #1 + #2 (guard) → issue #4 → issue #3.

Aturan parkir `x_batas_jam_disiplin` **tetap berlaku** sampai issue #3 selesai.

### Catatan operasional VPS (belum dikerjakan)

- Banner login masih menampilkan `*** System restart required ***`, dan jumlah update tertunda bergeser (68 → 63) — artinya ada paket teraplikasi tanpa restart, jadi server berjalan dengan kernel lama sementara paketnya sudah baru. **Perlu dijadwalkan**, karena restart berarti Odoo down sebentar. Bukan keputusan yang boleh diambil agent di tengah sesi kerja.
- Login ke VPS masih sebagai `root`, dan sandbox Claude Code di mesin itu mati. Kombinasi itu berarti dialog "allow reads outside working directories" sebaiknya selalu dijawab "sekali ini saja", bukan "selalu".
- `~/.ssh` di mesin dev Windows memuat 8 file kunci tanpa label jelas, termasuk `id_rsa` lama. Kunci untuk VPS ini adalah `id_ed25519_103_77_106_214`, sekarang sudah terdaftar di `~/.ssh/config` sebagai host `hociro`. Sisanya layak dibersihkan — catatan, bukan tugas mendesak.
- Folder induk di mesin dev sudah di-rename dari `erp-hociro` menjadi **`odoo-hociro`** supaya tidak tertukar dengan repo `hociro-erp` (dua nama yang cuma beda urutan kata sudah dua kali menyebabkan perintah git dijalankan di direktori yang salah). Repo git tetap bernama `hociro-erp`.

---

## -4. Update 2026-09-11 — Verifikasi kode Agent 3, empat keputusan dikunci, issue #4 dibuat

**Konteks:** sesi ini (Claude Code Desktop, dev lokal) menindaklanjuti §-3 di atas. Agent 3 sudah memverifikasi langsung ke kode nama field dan asumsi yang sebelumnya belum dicek di issue #2, dan verifikasi itu juga menyingkap dua masalah baru pada field input manual (`bonus`, `hari_lembur_staf`). Tidak ada perubahan kode di sesi ini — murni dokumentasi dan issue GitHub.

**Hasil verifikasi kode Agent 3:**
- Field pembeda siklus periode adalah **`tipe`** (bukan `tipe_periode` seperti diasumsikan sebelumnya), nilai `mingguan`/`bulanan`. State draft dieja `draft` (Inggris). `tanggal_mulai`, `tanggal_selesai`, `line_ids` terkonfirmasi sesuai asumsi. Periode juga punya `name` (computed, store) untuk pesan error.
- `hociro.upah.line` didefinisikan di file yang sama dengan `hociro.periode.upah` (`hociro_periode_upah.py`, class mulai baris 140) — tidak ada `hociro_upah_line.py` terpisah.
- `_prepare_line_vals()` mengambil `saldo_awal` hanya dari periode berstatus `ditutup` — celah ini jadi dasar predecessor lock baru (lihat di bawah).
- **Tidak ada `@api.constrains`/`models.Constraint` apa pun** pada `hociro.periode.upah` yang mencegah periode dibuat tidak berurutan atau tanggal tumpang tindih — mengonfirmasi predecessor lock bukan kekhawatiran teoretis.
- **`hari_lembur_staf` tidak pernah dirender di view mana pun**, walau help text-nya bilang "input manual" — field ini tidak bisa diisi siapa pun lewat UI. **Konsekuensi: seluruh perhitungan upah staf yang pernah dijalankan (termasuk semua pengujian di `test_bersih_5`, §-2 di atas) menghitung lembur staf = nol.** Belum ada dampak production karena periode bulanan belum pernah dipakai di luar `test_bersih_5`.
- **`bonus` disembunyikan untuk periode mingguan** (`column_invisible="parent.tipe != 'bulanan'"`) — tukang tidak bisa diberi bonus lewat UI sekarang, padahal user mengonfirmasi bonus untuk tukang akan terjadi.

**Empat keputusan dikunci setelah verifikasi ini:**
1. **Jenis koreksi masuk** — model baru `hociro.upah.penyesuaian` (issue #4) punya tiga `jenis`: `bonus`, `lembur_staf`, `koreksi`. `koreksi` adalah satu-satunya yang menerima nilai negatif, dipakai untuk mengalirkan perbaikan periode lampau **maju** ke periode berjalan (periode `ditutup` tetap tidak boleh dihitung ulang, sesuai issue #2).
2. **Urutan implementasi: issue #4 sebelum issue #3.** Alasan: selama gap input lembur staf terbuka, periode bulanan tidak bisa masuk UAT sama sekali — itu memblokir jalur kerja lebih besar daripada compute tarif yang belum pindah ke lookup bertanggal. Urutan penuh sekarang: issue #1 + #2 (guard, kecil, tidak sentuh data) → **issue #4** (butuh diuji duluan mekanisme `line_id` recompute di `test_bersih_5`) → issue #3.
3. **Aturan parkir `x_batas_jam_disiplin` tetap berlaku, ditegaskan ulang** — jangan isi field itu dengan jawaban cutoff Mr. Ricoh sampai issue #3 selesai. Berlaku juga selama pengerjaan issue #4 (yang dikerjakan duluan), karena `_compute_dapat_disiplin` belum berubah sampai #3 selesai.
4. **State mapping `ditutup` → `dikonfirmasi` (poin 4 di desain issue #2 lama) DICABUT.** Verifikasi menunjukkan state machine yang diusulkan sudah ada dengan nama berbeda — `ditutup` sudah berfungsi persis seperti `dikonfirmasi` yang diusulkan, transisinya sudah dijaga `action_tutup_periode()`/`action_buka_kembali()`. Rename dibatalkan sepenuhnya: nol manfaat, menambah migrasi data dan mengubah label yang sudah dilihat user. State `dibayar` tetap menyusul bersama `hociro.pembayaran`, ditambahkan di atas `ditutup` yang sudah ada, bukan menggantikannya.

**Temuan tambahan yang mengubah scope issue #2 — predecessor lock:** `_prepare_line_vals()` mengambil `saldo_awal` dari periode `ditutup` terakhir sebelum `tanggal_mulai`, dan filter `ditutup` itu berarti periode yang masih `draft`/`dihitung` **dilompati begitu saja**, bukan diblokir. Skenario: Juni ditutup → Juli dibuat tapi masih draft → Agustus dihitung, melompati Juli, mengambil saldo dari Juni → Agustus salah, tidak ada mekanisme yang tahu. Ini arah kebalikan dari successor lock (issue #2 asli memproteksi pendahulu dari perubahan; ini menangkap penerus yang dihitung terlalu dini). Guard baru ditambahkan ke issue #2 via komentar: `action_hitung_upah()` menolak kalau ada pendahulu (tipe sama, `tanggal_selesai` lebih awal) yang belum `ditutup`.

**Revisi lain ke issue #1 (via komentar):** daftar field yang dijaga guard menyusut dari tiga jadi dua — `hari_lembur_staf` dikeluarkan (tidak pernah bisa diisi, jadi tidak ada yang perlu dijaga; ditangani di issue #4), `bonus` juga keluar (akan pindah ke `hociro.upah.penyesuaian`), tapi **`saldo_awal` masuk** (terkonfirmasi editable, satu-satunya jalan input saldo pembuka era Excel, dan hilang di regenerate pertama tanpa guard). Daftar final: `total_dibayar` dan `saldo_awal`. Aturan guard juga berubah dari "≠ 0" jadi "berbeda dari hasil `_prepare_line_vals()`" — supaya `saldo_awal` normal periode kedua dst tidak salah terblokir.

**Tiga tindakan GitHub:**
- [Issue #4](https://github.com/novis97/hociro-erp/issues/4) — dibuat baru. Model `hociro.upah.penyesuaian` (field: `periode_id`, `employee_id`, `jenis`, `nilai`, `keterangan` wajib, `line_id` computed store). `bonus`/`hari_lembur_staf` dihapus dari `hociro.upah.line`. Titik paling rapuh: `line_id` harus di-recompute eksplisit setelah `action_hitung_upah()` bikin ulang line, karena dependency-nya (`periode_id`/`employee_id`) tidak berubah saat line diganti — harus diuji duluan di `test_bersih_5` sebelum menulis sisa implementasi.
- Komentar revisi di [issue #1](https://github.com/novis97/hociro-erp/issues/1) — daftar field guard & aturan guard direvisi (lihat di atas). Tidak ditutup, label tidak diubah.
- Komentar revisi di [issue #2](https://github.com/novis97/hociro-erp/issues/2) — state mapping dicabut, nama field dikoreksi, predecessor lock ditambahkan (lihat di atas). Tidak ditutup, label tidak diubah.
- Issue #3 **tidak disentuh** di sesi ini.

**Status: implementasi keempat issue di atas masih belum dimulai.** Verifikasi field yang jadi salah satu prasyarat penundaan sebelumnya sudah selesai (poin ini tuntas). Yang masih menunggu:
1. ~~Verifikasi lapangan production: apakah periode Mingguan 2026-W24 punya `bonus`/`total_dibayar` terisi (dibutuhkan migrasi issue #4 kalau ya) — belum dicek.~~ — **RESOLVED 2026-09-11**: nol data manual di W24, bagian "Migrasi" dihapus dari scope issue #4. Lihat §-5.
2. ~~Uji mekanisme `line_id` recompute (issue #4) di `test_bersih_5` — belum dijalankan, disyaratkan selesai sebelum menulis sisa implementasi issue #4.~~ — **RESOLVED 2026-09-11**: mekanisme LOLOS uji, dengan temuan penting bahwa Odoo ternyata sudah memicu recompute otomatis sendiri (recompute eksplisit dipertahankan sebagai jaring pengaman, bukan lagi "wajib"). Lihat §-5.

---

## -3. Update 2026-09-11 — Cek divergensi, pindahkan 2 commit VPS, buat 3 issue

**Konteks:** sesi ini (Claude Code Desktop, dev lokal) menjalankan tugas administratif murni — tidak ada perubahan kode. Tujuan: memindahkan commit yang tertahan di VPS (§-2 di atas) dan membuat issue GitHub untuk dua bug yang belum punya issue, plus komentar keputusan di issue #1. Desain perbaikan ketiganya sudah disepakati di sesi lain sebelum sesi ini jalan.

**Cek divergensi (dilakukan sebelum tindakan apa pun, sesuai instruksi):** `git fetch origin` tidak menemukan perubahan baru; HEAD lokal sudah identik dengan `origin/main` (`40d1eda`), working tree bersih, tidak ada yang perlu di-rebase. Commit `3e33305` ("read upah", author `novis97 <novis97@gmail.com>`, 2026-09-03) yang sempat dicurigai — yang terjelaskan cuma **posisinya di riwayat**: sudah lama jadi ancestor sah dari `origin/main`, bukan commit baru yang divergen sekarang. **Asal-usulnya (siapa yang sebenarnya membuatnya) belum terkonfirmasi** — email author (`novis97@gmail.com`) berbeda dari akun yang biasa dipakai untuk commit di repo ini. Lihat juga catatan asli soal commit ini di §akhir file (entri 2026-09-03, poin 4).

**Dua commit dari VPS berhasil diterapkan** via `git am` dari patch (`git format-patch`) tanpa konflik, lalu di-push ke `origin/main`:
- `437e928` — dokumentasi bug saldo_awal stale (`docs/bugs/saldo-awal-stale-snapshot-lintas-periode.md`), sebelumnya `90ebb34` di VPS sebelum hash berubah karena format-patch/am.
- `499003a` — update entri `-2.` di file ini (isinya sudah ada di atas).

**Tiga issue GitHub dibuat/diperbarui** (label `prioritas-tinggi` dan `hociro_upah` dibuat baru di repo, sebelumnya belum ada):
- [Issue #2](https://github.com/novis97/hociro-erp/issues/2) — `saldo_awal` stale snapshot lintas periode. Desain: successor lock (`_get_penerus()` + guard di `action_hitung_upah()`/`action_buka_kembali()`), state `ditutup`→`dikonfirmasi`, line saldo-only untuk karyawan archived.
- [Issue #3](https://github.com/novis97/hociro-erp/issues/3) — tarif & batas jam disiplin dibaca dari master data terkini alih-alih snapshot historis. Desain: model baru `hociro.parameter.karyawan` (nilai berlaku per tanggal, lookup `berlaku_mulai <= T`), `@api.depends` pada `_compute_dapat_disiplin` **sengaja** dilepas dari `x_batas_jam_disiplin`.
- Komentar di [issue #1](https://github.com/novis97/hociro-erp/issues/1) — keputusan: guard murah dulu (blokir `action_hitung_upah()` kalau ada `bonus`/`hari_lembur_staf`/`total_dibayar` terisi), pisah model (`hociro.upah.penyesuaian`) ditunda sampai setelah UAT Periode Bulanan dengan Mr. Ricoh. Issue #1 **tidak ditutup**, label tidak diubah (sesuai batasan tugas).

**Aturan parkir yang masih berlaku — penting untuk sesi berikutnya:** jangan isi `x_batas_jam_disiplin` di `hr.employee` dengan jawaban cutoff dari Mr. Ricoh sampai model `hociro.parameter.karyawan` (issue #3) selesai dibangun. Mengisinya akan memicu `_compute_dapat_disiplin` (`store=True`, `@api.depends` masih menyertakan field itu untuk saat ini) me-recompute `dapat_disiplin` di seluruh riwayat absensi staf tersebut secara otomatis dalam satu `write()`, tanpa jejak dan tanpa cara membatalkannya.

**Status: implementasi ketiga issue di atas belum dimulai.** Menunggu tiga hal sebelum mulai coding:
1. Hasil verifikasi kode dari Agent 3 (nama field `tipe_periode`/`jenis`, `tanggal_mulai`, `tanggal_selesai`, `line_ids` di `hociro.periode.upah` yang dipakai di issue #2 masih asumsi dari dokumentasi, belum dicek langsung ke `models/hociro_periode_upah.py`).
2. Keputusan user soal aturan parkir di atas (kapan/apakah cutoff Mr. Ricoh boleh langsung masuk vs menunggu issue #3).
3. Konfirmasi final nama field yang dipakai di ketiga issue setelah poin 1 selesai.

---

## -2. Update 2026-09-10 — Pengujian periode Bulanan staf di `test_bersih_5`, dua bug ditemukan

**Konteks:** sesi ini berjalan di VPS (bukan mesin dev lokal), dengan akses ke Docker (`hociro-erp-db-1`/`hociro-erp-odoo-1`) dan lima database `test_bersih*` yang sudah ada sebelumnya. Sebelum membuat dummy data, kelima database dicek: modul `hociro_upah` `installed` di semua lima, tapi hanya **`test_bersih_5`** yang skemanya lengkap (punya keempat tabel `hociro_absensi_staf`, `hociro_absensi_tukang`, `hociro_periode_upah`, `hociro_upah_line` sesuai kode addon saat ini) **dan** masih kosong datanya. `test_bersih`, `_2`, `_3` cuma punya `hociro_absensi_tukang` (skema lama/stale), `_4` cuma tambah `hociro_absensi_staf`. Jadi `test_bersih_5` dipakai untuk seluruh pengujian di bawah.

**Dummy data yang diseed** (lewat Odoo shell/ORM, bukan raw SQL, supaya field compute beneran jalan): 3 `hr.employee` (`x_tipe_pekerja='staf'`) — Staf A & C pakai default `x_batas_jam_disiplin` (8.5), Staf B di-override jadi 8.0 — plus absensi Juli 2026 (Senin-Sabtu) dan Agustus 2026 dengan pola `jam_masuk` bervariasi supaya kombinasi cutoff disiplin per-karyawan teruji. Periode `Bulanan 2026-07` dihitung via `action_hitung_upah()` (bukan insert manual ke `hociro.upah.line`), hasilnya diverifikasi manual terhadap formula `upah_kotor` di kode dan terverifikasi ulang langsung lewat query Postgres (independen dari cache ORM) — semua cocok, termasuk override cutoff disiplin per-karyawan (Staf B tidak dapat disiplin di hari-hari yang lolos cutoff default 8.5 tapi tidak lolos cutoff pribadinya 8.0).

**Carry-over saldo antar periode diuji dan LOLOS**: periode Juli ditutup (`action_tutup_periode()`), periode Agustus dibuat & dihitung, `saldo_awal` Agustus persis sama dengan `saldo_akhir` Juli untuk ketiga staf. Constraint read-only periode `ditutup` juga terverifikasi (`write()`/`unlink()` pada periode/line yang `ditutup` menghasilkan `UserError`, seperti didesain).

**DUA BUG ditemukan** saat menguji skenario regenerate & buka-kembali periode (skenario yang sebelumnya belum pernah diuji end-to-end):

1. **[`docs/bugs/regenerate-upah-menghapus-data-manual.md`](./bugs/regenerate-upah-menghapus-data-manual.md)** — `action_hitung_upah()` melakukan `unlink()` + `create()` ulang pada seluruh `hociro.upah.line` setiap dipanggil ulang (mis. setelah koreksi absensi), sehingga field yang cuma bisa diisi manual — `bonus`, `hari_lembur_staf`, `total_dibayar` — hilang tanpa peringatan, dan `saldo_akhir` jadi salah sebesar nilai `total_dibayar` yang hilang. ID line juga berubah tiap regenerate. Sudah ada TODO existing di kode (baris 190-197) yang mengantisipasi `total_dibayar` jadi computed field setelah modul `hociro.pembayaran` dibangun — tapi TODO itu tidak mencakup `bonus`/`hari_lembur_staf`. **Dilaporkan ke GitHub sebagai issue #1** (per informasi dari user; belum diverifikasi langsung oleh sesi ini karena tidak ada akses `gh`/token GitHub di VPS).
2. **[`docs/bugs/saldo-awal-stale-snapshot-lintas-periode.md`](./bugs/saldo-awal-stale-snapshot-lintas-periode.md)** — `saldo_awal` di `hociro.upah.line` adalah snapshot statis (bukan computed), diambil sekali dari `saldo_akhir` periode sebelumnya saat `_prepare_line_vals()` jalan. Kalau periode sumber yang sudah `ditutup` dibuka kembali (`action_buka_kembali()`) dan dihitung ulang dengan hasil `saldo_akhir` berbeda, periode berikutnya yang sudah dibuat tidak ikut ter-update — jadi stale, tidak sinkron, berpotensi cascading ke periode-periode setelahnya (belum teruji langsung untuk rantai >2 periode). Tidak ada `UserError`/warning apa pun. Root cause beda dari bug #1 (snapshot statis vs unlink+create), tapi sama-sama dipicu alur "buka kembali periode ditutup lalu hitung ulang". **Belum ada issue GitHub untuk bug ini.**

Kedua bug murni didokumentasikan — **belum ada patch kode**, tiga opsi perbaikan untuk bug kedua (computed field, blokir buka-kembali kalau ada periode dependen, cascade recompute otomatis) dicatat sebagai opsi diskusi, belum diputuskan mana yang dipakai. Rencana perbaikan gabungan untuk kedua bug juga **belum diputuskan** (mitigasi cepat vs perbaikan permanen).

**Status commit & git — penting untuk sesi berikutnya:**
- Origin/main sempat diverge dari HEAD lokal VPS ini: ada commit `adfd707` (update session-log tentang test produksi periode Mingguan 2026-W24, dua tukang tanpa tarif) dan `40d1eda` (dokumentasi bug #1, isinya **identik** dengan draft yang dibuat sesi ini) yang masuk ke `origin/main` lewat sesi lain, bukan lewat push dari VPS ini (SSH deploy key di VPS ini **read-only by design** — jangan diubah tanpa diskusi eksplisit dengan user).
- Karena `40d1eda` isinya identik dengan commit lokal untuk bug #1, sesi ini **rebase** riwayat lokal ke atas `origin/main` (bukan merge) supaya tidak ada file terduplikasi/bentrok — commit lokal lama untuk bug #1 (yang tadinya bernama `b1c4c48`) sudah tidak ada lagi di riwayat, digantikan `40d1eda` yang sudah di origin.
- Setelah rebase, satu commit masih tertahan lokal di VPS ini: **`90ebb34`** (dokumentasi bug #2, `saldo-awal-stale-snapshot-lintas-periode.md` — sebelum rebase sempat bernama `7d7f60f`, hash berubah karena rebase). Belum ke-push, sama-sama karena SSH key read-only.
- Update entri session-log ini sendiri (`-2.` di atas) ada di commit setelah `90ebb34` — cek riwayat git kalau butuh urutan pastinya, jangan patokan ke hash lama di percakapan sebelumnya karena sudah berubah akibat rebase.

**Catatan arsitektur — perlu didokumentasikan resmi:** selain 3-agent yang sudah ditetapkan sebelumnya, ternyata ada sesi keempat — **Claude/Cowork project "erp-hociro" di claude.ai** — yang punya akses commit+push+buat issue **langsung ke GitHub** (bukan lewat VPS ini). Sesi ini juga menemukan commit `adfd707` di origin yang dibuat langsung oleh user (`novis97`, bukan atas nama Claude) tentang test produksi Mingguan W24 — menandakan mungkin ada lebih dari satu jalur yang menyentuh `origin/main` di luar yang sudah dipetakan. Akses persis sesi Cowork ini (apakah juga bisa akses VPS/database staging, atau murni repo GitHub) **belum diverifikasi** dari sesi VPS ini. Perlu dipetakan resmi perannya (scope akses, kapan dipakai) sebelum dipakai lagi, supaya tidak ada kejutan divergensi git seperti yang terjadi di sesi ini.

---

## -1. Update 2026-09-10 — `hociro.periode.upah` selesai, terverifikasi di production

**Modul `hociro.periode.upah` (perhitungan periode upah mingguan/bulanan) sudah selesai dan lolos test end-to-end di production**, untuk periode Mingguan **2026-W24**.

**Temuan saat test:** dua tukang — **Wak Andi** dan **Anak Bang Dedek** — tidak punya tarif upah di master data (`hr.employee`). Ini **bukan bug di modul**: data sumber untuk kedua tukang ini memang belum lengkap. Sudah dicatat sebagai pertanyaan terbuka ke **Mr. Ricoh** (perlu tarif upah harian/lembur untuk keduanya sebelum periode upah yang melibatkan mereka bisa dihitung penuh).

---

## 0. Update 2026-09-04 — Checklist §5 poin instalasi LOLOS

**Install `hociro_upah` ke database bersih (`test_bersih`) berhasil, tanpa error.** Ini menutup item yang paling banyak ditandai "belum" di log 2026-09-03 (lihat §1, §2, §4 poin 3 di bawah — semua merujuk balik ke sini).

Dua temuan v19 muncul dan sudah diperbaiki + didokumentasikan di `docs/v19-conventions.md`:

1. **`ParseError` di search view** — `<group expand="0" string="Kelompokkan">` di `views/hociro_absensi_tukang_views.xml` tidak valid lagi di v19 (atribut `expand`/`string` pada `<group>` search view dihapus lewat commit resmi Odoo `a814ad6b`). Diperbaiki jadi `<group>` polos. Lihat `v19-conventions.md` §1.7.
2. **Warning (bukan error) `_sql_constraints` deprecated** — muncul saat install sukses: `Model attribute _sql_constraints is no longer supported, please define models.Constraint on the model`. Diperbaiki di `models/hociro_absensi_tukang.py`: `_sql_constraints = [...]` diganti `_tanggal_employee_uniq = models.Constraint(...)`. Lihat `v19-conventions.md` §1.9.

Kedua pola ini juga sudah ditambahkan sebagai grep check baru di checklist §5 `v19-conventions.md` supaya modul berikutnya tidak mengulang.

**Yang masih belum jadi bukti**: instalasi ini di database *test_bersih*, bukan berarti seluruh alur deployment VPS (§2 dan §3 di bawah) sudah selesai — `.env`, `odoo.conf`, `docker-compose.yml` sungguhan, swap, Nginx/SSL, dsb. semuanya **masih berstatus belum dikerjakan** seperti tercatat di §2/§3 di bawah.

**Konteks penting:** seluruh sesi ini dikerjakan di mesin dev lokal (Windows), **bukan** di VPS. Tidak ada koneksi ke VPS produksi/staging yang dibuat di sesi ini. Semua yang disebut "belum dilakukan" di bawah ini murni karena belum dikerjakan — bukan karena dicoba dan gagal.

---

## 1. Yang Sudah Selesai

### Model Odoo
- Modul baru `hociro_upah` dibuat dari nol, berisi model `hociro.absensi.tukang` sesuai `docs/specs/hociro_upah.md` §3.4:
  - `addons/hociro_upah/models/hociro_absensi_tukang.py` — field lengkap (`tanggal`, `employee_id`, `proyek_id`, `sesi_pagi`, `sesi_siang`, `lembur`, `hari_kerja` compute+store, `pengawas_id`, `state`, `catatan`), constraint unik `(tanggal, employee_id)`, method `action_dikuatkan`/`action_draft`, override `unlink()` (tolak hapus record `dikuatkan`), override `write()` (tolak ubah field kunci — `tanggal`/`employee_id`/`proyek_id`/`sesi_pagi`/`sesi_siang`/`lembur` — saat `state = dikuatkan`, kecuali perubahan `state` itu sendiri).
  - `addons/hociro_upah/models/hr_employee.py` — **hanya** field `x_tipe_pekerja` (staf/tukang). Ini bagian minimal dari spec §3.3, ditambahkan karena domain `employee_id` di §3.4 butuh field ini ada. Field upah lain di §3.3 (`x_upah_harian`, `x_tarif_lembur`, dst) **belum dibangun**.
  - `addons/hociro_upah/security/ir.model.access.csv` — satu baris akses penuh (CRUD) untuk `base.group_user`. Belum ada pemisahan hak akses.
  - `addons/hociro_upah/views/hociro_absensi_tukang_views.xml` — list/form/search + action + menu (`Upah & Absensi > Absensi > Tukang`).
  - `addons/hociro_upah/__manifest__.py` — depends `hr`, `analytic` saja; `license: LGPL-3`; `version: 19.0.1.0.0`.
- Checklist §5 `docs/v19-conventions.md` sudah dijalankan terhadap kode di atas:
  - ✅ Tidak ada `attrs=` / `states=`
  - ✅ Tidak ada `<tree>` (semua `<list>`)
  - ✅ Tidak ada `def name_get`
  - ✅ Tidak ada `t-esc=`
  - ✅ **Poin instalasi ke database bersih SUDAH lolos (2026-09-04)** — lihat §0 di atas untuk detail dan dua temuan v19 yang muncul saat itu.

### Struktur folder (konsolidasi)
- Sebelumnya: `docs/`, `specs/`, dan `hociro_upah/` tersebar antara folder induk `erp-hociro/` dan repo git `hociro-erp/`.
- Sekarang, semua sudah di dalam repo git `hociro-erp/`:
  - `docs/v19-conventions.md`
  - `docs/setup-odoo-docker-agent3.md`
  - `docs/specs/hociro_upah.md`
  - `addons/hociro_upah/` (modul, lihat di atas)
- Folder `addons/` dan `deploy/` yang kosong di folder induk `erp-hociro/` (di luar repo git) sudah dihapus.
- Folder `docs/` dan `specs/` di folder induk `erp-hociro/` **masih ada tapi kosong** (sengaja tidak dihapus — belum ada instruksi eksplisit untuk itu).
- `docs/setup-odoo-docker-agent3.md` sudah diupdate: semua referensi `custom-addons/` diganti jadi `repo/` (direktori clone) dan `repo/addons/` (bind-mount ke `/mnt/extra-addons`), supaya cocok dengan struktur repo aktual (`addons/hociro_upah/`, bukan modul langsung di root repo).

### Commit yang sudah di-push ke `origin/main`
```
efb6d48 Update setup-odoo-docker-agent3.md: custom-addons/ -> repo/addons/ sesuai struktur aktual
19de1f8 Tambah model hociro.absensi.tukang, reorganisasi struktur addons/docs
3e33305 read upah                              <- lihat peringatan §4, bukan buatan sesi ini
876e0d1 Initial commit
```

---

## 2. Yang BELUM Dilakukan — dan Kenapa Berhenti di Situ

Semua poin ini adalah langkah **deployment ke VPS** dari `docs/setup-odoo-docker-agent3.md`. Sesi ini berhenti di sini karena scope kerja sejauh ini murni penulisan kode modul + dokumentasi di repo, belum masuk ke tahap operasional VPS — dan mesin dev ini memang tidak punya akses ke VPS produksi.

- **`.env` belum dibuat/diisi** (§2 dokumen) — perlu `POSTGRES_PASSWORD` dan `ODOO_ADMIN_PASSWD` diisi manual dengan password acak yang kuat. File ini **sengaja tidak pernah dibuat lewat otomasi** karena berisi secret — harus diisi manual oleh yang pegang akses VPS, jangan digenerate/dicommit oleh agent.
- **`config/odoo.conf` dan `docker-compose.yml`/`docker-compose.staging.yml` belum dibuat sebagai file sungguhan** di VPS maupun di repo ini — isinya baru ada sebagai contoh kode di dalam `docs/setup-odoo-docker-agent3.md` §3–§5. Belum ada langkah "copy dari dokumen ke file nyata di `/opt/hociro-erp/`" yang dijalankan.
- **Swap 2GB belum diverifikasi** (§0.1) — perintah `sudo fallocate ...` s/d `sudo sysctl -p` belum pernah dijalankan/dicek di sesi ini.
- **`docker compose up -d` belum dijalankan** — container `db` dan `odoo` belum pernah dinyalakan.
- **Database belum dibuat**, jadi `list_db = False` juga belum bisa diverifikasi aktif.
- **Nginx + SSL (§6), cron disk/memory/backup (§7–8) belum disentuh.**
- ~~Checklist §5 `v19-conventions.md` (`odoo -d test_bersih -i hociro_upah --stop-after-init`) belum bisa dijalankan~~ — **SUDAH lolos 2026-09-04, lihat §0.**

---

## 3. Command Berikutnya, Urut

Semua di bawah ini dijalankan **di VPS**, bukan di mesin dev. Mengikuti urutan `docs/setup-odoo-docker-agent3.md`.

```bash
# 1. Prasyarat VPS (§0) — kalau Docker belum terpasang
sudo apt update && sudo apt upgrade -y
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
# logout/login supaya group docker aktif
docker --version && docker compose version

# 2. Swap 2GB — WAJIB, cek dulu apakah sudah ada sebelum membuat baru (§0.1)
free -h   # cek dulu, kalau swap sudah 2.0G aktif, skip langkah di bawah
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
echo 'vm.swappiness=10' | sudo tee -a /etc/sysctl.conf
sudo sysctl -p
free -h   # verifikasi swap 2.0G aktif

# 3. Struktur direktori + clone repo (§1, sudah disesuaikan ke repo/addons/)
sudo mkdir -p /opt/hociro-erp/{config,repo,backups}
sudo chown -R $USER:$USER /opt/hociro-erp
cd /opt/hociro-erp
git clone https://github.com/novis97/hociro-erp.git repo
# verifikasi: ls repo/addons/hociro_upah harus menunjukkan isi modul

# 4. Buat .env (§2) — ISI MANUAL, jangan commit ke git
cat > /opt/hociro-erp/.env <<'EOF'
POSTGRES_DB=postgres
POSTGRES_USER=odoo19
POSTGRES_PASSWORD=GANTI_DENGAN_PASSWORD_KUAT_ACAK
ODOO_ADMIN_PASSWD=GANTI_DENGAN_PASSWORD_KUAT_LAIN
ODOO_VERSION=19.0
EOF
# lalu edit manual, ganti dua placeholder di atas dengan password sungguhan

# 5. Buat config/odoo.conf (§5 dokumen)
cat > /opt/hociro-erp/config/odoo.conf <<'EOF'
[options]
admin_passwd = ${ODOO_ADMIN_PASSWD}
addons_path = /usr/lib/python3/dist-packages/odoo/addons,/mnt/extra-addons
list_db = False
proxy_mode = True
workers = 0
max_cron_threads = 1
EOF

# 6. Buat docker-compose.yml (§3 dokumen) — salin isi lengkap dari
#    docs/setup-odoo-docker-agent3.md §3 ke /opt/hociro-erp/docker-compose.yml
#    (perhatikan bind mount sudah harus ./repo/addons:/mnt/extra-addons)

# 7. Nyalakan production
cd /opt/hociro-erp
docker compose up -d
docker compose ps
docker compose logs -f odoo   # pastikan tidak ada error saat startup

# 8. Buat database via browser
#    https://<domain-atau-ip>:8069/web/database/manager
#    - demo data DIMATIKAN
#    - password kuat
#    - setelah database dibuat, restart Odoo (list_db=False harus sudah aktif)

# 9. BARU SETELAH itu, tes install modul di database bersih terpisah
#    (checklist v19-conventions.md §5 poin 5)
docker compose exec -T odoo \
    odoo -d test_bersih -i hociro_upah --stop-after-init
# cek log: harus tidak ada traceback, terutama di sekitar field
# proyek_id / plan_id (lihat peringatan §4 di bawah)

# 10. Baru lanjut ke Nginx+SSL (§6), monitoring (§7), backup (§8) sesuai dokumen
```

---

## 4. Peringatan yang Masih Menggantung

1. **Swap 2GB belum pernah diverifikasi berjalan di VPS mana pun dari sesi ini.** Jangan asumsikan sudah aktif — jalankan `free -h` dulu sebelum `docker compose up -d`, karena tanpa swap di RAM 3GB, instalasi modul atau lonjakan beban bisa memicu OOM (lihat `docs/setup-odoo-docker-agent3.md` §0.1).
2. **Asumsi belum terverifikasi ke source Odoo 19 asli:** field `plan_id` pada `account.analytic.account` (dipakai di domain `proyek_id` — `addons/hociro_upah/models/hociro_absensi_tukang.py` baris ~29-31, komentar sudah ada di kode). Kalau nama field sebenarnya berbeda di Odoo 19, modul akan gagal load view. **Wajib** dicek ke `$ODOO_SRC/addons/analytic/models/analytic_account.py` di VPS sebelum atau saat langkah install (§3 poin 9 di atas).
3. ~~Checklist §5 poin 5 (`v19-conventions.md`) belum pernah lolos~~ — **RESOLVED 2026-09-04**: instalasi ke `test_bersih` berhasil tanpa error. Lihat §0 untuk dua temuan v19 (ParseError search view, warning `_sql_constraints`) yang muncul dan sudah diperbaiki dalam prosesnya.
4. **Commit `3e33305 "read upah"` di riwayat git tidak dibuat lewat perintah eksplisit dalam sesi kerja ini** — muncul begitu saja di antara "Initial commit" dan commit pertama yang saya buat, berisi isi awal modul `hociro_upah/` (sebelum dipindah ke `addons/`). Sudah dilaporkan ke user saat ditemukan, tidak ada investigasi lebih lanjut dan tidak ada tindakan diambil terhadapnya. Kalau ini bukan hasil kerja yang diketahui/diinginkan, cek riwayat commit dan proses lain (hook, sesi lain) yang mungkin punya akses tulis ke repo ini.
5. **`ir.model.access.csv` masih sangat longgar** — semua user internal (`base.group_user`) punya akses penuh CRUD ke `hociro.absensi.tukang`, termasuk `unlink` (walau dibatasi lewat kode untuk record `dikuatkan`, bukan lewat access right). Belum ada pemisahan peran pengawas vs staf lain.
6. **`.env`, `config/odoo.conf`, `docker-compose.yml` belum ada sebagai file nyata di mana pun** — baru contoh isi di dokumentasi. Jangan lupa buat filenya dulu sebelum `docker compose up`.
7. **Open items dari `docs/specs/hociro_upah.md` §6 belum diputuskan** (pemetaan Tempat lama ke proyek, trade name per proyek, dimensi proyek untuk absensi staf, daftar kantong lengkap) — di luar scope sesi ini, tapi menghalangi migrasi data (§5 spec) kalau belum ada keputusan.

---

*Ditulis di akhir sesi kerja 2026-09-03. Entri di atas menambah riwayat sampai 2026-09-11; lihat masing-masing entri untuk status commit/push saat entri itu ditulis.*
