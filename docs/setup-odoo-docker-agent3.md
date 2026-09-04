# Setup Odoo 19 via Docker — Instruksi untuk Agent 3

**Status:** Menggantikan `docs/setup-odoo-agent3.md` (instalasi manual venv/systemd). Dokumen lama ditandai *superseded*, jangan dihapus — simpan sebagai riwayat keputusan.

**Domain:**
- Production: `erp.hociroarchitects.com`
- Staging: `staging.hociroarchitects.com` — **tidak jalan 24 jam**, lihat §4

**Spek VPS:** 2 vCPU (>3.4GHz) / 3GB RAM / 40GB NVMe. RAM adalah titik paling ketat di spek ini — semua konfigurasi di bawah disesuaikan untuk itu (threaded mode, swap wajib, staging tidak boleh jalan bersamaan dengan production). Storage lebih longgar dibanding spek sebelumnya berkat NVMe 40GB, tapi monitoring tetap dipasang (§6).

---

## 0. Prasyarat di VPS

```bash
sudo apt update && sudo apt upgrade -y
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
# logout/login supaya group docker aktif
docker --version
docker compose version
```

### 0.1 Swap — WAJIB di RAM 3GB, bukan opsional

Tanpa swap, satu lonjakan pemakaian memori (mis. generate laporan PDF besar, atau import data massal) bisa memicu OOM killer Linux mematikan proses Odoo atau Postgres tanpa peringatan apa pun ke user. Di NVMe, penalti kecepatan swap kecil — jauh berbeda dengan swap di HDD yang biasanya dihindari.

```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

# Turunkan swappiness — swap dipakai sebagai jaring pengaman, bukan memori utama
echo 'vm.swappiness=10' | sudo tee -a /etc/sysctl.conf
sudo sysctl -p
```

Verifikasi: `free -h` harus menunjukkan swap 2.0G aktif.

---

## 1. Struktur Direktori

```
/opt/hociro-erp/
├── docker-compose.yml
├── .env
├── config/
│   └── odoo.conf
├── repo/                   ← repo hociro-erp di-clone ke sini
│   └── addons/
│       └── hociro_upah/    ← modul Odoo, di-mount ke container
└── backups/
```

```bash
sudo mkdir -p /opt/hociro-erp/{config,repo,backups}
sudo chown -R $USER:$USER /opt/hociro-erp
cd /opt/hociro-erp
```

`repo/` adalah tempat repo GitHub (`novis97@gmail.com`) di-clone; addons Odoo ada di `repo/addons/`. Agent 3 tidak menulis kode di sini — hanya `git pull` setelah Agent 2 commit.

---

## 2. `.env`

```env
POSTGRES_DB=postgres
POSTGRES_USER=odoo19
POSTGRES_PASSWORD=GANTI_DENGAN_PASSWORD_KUAT_ACAK
ODOO_ADMIN_PASSWD=GANTI_DENGAN_PASSWORD_KUAT_LAIN
ODOO_VERSION=19.0
```

Dua password di atas **berbeda** dan **bukan** untuk dibagikan ke Mr. Ricoh. `ODOO_ADMIN_PASSWD` adalah master password Database Manager.

---

## 3. `docker-compose.yml` — Production

```yaml
services:
  db:
    image: postgres:16
    restart: always
    environment:
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    command: >
      -c shared_buffers=256MB
      -c work_mem=8MB
      -c maintenance_work_mem=64MB
      -c max_connections=40
    deploy:
      resources:
        limits:
          memory: 700M
    volumes:
      - odoo-db-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER}"]
      interval: 10s
      retries: 5

  odoo:
    image: odoo:19.0
    restart: always
    depends_on:
      db:
        condition: service_healthy
    ports:
      - "127.0.0.1:8069:8069"
    environment:
      HOST: db
      USER: ${POSTGRES_USER}
      PASSWORD: ${POSTGRES_PASSWORD}
    deploy:
      resources:
        limits:
          memory: 1800M
    volumes:
      - odoo-web-data:/var/lib/odoo        # filestore — WAJIB persistent
      - ./config:/etc/odoo
      - ./repo/addons:/mnt/extra-addons

volumes:
  odoo-db-data:
  odoo-web-data:
```

