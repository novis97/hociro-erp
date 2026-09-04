# Konvensi Odoo 19 — Panduan Wajib Penulisan Kode

**Repo:** `hociro-erp`
**Target:** Odoo 19.0 Community, self-hosted VPS
**Pembaca:** Agent 2 (developer), Agent 3 (sysadmin)
**Ditulis oleh:** Agent 1 (arsitek/operator)

---

## 0. Aturan Nol — Baca Ini Dulu

**Jangan menulis kode Odoo dari ingatan.** Model bahasa punya data pelatihan yang jauh lebih tebal untuk Odoo 15–17 dibanding 19. Kode yang "terlihat benar" sering kali adalah kode v16/v17 yang akan gagal load di v19, atau lebih buruk: load tanpa error tapi berperilaku salah.

Sebelum menulis model/view/field apa pun, **verifikasi ke source Odoo 19 yang terpasang di VPS.**

```bash
# Lokasi source (sesuaikan dengan instalasi)
export ODOO_SRC=/opt/odoo/odoo

# Contoh: mau extend hr.attendance? Baca dulu definisinya.
cat $ODOO_SRC/addons/hr_attendance/models/hr_attendance.py

# Contoh: mau bikin list view? Lihat contoh asli v19.
cat $ODOO_SRC/addons/hr_attendance/views/hr_attendance_views.xml
```

Kalau ragu tentang sebuah API, **grep dulu, tulis kemudian.** Satu perintah grep lebih murah daripada satu siklus debug.

---

## 1. Perubahan yang Sudah Pasti (v17 → v19)

Semua ini sudah berlaku di v19. Kode yang melanggarnya akan gagal.

### 1.1 `attrs` dan `states` sudah DIHAPUS

Ini pelanggaran paling sering muncul dari kode hasil generate.

```xml
<!-- SALAH — pola v16 ke bawah, akan error di v19 -->
<field name="upah_harian" attrs="{'invisible': [('tipe_upah', '!=', 'mingguan')]}"/>
<field name="catatan" attrs="{'readonly': [('state', '=', 'done')]}"/>

<!-- BENAR — v17+ -->
<field name="upah_harian" invisible="tipe_upah != 'mingguan'"/>
<field name="catatan" readonly="state == 'done'"/>
```

Ekspresi di dalamnya adalah Python, bukan domain list. Field yang dipakai di ekspresi **harus ada di view** (boleh `column_invisible` atau `invisible="1"`).

### 1.2 `<tree>` → `<list>`

```xml
<!-- SALAH -->
<record id="view_kasbon_tree" model="ir.ui.view">
    <field name="arch" type="xml">
        <tree string="Kasbon">...</tree>
    </field>
</record>

<!-- BENAR -->
<record id="view_kasbon_list" model="ir.ui.view">
    <field name="arch" type="xml">
        <list string="Kasbon">...</list>
    </field>
</record>
```

Berlaku juga untuk `view_mode`: gunakan `list,form`, bukan `tree,form`.

Di dalam `<list>`, atribut `invisible` pada kolom disebut `column_invisible` kalau tujuannya menyembunyikan seluruh kolom.

### 1.3 `name_get()` sudah dihapus

```python
# SALAH
def name_get(self):
    result = []
    for rec in self:
        result.append((rec.id, f"{rec.employee_id.name} - {rec.tanggal}"))
    return result

# BENAR
@api.depends('employee_id', 'tanggal')
def _compute_display_name(self):
    for rec in self:
        rec.display_name = f"{rec.employee_id.name} - {rec.tanggal}"
```

### 1.4 `create()` wajib multi-record

```python
# SALAH
@api.model
def create(self, vals):
    return super().create(vals)

# BENAR
@api.model_create_multi
def create(self, vals_list):
    return super().create(vals_list)
```

### 1.5 QWeb: `t-esc` → `t-out`

```xml
<!-- SALAH -->
<span t-esc="doc.total"/>

<!-- BENAR -->
<span t-out="doc.total"/>
```

### 1.6 Chatter memakai tag tunggal

```xml
<!-- SALAH — pola lama, verbose -->
<div class="oe_chatter">
    <field name="message_follower_ids"/>
    <field name="activity_ids"/>
    <field name="message_ids"/>
</div>

<!-- BENAR -->
<chatter/>
```

