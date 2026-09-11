"""Seed data uji untuk hociro_upah -- master data + absensi, TANPA periode.

Dijalankan lewat `odoo shell`, BUKAN `python3 seed_test_data.py` -- skrip ini
memakai `env` yang cuma tersedia di dalam sesi odoo shell:

    odoo shell -d <nama_database_test_xxx> < scripts/seed_test_data.py

Baca docs/testing/database-uji.md dulu sebelum menjalankan ini -- dokumen itu
memuat cara menjalankan lengkap dan nilai (`hari_hadir`, `upah_kotor`,
`saldo_akhir`, dst.) yang seharusnya dihasilkan kalau seed ini dipakai untuk
menghitung periode, supaya hasilnya bisa dibandingkan sebagai baseline.

Yang dibuat: 3 staf + absensi Juli & Agustus 2026, 3 tukang + absensi dua
minggu berurutan Juni 2026. TIDAK ADA hociro.periode.upah yang dibuat --
periode dibuat oleh masing-masing pengujian sesuai skenarionya sendiri.
"""

from datetime import date, timedelta

# =====================================================================
# PENGAMAN 1 -- satu-satunya penghalang antara skrip ini dan hociro_prod.
# HARUS jadi kode pertama yang dijalankan.
# =====================================================================
DBNAME = env.cr.dbname
if not DBNAME.startswith('test_'):
    raise RuntimeError(
        f'Skrip ini MENOLAK jalan di database "{DBNAME}" -- nama database '
        'tidak diawali "test_". Ini satu-satunya pengaman yang berdiri di '
        'antara skrip ini dan hociro_prod. Jalankan hanya di database uji '
        'baru yang namanya diawali "test_".'
    )

# =====================================================================
# PENGAMAN 2 -- tolak kalau sudah ada data hociro_upah, supaya seed tidak
# menumpuk di atas data lama (dan supaya baseline-nya deterministik).
# =====================================================================
AbsensiStaf = env['hociro.absensi.staf']
AbsensiTukang = env['hociro.absensi.tukang']
Periode = env['hociro.periode.upah']

jumlah_absensi_staf_lama = AbsensiStaf.search_count([])
jumlah_absensi_tukang_lama = AbsensiTukang.search_count([])
jumlah_periode_lama = Periode.search_count([])

if jumlah_absensi_staf_lama or jumlah_absensi_tukang_lama or jumlah_periode_lama:
    raise RuntimeError(
        f'Database "{DBNAME}" sudah punya data hociro_upah: '
        f'{jumlah_absensi_staf_lama} hociro.absensi.staf, '
        f'{jumlah_absensi_tukang_lama} hociro.absensi.tukang, '
        f'{jumlah_periode_lama} hociro.periode.upah. '
        'Skrip ini menolak jalan di atas data lama -- pakai database yang '
        'baru saja dipasang modulnya (kosong), bukan yang sudah dipakai uji '
        'sebelumnya.'
    )

Employee = env['hr.employee']

# =====================================================================
# STAF -- 3 orang, tarif lengkap. Staf A & C pakai default
# x_batas_jam_disiplin (8.5). Staf B di-override ke 8.0 supaya perbedaan
# cutoff antar-karyawan teruji (lihat POLA_JAM_MASUK di bawah).
# =====================================================================
staf_a = Employee.create({
    'name': 'Staf A',
    'x_tipe_pekerja': 'staf',
    'x_gaji_pokok': 2_000_000,
    'x_tarif_harian': 50_000,
    'x_tarif_disiplin': 15_000,
    'x_tarif_transpor': 10_000,
    'x_tarif_lembur': 100_000,
    # x_batas_jam_disiplin TIDAK diisi -- pakai default field (8.5).
})
staf_b = Employee.create({
    'name': 'Staf B',
    'x_tipe_pekerja': 'staf',
    'x_gaji_pokok': 2_000_000,
    'x_tarif_harian': 50_000,
    'x_tarif_disiplin': 15_000,
    'x_tarif_transpor': 10_000,
    'x_tarif_lembur': 100_000,
    'x_batas_jam_disiplin': 8.0,  # override -- lihat docs/testing/database-uji.md
})
staf_c = Employee.create({
    'name': 'Staf C',
    'x_tipe_pekerja': 'staf',
    'x_gaji_pokok': 2_500_000,
    'x_tarif_harian': 60_000,
    'x_tarif_disiplin': 15_000,
    'x_tarif_transpor': 12_000,
    'x_tarif_lembur': 120_000,
    # x_batas_jam_disiplin TIDAK diisi -- pakai default field (8.5).
})

# Pola jam_masuk per hari-dalam-minggu (0=Senin ... 5=Sabtu), SAMA untuk
# ketiga staf -- yang membedakan hasil disiplin cuma x_batas_jam_disiplin
# masing-masing. Dirancang supaya sebagian hari lolos cutoff 8.5 tapi gagal
# di cutoff 8.0 (Selasa, Rabu), sebagian lolos keduanya (Senin, Jumat), dan
# sebagian gagal keduanya (Kamis, Sabtu). Lihat docs/testing/database-uji.md
# untuk perhitungan hari_disiplin lengkap per staf per periode.
POLA_JAM_MASUK = {
    0: 8.0,   # Senin   -- lolos 8.0 dan 8.5
    1: 8.3,   # Selasa  -- lolos 8.5, GAGAL 8.0
    2: 8.5,   # Rabu    -- lolos 8.5 (pas di batas), GAGAL 8.0
    3: 8.6,   # Kamis   -- GAGAL 8.0 dan 8.5
    4: 7.5,   # Jumat   -- lolos 8.0 dan 8.5
    5: 9.0,   # Sabtu   -- GAGAL 8.0 dan 8.5
}


