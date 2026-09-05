# Spesifikasi Model — `hociro.absensi.staf`

**Versi:** draft 1  
**Modul:** `hociro_upah` (tambahan model, bukan modul baru)  
**Target:** Odoo 19.0 Community  
**Prasyarat baca:** `docs/v19-conventions.md`, `docs/specs/hociro_upah.md`

---

## 1. Konteks & Temuan dari Data Aktual

### 1.1 Sumber Data

Absensi staf sekarang berjalan lewat **Google Form** — staf submit foto jempol tiap pagi. Response tersimpan di Google Spreadsheet, lalu secara manual dipindahkan ke sheet `ABSENSI` per-orang di file Excel masing-masing (`01__Rahmad_2026B_.xlsx`, dst).

File yang sudah dianalisis:
- `Salinan_ABSENSI_2026B_studio__Responses_.xlsx` — Google Form responses gabungan
- `01__Rahmad_2026B_.xlsx` sampai `07__Rifa_Naswa.xlsx` — rekap per-orang

### 1.2 Keterangan yang Dipakai Sekarang

Dari Google Form responses (314 baris):
- `HADIR` (312×)
- `SAKIT` (2×)

Dari sheet ABSENSI individual:
- `H` = Hadir
- `S` = Sakit
- `C` = Cuti
- `I` (implisit) = Izin — ditemukan di satu entri "Hadir, Izin terlambat"

**Kesimpulan:** keterangan aktual sangat sederhana. Hanya 4 nilai yang bermakna: Hadir, Sakit, Cuti, Izin.

### 1.3 Jam Masuk

Tersedia dari kolom `Timestamp` di Google Form — format datetime penuh. Contoh aktual:
```
08:21, 08:22, 08:30, 08:13, 09:37, 08:27, 08:46, ...
```

Batas jam disiplin saat ini (dari catatan di form): **"waktu absensi akan dikurangi 2 menit"** — artinya submit jam 08:02 dianggap masuk jam 08:00. Batas resmi tidak tersurat, tapi dari data tarif disiplin yang hanya dihitung di hari tertentu, batas yang paling masuk akal adalah **08:30** (konsisten dengan nama field `x_batas_jam_disiplin` yang sudah direncanakan di spec §3.3).

### 1.4 Komponen Gaji Staf (Terverifikasi dari 7 File)

| Komponen | Rahmad | Meutia | Nada | Khalil | Firmansyah | Naura | Rifa |
|---|---|---|---|---|---|---|---|
| Gaji Pokok | 1.500.000 | 1.300.000 | 1.000.000 | 800.000 | 1.500.000 | 500.000 | - |
| Harian | 85.000 | 85.000 | 75.000 | 70.000 | 65.000 | 25.000 | 40.000 |
| Disiplin | 15.000 | 15.000 | 15.000 | 15.000 | 15.000 | 15.000 | 15.000 |
| Transpor | 20.000 | 15.000 | 10.000 | 10.000 | - | 10.000 | 10.000 |

Tarif Disiplin **seragam 15.000 untuk semua staf** — tidak per-orang, bisa jadi konstanta default.

Rifa tidak punya Gaji Pokok — kemungkinan tenaga paruh waktu atau kontrak harian murni.

---

## 2. Model `hociro.absensi.staf`

### 2.1 Definisi Field

