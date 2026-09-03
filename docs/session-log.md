# Session Log — 2026-09-03

Catatan status kerja di repo `hociro-erp`, ditulis di akhir sesi supaya sesi berikutnya (siapa pun yang melanjutkan — manusia atau agent) tidak perlu membaca ulang seluruh transkrip.

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
  - ❌ **Poin 5 (install ke database bersih) BELUM dijalankan** — tidak ada instance Odoo 19 / Postgres di mesin dev ini. Lihat §3 dan §4 di bawah.

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
- **Checklist §5 poin 5 `v19-conventions.md`** (`odoo -d test_bersih -i hociro_upah --stop-after-init`) belum bisa dijalankan — butuh instance Odoo 19 nyata.

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
3. **Checklist §5 poin 5 (`v19-conventions.md`) belum pernah lolos** — modul ini belum pernah benar-benar diinstal ke Odoo 19 sungguhan. Semua "lolos checklist" sejauh ini hanya cek statis (grep pola v16 + `ast.parse`/XML parse), bukan bukti modul bisa jalan.
4. **Commit `3e33305 "read upah"` di riwayat git tidak dibuat lewat perintah eksplisit dalam sesi kerja ini** — muncul begitu saja di antara "Initial commit" dan commit pertama yang saya buat, berisi isi awal modul `hociro_upah/` (sebelum dipindah ke `addons/`). Sudah dilaporkan ke user saat ditemukan, tidak ada investigasi lebih lanjut dan tidak ada tindakan diambil terhadapnya. Kalau ini bukan hasil kerja yang diketahui/diinginkan, cek riwayat commit dan proses lain (hook, sesi lain) yang mungkin punya akses tulis ke repo ini.
5. **`ir.model.access.csv` masih sangat longgar** — semua user internal (`base.group_user`) punya akses penuh CRUD ke `hociro.absensi.tukang`, termasuk `unlink` (walau dibatasi lewat kode untuk record `dikuatkan`, bukan lewat access right). Belum ada pemisahan peran pengawas vs staf lain.
6. **`.env`, `config/odoo.conf`, `docker-compose.yml` belum ada sebagai file nyata di mana pun** — baru contoh isi di dokumentasi. Jangan lupa buat filenya dulu sebelum `docker compose up`.
7. **Open items dari `docs/specs/hociro_upah.md` §6 belum diputuskan** (pemetaan Tempat lama ke proyek, trade name per proyek, dimensi proyek untuk absensi staf, daftar kantong lengkap) — di luar scope sesi ini, tapi menghalangi migrasi data (§5 spec) kalau belum ada keputusan.

---

*Ditulis di akhir sesi kerja 2026-09-03. File ini di-commit tapi (per instruksi) belum di-push — cek isinya dulu sebelum push.*