def tanggal_senin_sabtu(tahun, bulan):
    """Semua tanggal Senin-Sabtu (weekday 0-5) dalam satu bulan, urut naik.
    Tanggal ditulis eksplisit lewat date(), bukan relatif -- baseline yang
    hasilnya berubah tergantung kapan skrip dijalankan bukan baseline."""
    hasil = []
    hari = date(tahun, bulan, 1)
    while hari.month == bulan:
        if hari.weekday() <= 5:  # 6 = Minggu, dikecualikan
            hasil.append(hari)
        hari = hari + timedelta(days=1)
    return hasil


tanggal_juli = tanggal_senin_sabtu(2026, 7)
tanggal_agustus = tanggal_senin_sabtu(2026, 8)

jumlah_absensi_staf_dibuat = 0
for staf in (staf_a, staf_b, staf_c):
    for hari in tanggal_juli + tanggal_agustus:
        AbsensiStaf.create({
            'tanggal': hari,
            'employee_id': staf.id,
            'status': 'hadir',
            'jam_masuk': POLA_JAM_MASUK[hari.weekday()],
        })
        jumlah_absensi_staf_dibuat += 1

# =====================================================================
# TUKANG -- 3 orang. Tukang 1 & 2 dengan tarif lengkap, Tukang 3 SENGAJA
# tanpa tarif (meniru kasus Wak Andi / Anak Bang Dedek di production --
# tukang yang datanya belum lengkap tapi tetap harus bisa diabsen).
# =====================================================================
tukang_1 = Employee.create({
    'name': 'Tukang 1',
    'x_tipe_pekerja': 'tukang',
    'x_upah_harian': 150_000,
    'x_tarif_lembur': 30_000,
})
tukang_2 = Employee.create({
    'name': 'Tukang 2',
    'x_tipe_pekerja': 'tukang',
    'x_upah_harian': 140_000,
    'x_tarif_lembur': 28_000,
})
tukang_3 = Employee.create({
    'name': 'Tukang 3 (tanpa tarif)',
    'x_tipe_pekerja': 'tukang',
    # x_upah_harian dan x_tarif_lembur SENGAJA tidak diisi (default 0) --
    # meniru tukang yang belum diberi tarif upah di production.
})

# Dua minggu berurutan, Senin-Sabtu, Juni 2026 -- dipakai untuk menguji
# periode Mingguan (tidak pernah ada di test_bersih_5). Minggu 1 punya satu
# hari lembur untuk Tukang 1 & 2 (Sabtu 6 Juni) supaya tarif_lembur ikut
# teruji; Tukang 3 tidak pernah lembur (tanpa tarif, hasilnya tetap 0).
MINGGU_1 = [date(2026, 6, 1) + timedelta(days=i) for i in range(6)]   # Sen 1 - Sab 6 Jun 2026
MINGGU_2 = [date(2026, 6, 8) + timedelta(days=i) for i in range(6)]   # Sen 8 - Sab 13 Jun 2026
HARI_LEMBUR = date(2026, 6, 6)

jumlah_absensi_tukang_dibuat = 0
for tukang in (tukang_1, tukang_2, tukang_3):
    for hari in MINGGU_1:
        lembur = 1.0 if (hari == HARI_LEMBUR and tukang != tukang_3) else 0.0
        AbsensiTukang.create({
            'tanggal': hari,
            'employee_id': tukang.id,
            'sesi_pagi': '1',
            'sesi_siang': '1',
            'lembur': lembur,
            'state': 'dikuatkan',
        })
        jumlah_absensi_tukang_dibuat += 1
    for hari in MINGGU_2:
        AbsensiTukang.create({
            'tanggal': hari,
            'employee_id': tukang.id,
            'sesi_pagi': '1',
            'sesi_siang': '1',
            'lembur': 0.0,
            'state': 'dikuatkan',
        })
        jumlah_absensi_tukang_dibuat += 1

env.cr.commit()

# =====================================================================
# RINGKASAN
# =====================================================================
print('=== Seed selesai di database "{}" ==='.format(DBNAME))
print('Staf dibuat: 3 (Staf A, Staf B [batas disiplin 8.0], Staf C)')
print('Absensi staf dibuat: {} ({} hari x 3 staf Juli + {} hari x 3 staf Agustus)'.format(
    jumlah_absensi_staf_dibuat, len(tanggal_juli), len(tanggal_agustus)
))
print('Rentang absensi staf: {} s/d {}'.format(tanggal_juli[0], tanggal_agustus[-1]))
print('Tukang dibuat: 3 (Tukang 1, Tukang 2, Tukang 3 [tanpa tarif])')
print('Absensi tukang dibuat: {} (2 minggu x 6 hari x 3 tukang)'.format(jumlah_absensi_tukang_dibuat))
print('Rentang absensi tukang: {} s/d {}'.format(MINGGU_1[0], MINGGU_2[-1]))
print('TIDAK ada hociro.periode.upah yang dibuat -- buat sesuai skenario ujimu.')
print('Nilai yang diharapkan per periode: lihat docs/testing/database-uji.md')
