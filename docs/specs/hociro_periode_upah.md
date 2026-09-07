# Spesifikasi Model — `hociro.periode.upah` & `hociro.upah.line`

**Versi:** draft 1  
**Modul:** `hociro_upah` (tambahan model, bukan modul baru)  
**Target:** Odoo 19.0 Community  
**Prasyarat baca:** `docs/v19-conventions.md`, `docs/specs/hociro_upah.md` §3.7

---

## 1. Konteks

Sheet REKAP di Excel lama menjawab pertanyaan: "bulan ini tukang A kerja berapa hari, dapat berapa, udah dibayar berapa, sisa berapa." Sheet TOTAL di file studio menjawab hal yang sama untuk staf bulanan.

Modul ini memindahkan kedua rekap itu ke Odoo — dengan perbedaan utama: data absensi sudah ada di database, jadi hari kerja/disiplin/lembur **dihitung otomatis** dari `hociro.absensi.tukang` dan `hociro.absensi.staf`, bukan diinput ulang manual.

### 1.1 Temuan dari Data Lama

**Tukang (dari sheet REKAP):**
- Alfin: 94.5 hari × 130.000 = 12.285.000, kasbon 12.335.000, sisa 0 (ada 50.000 uang lembur terpisah)
- Heri: 100.5 hari × 200.000 = 20.100.000, kasbon 20.300.000, sisa −200.000 (overpaid)
- Hendra: 90 hari × 200.000 + 1 lembur = 18.100.000, kasbon 19.600.000, sisa −1.500.000 (overpaid)

**Staf (dari sheet TOTAL/SLIP — Juli, Nada sebagai contoh):**
- Pokok 1.000.000 + Harian (27 × 75.000 = 2.025.000) + Disiplin (19 × 15.000 = 285.000) + Transpor (27 × 10.000 = 270.000) = 3.580.000

**Firmansyah:** flat 2.000.000, tidak ada komponen variabel — posisi Logistic, bukan arsitek.

---

## 2. Model `hociro.periode.upah`

Header periode. Satu record = satu siklus pembayaran (mingguan atau bulanan).

| Field | Tipe | Catatan |
|---|---|---|
| `name` | Char, compute | Auto-generate: "Mingguan 2026-W27" atau "Bulanan 2026-07" |
| `tipe` | Selection `mingguan` / `bulanan` | Mingguan untuk tukang, bulanan untuk staf |
| `tanggal_mulai` | Date, required | |
| `tanggal_selesai` | Date, required | |
| `state` | Selection `draft` / `dihitung` / `ditutup` | |
| `line_ids` | One2many `hociro.upah.line` | |
| `total_upah_kotor` | Monetary, compute | Σ `line_ids.upah_kotor` |
| `total_dibayar` | Monetary, compute | Σ `line_ids.total_dibayar` |
| `total_saldo` | Monetary, compute | Σ `line_ids.saldo_akhir` |
| `currency_id` | bawaan dari company, tidak perlu didefinisikan ulang |

**Alur state:**
1. `draft` — periode baru, belum ada line
2. `dihitung` — tombol "Hitung Upah" sudah ditekan, line ter-generate dari data absensi
3. `ditutup` — periode final, tidak bisa diedit lagi

**Tombol aksi:**
- "Hitung Upah" (draft → dihitung): generate/refresh `line_ids` dari data absensi
- "Tutup Periode" (dihitung → ditutup): kunci, tidak bisa diubah
- "Buka Kembali" (ditutup → dihitung): hanya admin, untuk koreksi

---

## 3. Model `hociro.upah.line`

Satu record = satu pekerja di satu periode.

### 3.1 Field Bersama (tukang & staf)

| Field | Tipe | Catatan |
|---|---|---|
| `periode_id` | Many2one `hociro.periode.upah`, required, ondelete cascade | |
| `employee_id` | Many2one `hr.employee`, required | |
| `tipe_pekerja` | Selection, related `employee_id.x_tipe_pekerja` | Untuk conditional display di view |
| `upah_kotor` | Monetary, compute, store | Rumus beda per tipe — lihat §3.2 dan §3.3 |
| `total_dibayar` | Monetary | **Input manual untuk sekarang** — nanti otomatis dari `hociro.pembayaran` |
| `saldo_awal` | Monetary | Diambil dari `saldo_akhir` periode sebelumnya, atau 0 kalau ini periode pertama |
| `saldo_akhir` | Monetary, compute, store | `saldo_awal + upah_kotor − total_dibayar` |
| `catatan` | Char | |