**Kenapa ada `deploy.resources.limits` di sini** — di RAM 3GB, satu container yang "bocor" memori (bug modul custom, misalnya) bisa menghabiskan seluruh RAM dan menjatuhkan container lain termasuk Postgres. Limit ini bukan optimasi performa, tapi pagar supaya kegagalan satu bagian tidak merambat ke semuanya. Total limit (700M + 1800M = 2.5GB) sengaja disisakan ruang untuk OS + Docker daemon (~500MB) dari total 3GB.

Nilai `shared_buffers=256MB` di Postgres sengaja diturunkan dari default rule-of-thumb (25% RAM) karena RAM total sudah sempit — prioritaskan agar Odoo punya cukup memori untuk render halaman, bukan Postgres cache besar.

**`odoo-web-data` menyimpan filestore** — semua lampiran, foto absensi tukang, dokumen yang diunggah user. Ini named volume, bukan bind mount biasa, supaya tidak sengaja terhapus saat `docker compose down -v` dijalankan tanpa sadar. **Jangan pernah jalankan `down -v` di production** kecuali sudah pasti ingin menghapus semua data.

Port di-bind ke `127.0.0.1` saja — akses publik lewat Nginx (§5), bukan port 8069 langsung ke internet.

---

## 4. `docker-compose.staging.yml` — Dijalankan Sesuai Kebutuhan

```yaml
services:
  staging-db:
    image: postgres:16
    environment:
      POSTGRES_DB: postgres
      POSTGRES_USER: odoo19
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - odoo-staging-db-data:/var/lib/postgresql/data

  staging-odoo:
    image: odoo:19.0
    depends_on:
      - staging-db
    ports:
      - "127.0.0.1:8070:8069"
    environment:
      HOST: staging-db
      USER: odoo19
      PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - odoo-staging-web-data:/var/lib/odoo
      - ./config:/etc/odoo
      - ./repo/addons:/mnt/extra-addons

volumes:
  odoo-staging-db-data:
  odoo-staging-web-data:
```

**Cara pakai — tidak jalan default, dan di RAM 3GB ini aturan keras, bukan sekadar rapi-rapi:**
```bash
# SEBELUM nyalakan staging: pastikan tidak ada sesi Mr. Ricoh yang sedang aktif
# di production. Di RAM 3GB, dua stack Odoo+Postgres berjalan bersamaan
# berisiko nyata memicu OOM — bukan skenario ekstrem, cukup satu laporan
# berat di kedua sisi bersamaan sudah bisa memicunya.

docker compose -f docker-compose.staging.yml up -d

# Test instalasi bersih (wajib per checklist v19-conventions.md §5)
docker compose -f docker-compose.staging.yml exec staging-odoo \
    odoo -d staging_test -i hociro_upah --stop-after-init

# Matikan SEGERA setelah selesai — jangan dibiarkan idle menyala
docker compose -f docker-compose.staging.yml down
```

**Jadwal aman:** kalau memungkinkan, jalankan sesi staging di luar jam kerja Mr. Ricoh (malam hari/dini hari), bukan sekadar "setelah selesai pakai lalu stop" — supaya ada margin kalau proses stop tertunda atau lupa.

---

## 5. `config/odoo.conf`

```ini
[options]
admin_passwd = ${ODOO_ADMIN_PASSWD}
addons_path = /usr/lib/python3/dist-packages/odoo/addons,/mnt/extra-addons
list_db = False
proxy_mode = True
workers = 0
max_cron_threads = 1
```

**`admin_passwd = ${ODOO_ADMIN_PASSWD}` TIDAK tersubstitusi otomatis.** Odoo membaca `odoo.conf` secara literal lewat `ConfigParser` — tidak ada shell atau Docker Compose di antaranya yang mengganti `${...}`. Nilai `${ODOO_ADMIN_PASSWD}` di `.env` **hanya** dipakai Compose untuk variabel di `docker-compose.yml`, bukan untuk isi file ini. Setelah mengisi `.env`, baris `admin_passwd` di `odoo.conf` harus diisi manual dengan nilai **sama persis** dengan `ODOO_ADMIN_PASSWD` di `.env` — kalau lupa, master password Database Manager akan jadi string literal `${ODOO_ADMIN_PASSWD}`, bukan password yang dimaksud.