```python
class HociroAbsensiStaf(models.Model):
    _name = 'hociro.absensi.staf'
    _description = 'Absensi Harian Staf Studio'
    _order = 'tanggal desc, employee_id'

    tanggal = fields.Date(required=True, default=fields.Date.context_today)
    employee_id = fields.Many2one(
        'hr.employee', string='Staf', required=True,
        domain=[('x_tipe_pekerja', '=', 'staf')],
    )
    status = fields.Selection([
        ('hadir', 'Hadir'),
        ('sakit', 'Sakit'),
        ('izin', 'Izin'),
        ('cuti', 'Cuti'),
        ('alfa', 'Alfa'),
    ], required=True, default='hadir')
    jam_masuk = fields.Float(
        string='Jam Masuk',
        widget='float_time',
        help='Diisi dari timestamp Google Form. Format: 8.5 = 08:30',
    )
    dapat_disiplin = fields.Boolean(
        compute='_compute_dapat_disiplin',
        store=True,
        string='Dapat Disiplin',
    )
    url_foto = fields.Char(
        string='Foto Kehadiran',
        help='Link Google Drive dari upload form absensi. Klik untuk buka foto.',
    )
    catatan = fields.Char()

    _sql_constraints = [  # akan diganti models.Constraint sesuai v19-conventions §1.9
        ('tanggal_employee_uniq', 'unique(tanggal, employee_id)',
         'Sudah ada absensi untuk staf ini pada tanggal yang sama.'),
    ]
```

**Catatan untuk Agent 2:** gunakan `models.Constraint` bukan `_sql_constraints`, sesuai `docs/v19-conventions.md` §1.9.

### 2.2 Compute `dapat_disiplin`

```python
@api.depends('status', 'jam_masuk', 'employee_id.x_batas_jam_disiplin')
def _compute_dapat_disiplin(self):
    for rec in self:
        if rec.status != 'hadir':
            rec.dapat_disiplin = False
        else:
            batas = rec.employee_id.x_batas_jam_disiplin or 8.5  # default 08:30
            rec.dapat_disiplin = (rec.jam_masuk > 0 and rec.jam_masuk <= batas)
```

**Aturan:** hanya status `hadir` yang bisa dapat disiplin, dan jam masuk harus terisi dan ≤ batas. Kalau `jam_masuk` kosong (0) → tidak dapat disiplin (prinsip: tidak ada bukti = tidak ada reward).

### 2.3 Field Tambahan di `hr.employee` (extend)

Field-field ini **belum** ada di kode saat ini (`hr_employee.py` baru punya `x_tipe_pekerja`, `x_upah_harian`, `x_tarif_lembur`). Perlu ditambahkan:

| Field | Tipe | Catatan |
|---|---|---|
| `x_gaji_pokok` | Monetary, `currency_field='currency_id'` | Staf; kosong untuk Rifa (harian murni) |
| `x_tarif_harian` | Monetary, `currency_field='currency_id'` | Staf; upah per hari hadir |
| `x_tarif_disiplin` | Monetary, `currency_field='currency_id'` | Default 15.000, bisa dioverride per-orang |
| `x_tarif_transpor` | Monetary, `currency_field='currency_id'` | Kosong untuk Firmansyah |
| `x_batas_jam_disiplin` | Float, widget `float_time` | Default 8.5 (08:30); batas cut-off jam masuk |

**Catatan:** semua field Monetary wajib menyertakan `currency_field='currency_id'` eksplisit, sesuai temuan dari `x_upah_harian` kemarin (`docs/v19-conventions.md` — perlu ditambahkan sebagai konvensi baru di §1).

---

## 3. View yang Diperlukan

### 3.1 List View
Kolom: Tanggal, Staf, Status, Jam Masuk, Dapat Disiplin.

Status ditampilkan dengan badge warna:
- Hadir → hijau
- Sakit/Izin → kuning
- Alfa → merah

### 3.2 Form View
Field: Tanggal, Staf, Status, Jam Masuk, Dapat Disiplin (readonly, computed), Catatan.

`jam_masuk` hanya relevan kalau status = `hadir` — sembunyikan untuk status lain:
```xml
<field name="jam_masuk" invisible="status != 'hadir'"/>
<field name="dapat_disiplin" invisible="status != 'hadir'" readonly="1"/>
```

### 3.3 Search View
Filter: Hadir, Sakit, Izin, Cuti, Alfa.  
Group by: Staf, Tanggal (bulan).