### 3.2 Field Khusus Tukang

| Field | Tipe | Sumber |
|---|---|---|
| `hari_kerja` | Float, compute, store | Σ `hociro.absensi.tukang.hari_kerja` yang `state=dikuatkan` dalam rentang periode |
| `hari_lembur` | Float, compute, store | Σ `hociro.absensi.tukang.lembur` |
| `tarif_harian` | Monetary | Disalin dari `employee_id.x_upah_harian` saat dihitung — snapshot, bukan referensi live |
| `tarif_lembur` | Monetary | Disalin dari `employee_id.x_tarif_lembur` |

**Rumus `upah_kotor` tukang:**
```
hari_kerja × tarif_harian + hari_lembur × tarif_lembur
```

### 3.3 Field Khusus Staf

| Field | Tipe | Sumber |
|---|---|---|
| `hari_hadir` | Integer, compute, store | Jumlah absensi `status=hadir` dalam rentang |
| `hari_disiplin` | Integer, compute, store | Jumlah absensi `dapat_disiplin=True` |
| `hari_lembur_staf` | Float | Input manual — lembur staf tidak tercatat otomatis dari absensi sekarang |
| `tarif_pokok` | Monetary | Snapshot dari `x_gaji_pokok` |
| `tarif_harian` | Monetary | Snapshot dari `x_tarif_harian` |
| `tarif_disiplin` | Monetary | Snapshot dari `x_tarif_disiplin` |
| `tarif_transpor` | Monetary | Snapshot dari `x_tarif_transpor` |
| `tarif_lembur` | Monetary | Snapshot dari `x_tarif_lembur` |
| `bonus` | Monetary | Input manual — ada di slip Rahmad tapi tidak rutin |

**Rumus `upah_kotor` staf:**
```
tarif_pokok
+ (hari_hadir × tarif_harian)
+ (hari_disiplin × tarif_disiplin)
+ (hari_hadir × tarif_transpor)
+ (hari_lembur_staf × tarif_lembur)
+ bonus
```

**Firmansyah:** tarif_pokok = 2.000.000, semua tarif lain = 0 → upah_kotor selalu 2.000.000 berapa pun hari hadir. Ini otomatis tertangani karena 0 × hari_hadir = 0 — tidak perlu logik khusus.

---

## 4. Logik "Hitung Upah"

Saat tombol "Hitung Upah" ditekan:

1. **Hapus line lama** yang sudah ada di periode ini (kalau ada, misalnya dari hitungan sebelumnya yang mau di-refresh)
2. **Ambil daftar pekerja** berdasarkan `tipe`:
   - Mingguan → semua employee dengan `x_tipe_pekerja = tukang` yang punya absensi `dikuatkan` di rentang periode
   - Bulanan → semua employee dengan `x_tipe_pekerja = staf`
3. **Per pekerja, generate satu `upah.line`:**
   - Hitung hari kerja/disiplin/lembur dari model absensi yang sesuai
   - Snapshot tarif dari employee saat itu (bukan referensi live — kalau tarif berubah besok, periode lama tidak ikut berubah)
   - Hitung `upah_kotor`
   - Cari periode sebelumnya yang `state=ditutup` dengan `tipe` yang sama → ambil `saldo_akhir` sebagai `saldo_awal` untuk periode ini, atau 0 kalau tidak ada
   - `total_dibayar` default 0 — diisi manual oleh user

**Poin penting:** tombol ini bisa ditekan ulang selama masih `dihitung` (belum `ditutup`) — ini sengaja, supaya kalau ada absensi yang baru dikuatkan setelah pertama kali dihitung, bisa di-refresh tanpa membuat periode baru.

---

## 5. Field `total_dibayar` — Desain Transisi

Saat ini: field ini diinput **manual** oleh user — ketik angka berapa yang sudah dibayar ke pekerja selama periode itu. Ini menggantikan kolom KASBON di sheet REKAP yang sudah ada.