### 1.7 `<group>` group-by di search view: tanpa `expand` dan `string`

Sejak commit resmi Odoo [`a814ad6b`](https://github.com/odoo/odoo/commit/a814ad6b18da68370376d5cce26e06434cde704f) ("[REF] *: remove string attribute from group in search view"), elemen `<group>` yang membungkus filter "Kelompokkan/Group By" di **search view** tidak lagi menerima atribut `expand` maupun `string`. Modul `hociro_upah` sempat gagal install (`ParseError: Invalid view ... search definition`) karena ini.

```xml
<!-- SALAH — pola v17/v18, gagal ParseError di v19 -->
<group expand="0" string="Group By">
    <filter string="Proyek" name="group_proyek" context="{'group_by': 'proyek_id'}"/>
</group>

<!-- BENAR — v19 -->
<group>
    <filter string="Proyek" name="group_proyek" context="{'group_by': 'proyek_id'}"/>
</group>
```

Catatan: atribut `string` pada `<group>` di **form view** tidak terpengaruh — larangan ini spesifik untuk `<group>` di dalam `<search>`.

### 1.8 Manifest wajib punya `license`

```python
{
    'name': 'Hociro — Upah Harian',
    'version': '19.0.1.0.0',
    'category': 'Human Resources',
    'license': 'LGPL-3',
    'depends': ['hr', 'analytic'],
    'data': [
        'security/ir.model.access.csv',
        'views/menu_views.xml',
    ],
    'installable': True,
    'application': False,
}
```

Format `version` harus `19.0.x.y.z` — prefix versi Odoo, bukan `1.0.0`.

---

## 2. Area yang WAJIB Diverifikasi Sebelum Dipakai

Ini bukan daftar larangan. Ini daftar hal yang **berubah di v19 dan belum terkonfirmasi detailnya**. Jangan asumsikan, cek dulu.

### 2.1 `hr.contract` — kemungkinan besar sudah dilebur

Odoo 19 menyatukan employee record dan contract dalam satu struktur. Kode apa pun yang mereferensikan model `hr.contract` berisiko gagal.

```bash
# Cek eksistensi model
grep -rn "_name = 'hr.contract'" $ODOO_SRC/addons/
```

Kalau tidak ketemu: jangan pakai. Simpan field upah langsung di `hr.employee` (lihat §3).

**Untuk proyek ini, ini tidak jadi masalah** — kita tidak memakai contract sama sekali.

### 2.2 `hr.attendance` — struktur overtime berubah

Cek field yang tersedia sebelum extend:

```bash
grep -n "fields\." $ODOO_SRC/addons/hr_attendance/models/hr_attendance.py
```

### 2.3 Analytic — plan-based sejak v17

`account.analytic.account` sekarang terikat ke `account.analytic.plan`. Field distribusi analitik memakai `analytic_distribution` (JSON), bukan `analytic_account_id`.

Untuk proyek ini, Plan yang dipakai: **Trade Name** (Hociro/Hananikasha) dan **Project** (Hananikasha saja).

```bash
grep -n "analytic_distribution" $ODOO_SRC/addons/analytic/models/*.py
```

### 2.4 Owl — komponen JS

Kalau ada widget custom, jangan tulis dari ingatan. Salin pola dari komponen v19 yang ada di `$ODOO_SRC/addons/web/static/src/`.

---

## 3. Keputusan Arsitektur untuk Proyek Ini

Keputusan ini sudah final. Jangan diubah tanpa persetujuan Agent 1.

### 3.1 TIDAK memakai `hr_payroll` maupun OCA `payroll`

**Alasan:**
- Tidak ada potongan PPh 21
- Tidak ada potongan BPJS
- Tidak ada slip gaji formal untuk keperluan pajak

Yang dibutuhkan hanyalah perhitungan upah dan daftar bayar. Memasang engine payroll berarti membawa overhead salary rule, salary structure, contract, dan payslip run yang seluruhnya tidak terpakai — ditambah dependency ke repo OCA yang migrasi 19.0-nya masih berjalan.

**Dependency eksternal proyek ini: NOL.** Hanya modul core Odoo.

### 3.2 Dua siklus pembayaran

| | Staf bulanan | Tukang & kuli |
|---|---|---|
| Periode | Akhir bulan | Tiap Sabtu (mingguan) |
| Dasar hitung | Gaji tetap | Hari kerja × upah harian |
| Absensi per proyek | Tidak perlu | **Wajib** |
| Potongan kasbon | — | Ya |

### 3.3 Absensi kuli BUKAN `hr.attendance`

`hr.attendance` berbasis check-in/check-out dengan timestamp. Tukang dan kuli tidak melakukan clock-in di kiosk — mandor mencatat kehadiran harian.

Model yang dipakai: **pencatatan harian**, bukan jam masuk-keluar.

```
hociro.absensi.harian
├── tanggal (date)
├── employee_id (many2one hr.employee)
├── project_id (many2one account.analytic.account, domain=plan Project)
└── status (selection: hadir / setengah_hari / absen)
```

Satu record = satu orang, satu hari, satu proyek. Input massal per proyek per hari lewat wizard.

### 3.4 Field upah disimpan di `hr.employee`

Bukan di contract. Extend langsung:

```
hr.employee (extend)
├── x_tipe_upah (selection: bulanan / mingguan)
├── x_upah_harian (monetary — dipakai kalau mingguan)
└── x_gaji_bulanan (monetary — dipakai kalau bulanan)
```

---

## 4. Template Prompt untuk Agent 2

Setiap tugas ke Agent 2 harus memakai format ini. Jangan kirim instruksi telanjang.

```
KONTEKS PROYEK
- Odoo 19.0 Community, self-hosted
- Modul: hociro_upah
- Dependency: hr, analytic (TIDAK ADA yang lain)

KONVENSI WAJIB
[paste isi §1 dari v19-conventions.md]

TUGAS
[deskripsi spesifik]

SEBELUM MENULIS KODE
1. Sebutkan file source Odoo 19 mana yang perlu saya cek untuk verifikasi
2. Tunggu saya kirimkan isinya
3. Baru tulis kode

OUTPUT
- Path file lengkap untuk setiap file
- Kode utuh, bukan potongan
- Catat asumsi apa pun yang belum terverifikasi
```

Poin 1–3 penting. Memaksa Agent 2 meminta verifikasi lebih dulu memutus kebiasaan menulis dari ingatan.

---

## 5. Checklist Sebelum Commit

Jalankan sebelum setiap commit ke repo:

```bash
# 1. Tidak ada attrs / states tersisa
grep -rn 'attrs=' addons/ && echo "GAGAL: attrs masih ada"
grep -rn 'states=' addons/ && echo "GAGAL: states masih ada"

# 2. Tidak ada <tree> tersisa
grep -rn '<tree' addons/ && echo "GAGAL: <tree> harus jadi <list>"

# 3. Tidak ada name_get tersisa
grep -rn 'def name_get' addons/ && echo "GAGAL: pakai _compute_display_name"

# 4. Tidak ada t-esc tersisa
grep -rn 't-esc=' addons/ && echo "GAGAL: pakai t-out"

# 5. Tidak ada <group expand=...> atau <group string=...> di search view
grep -rn '<group expand=' addons/*/views/*.xml && echo "GAGAL: expand tidak valid di <group> search view v19"
grep -rln '<search' addons/*/views/*.xml | xargs -r grep -n '<group string=' && echo "GAGAL: string tidak valid di <group> search view v19"

# 6. Modul benar-benar bisa di-install di database bersih
odoo -d test_bersih -i hociro_upah --stop-after-init
```

Poin 6 tidak bisa dinegosiasi. Modul yang "berhasil upgrade" di database lama sering gagal di database bersih karena data XML yang sudah terlanjur ada.

---

## 6. Catatan Versi

- Odoo 19 rilis September 2025, disupport sampai Odoo 20 rilis + 2 siklus (~Odoo 22)
- Odoo 20 diperkirakan rilis sekitar Oktober 2026 — **tidak** menjadi alasan menunda; v19 justru punya runway support lebih panjang dibanding v18
- Pin versi Odoo ke commit/tag tertentu di VPS. Jangan `git pull` branch 19.0 secara membabi buta di production.

---

*Dokumen ini adalah sumber kebenaran untuk konvensi kode. Kalau ada konflik antara dokumen ini dan output Agent 2, dokumen ini yang menang. Perubahan hanya lewat Agent 1.*