### 3.4 Menu
Tambahkan di bawah menu "Absensi" yang sudah ada:
```
Absensi
├── Absensi Tukang  (sudah ada)
└── Absensi Staf    (baru)
```

---

## 4. Migrasi Data Historis

Sumber: sheet `Form Responses 1` di tiap file staf (kolom Timestamp, NAMA, TANGGAL, KETERANGAN).

**Yang perlu diperhatikan:**
- `jam_masuk` diambil dari `Timestamp` kolom A (jam:menit dari datetime, dikurangi 2 menit sesuai aturan form)
- `NAMA` di form tidak selalu cocok persis dengan nama di `hr.employee` — perlu tabel pemetaan nama (misal "Firman" di form → "Firmansyah Ginting" di database)
- Data form dimulai April 2025 (Semester I), file yang di-upload adalah Semester II 2026 — ada gap data historis yang perlu diklarifikasi ke Mr. Ricoh

**Pemetaan nama yang sudah teridentifikasi:**

| Nama di Form | Nama di hr.employee |
|---|---|
| Firman | Firmansyah Ginting |
| Rahmad | Rahmad Delanof |
| Nada | Nada Syifa |
| Meutia | Meutia Kemala |
| Khalil | Khalil Humam |
| Naura | Naura Putrina Pasha |
| Rifa | Rifa Naswa |

---

## 5. Yang TIDAK Dibangun di Iterasi Ini

- **Input langsung dari form Odoo** — staf masih submit lewat Google Form sekarang. Perpindahan ke absensi langsung di Odoo adalah keputusan terpisah yang butuh sosialisasi ke staf. Tidak dibangun sekarang, tidak dijanjikan ke Mr. Ricoh.
- **Integrasi Google Form → Odoo** — data masuk via import manual dulu.
- **Absensi berbasis lokasi/foto embed** — foto disimpan di Google Drive, Odoo hanya menyimpan URL-nya lewat field `url_foto`. Keputusan ini menghindari beban storage VPS. Kalau ke depan dibutuhkan foto langsung di Odoo, bisa dimigrasi ke Cloudflare R2 tanpa mengubah struktur model.
- **Field foto langsung (fields.Image)** — dikecualikan untuk alasan storage: 7 staf × 22 hari × 12 bulan foto full resolusi HP bisa cepat menghabiskan storage VPS 40GB.

---

## 6. Keputusan yang Sudah Dikunci (tidak perlu tunggu Mr. Ricoh)

**6.1 Batas jam disiplin: default 08:30.**  
Hard-code sebagai default di `_compute_dapat_disiplin`, tapi bisa di-override per-orang lewat field `x_batas_jam_disiplin`. Kalau nanti Mr. Ricoh ingin batas berbeda untuk posisi tertentu, cukup edit field itu di record employee yang bersangkutan.

**6.2 Rifa tanpa Gaji Pokok: treat sebagai staf harian murni.**  
Field `x_gaji_pokok` dikosongkan (nilai 0). Formula upah bulanan nanti skip komponen yang nilainya 0 — tidak perlu status khusus.

**6.3 Foto kehadiran: simpan URL Google Drive, bukan file.**  
Field `url_foto` bertipe Char, menampilkan link yang bisa diklik di form view. Tidak ada embed foto langsung di Odoo. Bisa dimigrasi ke Cloudflare R2 nanti kalau dibutuhkan, tanpa mengubah struktur model.

## 7. Open Item yang Masih Menunggu Mr. Ricoh

**7.1 Gap data Semester I 2025.**  
File yang di-upload adalah Semester II 2026. Data April–Desember 2025 belum ada. Tanyakan: apakah perlu dimigrasi, atau cukup mulai dari data yang tersedia saja?

---

*Dokumen ini adalah input untuk Agent 2 (Claude Code Desktop). Perubahan desain hanya lewat Agent 1.*