Nanti (setelah `hociro.pembayaran` dibangun): field ini berubah jadi **computed** — otomatis menjumlahkan semua record pembayaran untuk pekerja ini dalam rentang periode.

**Untuk Agent 2:** definisikan `total_dibayar` sebagai field Monetary biasa (bukan computed) sekarang. Tambahkan komentar di kode:
```python
# TODO: ganti jadi computed field setelah hociro.pembayaran dibangun
# Saat ini diinput manual sebagai bridge dari Excel lama
total_dibayar = fields.Monetary(
    string='Total Dibayar',
    currency_field='currency_id',
    help='Diisi manual. Akan otomatis dari pembayaran setelah modul kasbon jadi.',
)
```

---

## 6. View

### 6.1 Periode — List View
Kolom: Name, Tipe, Tanggal Mulai, Tanggal Selesai, Total Upah Kotor, Total Dibayar, Total Saldo, State.

### 6.2 Periode — Form View
Header: name, tipe, tanggal_mulai, tanggal_selesai, state (statusbar).
Tombol: "Hitung Upah" (visible di `draft` dan `dihitung`), "Tutup Periode" (visible di `dihitung`), "Buka Kembali" (visible di `ditutup`).
Tab "Detail Upah": One2many `line_ids` dalam mode list editable=bottom.

### 6.3 Line — Inline List (di dalam form Periode)
Kolom umum: Employee, Upah Kotor, Total Dibayar, Saldo Awal, Saldo Akhir.
Kolom tukang (invisible kalau tipe bukan mingguan): Hari Kerja, Hari Lembur, Tarif Harian, Tarif Lembur.
Kolom staf (invisible kalau tipe bukan bulanan): Hari Hadir, Hari Disiplin, Tarif Pokok, Tarif Harian, Tarif Disiplin, Tarif Transpor, Bonus.

### 6.4 Menu
```
Upah & Absensi
├── Absensi
│   ├── Tukang
│   └── Staf
├── Upah           ← BARU
│   ├── Periode Upah
│   └── (nanti: Pembayaran)
└── Analytic
```

### 6.5 Search View
Filter: Draft, Dihitung, Ditutup, Mingguan, Bulanan.
Group by: Tipe, State.

---

## 7. Peringatan Visual

- `saldo_akhir < 0`: baris merah di list (decoration-danger) — pekerja sudah dibayar lebih dari upahnya. Ini nyata di data historis (Heri −200.000, Hendra −1.500.000).
- `saldo_akhir > (2 × tarif_harian × 6)` untuk tukang: baris kuning (decoration-warning) — pekerja punya tagihan besar yang belum dibayar, butuh perhatian.

---

## 8. Security

- `base.group_user`: read pada periode dan line — supaya staf bisa lihat rekap mereka sendiri (nantinya)
- `base.group_system`: full CRUD — hanya admin yang bisa membuat periode, menjalankan "Hitung Upah", dan menutup periode
- Tombol "Hitung Upah" dan "Tutup Periode" dibatasi ke `base.group_system` lewat `groups=` di XML

---

## 9. Yang TIDAK Dibangun Sekarang

- Slip gaji cetak (PDF) — baru relevan kalau format slip sudah disetujui Mr. Ricoh
- Otomasi pembuatan periode (auto-generate tiap Sabtu/akhir bulan) — manual dulu, biar user paham alurnya
- Integrasi ke jurnal akuntansi — terpisah di fase accounting

---

## 10. Keputusan yang Sudah Dikunci

| Keputusan | Alasan |
|---|---|
| Tarif di-snapshot, bukan referensi live | Kalau tarif naik, periode lama tidak boleh ikut berubah |
| `total_dibayar` manual dulu | `hociro.pembayaran` belum ada, tapi saldo tetap bisa dihitung |
| Satu model line untuk tukang dan staf | Field tukang di-hide kalau tipe bulanan, dan sebaliknya — lebih sederhana dari dua model terpisah |
| Lembur staf manual, bukan dari absensi | Data lembur staf tidak tercatat di Google Form sekarang |

---

*Dokumen ini adalah input untuk Agent 2 (Claude Code Desktop). Perubahan desain hanya lewat Agent 1.*