`list_db = False` wajib sebelum domain publik aktif — kalau tidak, siapa saja bisa membuka `/web/database/manager` dan melihat daftar database Anda.

`proxy_mode = True` wajib karena Nginx di depan sebagai reverse proxy.

**`workers = 0` adalah penyesuaian khusus untuk spek 2-core/3GB ini.** Mode default Odoo (`workers` > 0) menjalankan banyak proses terpisah — cocok untuk server dengan banyak core dan RAM longgar, tapi di 2 core / 3GB tiap proses tambahan berarti memori terpisah pula. `workers = 0` menjalankan Odoo dalam satu proses threaded — lebih hemat memori, cukup untuk beban concurrency rendah seperti proyek ini (belasan user, bukan ratusan). Trade-off: kalau satu request berat (laporan besar) sedang diproses, request lain menunggu sebentar. Untuk skala Anda ini dampaknya kecil dan sepadan dengan penghematan memori.

`max_cron_threads = 1` membatasi background job (mis. reminder terjadwal) agar tidak menyaingi resource proses utama.

---

## 6. Nginx + SSL (di host, bukan di container)

```bash
sudo apt install -y nginx certbot python3-certbot-nginx
```

`/etc/nginx/sites-available/erp.hociroarchitects.com`:
```nginx
server {
    listen 80;
    server_name erp.hociroarchitects.com;

    location / {
        proxy_pass http://127.0.0.1:8069;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /longpolling {
        proxy_pass http://127.0.0.1:8072;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/erp.hociroarchitects.com /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d erp.hociroarchitects.com
```

Ulangi pola yang sama untuk `staging.hociroarchitects.com` → proxy ke `127.0.0.1:8070`, tapi sertifikat SSL-nya bisa langsung diminta sekarang juga (satu kali, tidak perlu diulang tiap staging dinyalakan) — hanya container-nya yang hidup-mati, bukan konfigurasi Nginx/SSL-nya.

---

## 7. Monitoring Disk — Wajib Karena Storage 20GB Ketat

```bash
# /opt/hociro-erp/check-disk.sh
#!/bin/bash
USAGE=$(df -h / | awk 'NR==2 {print $5}' | tr -d '%')
if [ "$USAGE" -gt 80 ]; then
    echo "PERINGATAN: disk usage ${USAGE}% di $(hostname)" | \
    mail -s "Disk Alert Hociro ERP" email-anda@domain.com
    # atau kirim ke webhook/WhatsApp API kalau mail server belum ada
fi
```
```bash
chmod +x check-disk.sh
crontab -e
# tambahkan: 0 */6 * * * /opt/hociro-erp/check-disk.sh
```

Kalau belum ada mail server terpasang, ganti bagian `mail` dengan `curl` ke webhook apa pun yang Anda pantau (Slack, Telegram bot, dll). Yang penting ada alert otomatis, bukan menunggu server penuh baru ketahuan.

### 7.1 Monitoring memori — tambahan wajib untuk RAM 3GB

Di spek sebelumnya (4GB) ini opsional. Di 3GB, ini sama pentingnya dengan disk check karena OOM lebih mungkin terjadi lebih dulu daripada disk penuh.

```bash
# /opt/hociro-erp/check-memory.sh
#!/bin/bash
MEM_USAGE=$(free | awk '/Mem:/ {printf "%.0f", $3/$2 * 100}')
SWAP_USAGE=$(free | awk '/Swap:/ {if ($2>0) printf "%.0f", $3/$2*100; else print 0}')

if [ "$MEM_USAGE" -gt 85 ] || [ "$SWAP_USAGE" -gt 50 ]; then
    echo "PERINGATAN: RAM ${MEM_USAGE}%, Swap ${SWAP_USAGE}% di $(hostname)" | \
    mail -s "Memory Alert Hociro ERP" email-anda@domain.com
fi
```
```bash
chmod +x check-memory.sh
crontab -e
# tambahkan: */15 * * * * /opt/hociro-erp/check-memory.sh
```

Interval 15 menit (lebih sering dari disk check 6 jam) karena tekanan memori bisa muncul dan berakibat fatal dalam hitungan menit, bukan jam.

**Kalau alert swap >50% muncul berulang** — itu sinyal jelas RAM 3GB sudah tidak cukup untuk beban aktual, bukan sekadar lonjakan sesaat. Saatnya upgrade RAM, bukan menoleransi swap terus-menerus (swap yang dipakai berat akan memperlambat semua operasi, sekalipun di NVMe).

---

## 8. Backup

```bash
# /opt/hociro-erp/backup.sh
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
cd /opt/hociro-erp
docker compose exec -T db pg_dump -U odoo19 postgres | gzip > backups/db_$DATE.sql.gz

# Filestore ikut di-backup, bukan cuma database
docker run --rm -v hociro-erp_odoo-web-data:/data -v /opt/hociro-erp/backups:/backup \
    alpine tar czf /backup/filestore_$DATE.tar.gz -C /data .

find backups/ -name "*.gz" -mtime +14 -delete
```
```bash
chmod +x backup.sh
crontab -e
# 0 2 * * * /opt/hociro-erp/backup.sh
```

**Backup database saja tidak cukup.** Filestore (lampiran, foto absensi) ada di volume terpisah — kalau tidak ikut di-backup, restore database akan menampilkan record tanpa lampirannya. Ini kesalahan umum di setup Docker Odoo yang sering luput.

Nama volume (`hociro-erp_odoo-web-data`) mengikuti pola `<nama-folder>_<nama-volume>` dari Docker Compose — verifikasi nama sebenarnya dengan `docker volume ls` setelah `up` pertama kali.

---

## 9. Menjalankan Production

```bash
cd /opt/hociro-erp
docker compose up -d
docker compose logs -f odoo   # pastikan tidak ada error saat startup
```

Buka `https://erp.hociroarchitects.com/web/database/manager`, buat database (mis. `hociro_prod`), demo data **dimatikan**, set password kuat. Setelah database dibuat, restart Odoo dengan `list_db = False` sudah aktif dari awal (§5) — jangan menunda ini sampai "nanti".

---

## 10. Data Contoh untuk Sesi Preview Mr. Ricoh

Sama seperti rencana sebelumnya:
- Analytic Plan **Trade Name** dan **Project** dibuat
- Tiga proyek contoh yang sudah terverifikasi: Finishing Bukulah, Finishing Moru, SP. Jambo Tape
- **Jangan** masukkan seluruh daftar Rencana Projek atau kode kantong (JBL/ILH/TMN/AND/hff) sebagai master permanen — masih open item di `docs/specs/hociro_upah.md` §6
- User login untuk Mr. Ricoh dibuat sebagai user biasa, bukan admin

---

## 11. Checklist Akhir

- [ ] `docker compose ps` menunjukkan `db` dan `odoo` sehat (healthy/running)
- [ ] `https://erp.hociroarchitects.com` bisa diakses dari luar VPS (tes dari HP, bukan dari server)
- [ ] `https://staging.hociroarchitects.com` sudah punya SSL, meski container-nya sedang mati
- [ ] `list_db = False` aktif di production
- [ ] Port 8069/8070 tidak bisa diakses langsung dari internet (hanya lewat Nginx)
- [ ] Named volume `odoo-web-data` terkonfirmasi via `docker volume ls`
- [ ] Backup DB + filestore sudah dites manual sekali, hasilnya bisa dibuka lagi
- [ ] Swap 2GB aktif dan terverifikasi (`free -h`)
- [ ] Cron disk-check, memory-check, dan backup aktif
- [ ] `workers = 0` terkonfirmasi di config, dan diuji: buka beberapa tab Odoo bersamaan tidak membuat server macet total
- [ ] Tiga proyek contoh + dua Analytic Plan sudah masuk
- [ ] Versi image dicatat: `docker inspect odoo:19.0 --format '{{.Id}}'` disimpan di `deploy-notes.md`
- [ ] Kalimat framing ke Mr. Ricoh (lihat dokumen setup manual §3, masih berlaku) sudah disiapkan Agent 1

---

*Setelah selesai, catat URL, versi image, dan tanggal setup di `docs/deploy-notes.md`. Tandai `docs/setup-odoo-agent3.md` versi manual sebagai superseded, bukan dihapus.*
