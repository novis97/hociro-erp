from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_is_zero


class HociroPeriodeUpah(models.Model):
    _name = 'hociro.periode.upah'
    _description = 'Periode Upah'
    _order = 'tanggal_mulai desc'

    name = fields.Char(compute='_compute_name', store=True)
    tipe = fields.Selection(
        [('mingguan', 'Mingguan'), ('bulanan', 'Bulanan')],
        string='Tipe', required=True,
        help='Mingguan untuk tukang, bulanan untuk staf.',
    )
    tanggal_mulai = fields.Date(string='Tanggal Mulai', required=True)
    tanggal_selesai = fields.Date(string='Tanggal Selesai', required=True)
    state = fields.Selection(
        [('draft', 'Draft'), ('dihitung', 'Dihitung'), ('ditutup', 'Ditutup')],
        string='Status', default='draft', required=True,
    )
    line_ids = fields.One2many('hociro.upah.line', 'periode_id', string='Baris Upah')
    # Model baru (bukan extend hr.employee), jadi tidak ada currency_id bawaan
    # dari modul core seperti pada hr_employee.py. Didefault dari company saat
    # dibuat, tanpa menambah field company_id terpisah yang tidak diminta spec.
    currency_id = fields.Many2one(
        'res.currency', string='Mata Uang',
        default=lambda self: self.env.company.currency_id,
    )
    total_upah_kotor = fields.Monetary(
        string='Total Upah Kotor', currency_field='currency_id',
        compute='_compute_totals', store=True,
    )
    total_dibayar = fields.Monetary(
        string='Total Dibayar', currency_field='currency_id',
        compute='_compute_totals', store=True,
    )
    total_saldo = fields.Monetary(
        string='Total Saldo', currency_field='currency_id',
        compute='_compute_totals', store=True,
    )

    @api.depends('tipe', 'tanggal_mulai')
    def _compute_name(self):
        for rec in self:
            if not rec.tanggal_mulai or not rec.tipe:
                rec.name = 'Periode Baru'
            elif rec.tipe == 'mingguan':
                tahun, minggu, _hari = rec.tanggal_mulai.isocalendar()
                rec.name = f'Mingguan {tahun}-W{minggu:02d}'
            else:
                rec.name = f"Bulanan {rec.tanggal_mulai.strftime('%Y-%m')}"

    @api.depends('line_ids.upah_kotor', 'line_ids.total_dibayar', 'line_ids.saldo_akhir')
    def _compute_totals(self):
        for rec in self:
            rec.total_upah_kotor = sum(rec.line_ids.mapped('upah_kotor'))
            rec.total_dibayar = sum(rec.line_ids.mapped('total_dibayar'))
            rec.total_saldo = sum(rec.line_ids.mapped('saldo_akhir'))

    def write(self, vals):
        if set(vals) - {'state'} and any(rec.state == 'ditutup' for rec in self):
            raise UserError(
                'Periode yang sudah ditutup tidak bisa diubah. '
                'Buka kembali terlebih dahulu (tombol "Buka Kembali").'
            )
        return super().write(vals)

    def action_hitung_upah(self):
        for rec in self:
            if rec.state == 'ditutup':
                raise UserError(
                    'Periode yang sudah ditutup tidak bisa dihitung ulang. '
                    'Buka kembali terlebih dahulu.'
                )
            rec._check_predecessor_lock()
            rec._check_successor_lock()
            vals_list = rec._prepare_line_vals()
            rec.line_ids.unlink()
            if vals_list:
                self.env['hociro.upah.line'].create(vals_list)
            rec.state = 'dihitung'

    def action_tutup_periode(self):
        for rec in self:
            if rec.state != 'dihitung':
                raise UserError('Hanya periode berstatus "Dihitung" yang bisa ditutup.')
            rec.state = 'ditutup'

    def action_buka_kembali(self):
        for rec in self:
            if rec.state != 'ditutup':
                raise UserError('Hanya periode berstatus "Ditutup" yang bisa dibuka kembali.')
            penerus = rec._get_penerus()
            if penerus:
                raise UserError(
                    f'Periode ini nggak bisa dibuka kembali, karena periode {penerus.name} '
                    'sudah dibuat dan angkanya ngambil saldo dari periode ini. Kalau '
                    'angkanya keliru dan harus diperbaiki, hapus dulu periode '
                    f'{penerus.name}, perbaiki periode ini, baru buat ulang periode '
                    f'{penerus.name}.'
                )
            rec.state = 'dihitung'

    def _get_penerus(self):
        """Periode dengan `tipe` sama yang mulai setelah periode ini selesai,
        dan sudah punya minimal satu hociro.upah.line -- artinya sudah
        menyerap saldo_awal dari periode ini lewat _prepare_line_vals().
        Successor lock (issue #2): dipakai di action_hitung_upah() dan
        action_buka_kembali(). Periode penerus yang masih kosong (belum
        pernah "Hitung Upah") belum menyerap apa pun, jadi tidak mengunci --
        kalau tidak, periode yang dibuat tidak berurutan akan mengunci
        pendahulunya secara permanen padahal belum ada yang jadi stale.
        """
        self.ensure_one()
        kandidat = self.env['hociro.periode.upah'].search([
            ('tipe', '=', self.tipe),
            ('tanggal_mulai', '>', self.tanggal_selesai),
        ], order='tanggal_mulai asc')
        return kandidat.filtered('line_ids')[:1]

    def _get_pendahulu_belum_ditutup(self):
        """Periode dengan `tipe` sama, tanggal_selesai lebih awal, yang
        belum berstatus ditutup. Predecessor lock (issue #2): tanpa ini,
        _prepare_line_vals() melompati periode seperti ini saat mencari
        saldo_awal (hanya mengambil dari periode `ditutup` terakhir),
        bukan memblokir -- sehingga periode ini bisa dihitung dengan
        saldo_awal dari periode yang lebih lama, melompati satu pendahulu
        yang belum ditutup, tanpa ada yang tahu.
        """
        self.ensure_one()
        return self.env['hociro.periode.upah'].search([
            ('tipe', '=', self.tipe),
            ('tanggal_selesai', '<', self.tanggal_mulai),
            ('state', '!=', 'ditutup'),
        ], order='tanggal_selesai desc', limit=1)

    def _check_predecessor_lock(self):
        self.ensure_one()
        pendahulu = self._get_pendahulu_belum_ditutup()
        if pendahulu:
            raise UserError(
                f'Periode ini belum bisa dihitung, karena periode {pendahulu.name} '
                'belum ditutup. Tutup dulu periode itu, supaya saldo yang terbawa '
                'ke sini angkanya benar.'
            )

    def _check_successor_lock(self):
        self.ensure_one()
        penerus = self._get_penerus()
        if penerus:
            raise UserError(
                f'Periode ini nggak bisa dihitung ulang, karena periode {penerus.name} '
                'sudah dibuat dan angkanya ngambil saldo dari periode ini. Kalau '
                'angkanya keliru dan harus diperbaiki, hapus dulu periode '
                f'{penerus.name}, perbaiki periode ini, baru buat ulang periode '
                f'{penerus.name}.'
            )

    def _prepare_line_vals(self):
        self.ensure_one()
        if self.tipe == 'mingguan':
            absensi = self.env['hociro.absensi.tukang'].search([
                ('tanggal', '>=', self.tanggal_mulai),
                ('tanggal', '<=', self.tanggal_selesai),
                ('state', '=', 'dikuatkan'),
            ])
            employees = absensi.mapped('employee_id')
        else:
            employees = self.env['hr.employee'].search([('x_tipe_pekerja', '=', 'staf')])

        prev_periode = self.env['hociro.periode.upah'].search([
            ('tipe', '=', self.tipe),
            ('state', '=', 'ditutup'),
            ('tanggal_selesai', '<', self.tanggal_mulai),
        ], order='tanggal_selesai desc', limit=1)
        saldo_awal_map = {
            line.employee_id.id: line.saldo_akhir for line in prev_periode.line_ids
        }

        vals_list = []
        employee_ids_terjaring = set()
        for employee in employees:
            employee_ids_terjaring.add(employee.id)
            vals = {
                'periode_id': self.id,
                'employee_id': employee.id,
                'saldo_awal': saldo_awal_map.get(employee.id, 0.0),
                'total_dibayar': 0.0,
            }
            if self.tipe == 'mingguan':
                vals.update({
                    'tarif_harian': employee.x_upah_harian,
                    'tarif_lembur': employee.x_tarif_lembur,
                })
            else:
                vals.update({
                    'tarif_pokok': employee.x_gaji_pokok,
                    'tarif_harian': employee.x_tarif_harian,
                    'tarif_disiplin': employee.x_tarif_disiplin,
                    'tarif_transpor': employee.x_tarif_transpor,
                    'tarif_lembur': employee.x_tarif_lembur,
                })
            vals_list.append(vals)

        # Karyawan yang tidak terjaring query di atas (mis. sudah
        # di-archive, active=False, sehingga hilang dari search default
        # Odoo) tapi punya saldo_akhir != 0 di periode sebelumnya tetap
        # dapat baris saldo-only -- tanpa ini, hutang/piutang ke orang
        # yang sudah berhenti kerja hilang dari sistem begitu saja.
        # tarif_* sengaja TIDAK diisi (default 0) supaya hari_hadir=0 dan
        # upah_kotor=0 pada baris ini, sesuai maksud saldo-only.
        rounding = self.currency_id.rounding
        for employee_id, saldo_akhir in saldo_awal_map.items():
            if employee_id in employee_ids_terjaring:
                continue
            if float_is_zero(saldo_akhir, precision_rounding=rounding):
                continue
            vals_list.append({
                'periode_id': self.id,
                'employee_id': employee_id,
                'saldo_awal': saldo_akhir,
                'total_dibayar': 0.0,
            })
        return vals_list


class HociroUpahLine(models.Model):
    _name = 'hociro.upah.line'
    _description = 'Baris Upah per Pekerja per Periode'
    _order = 'periode_id desc, employee_id'

    periode_id = fields.Many2one(
        'hociro.periode.upah', string='Periode', required=True, ondelete='cascade',
    )
    employee_id = fields.Many2one('hr.employee', string='Pekerja', required=True)
    tipe_pekerja = fields.Selection(
        related='employee_id.x_tipe_pekerja', store=True, string='Tipe Pekerja',
    )
    # Tidak disebut eksplisit di spec §3.1, tapi dibutuhkan sebagai
    # currency_field untuk semua Monetary di bawah — diturunkan dari periode.
    currency_id = fields.Many2one(
        related='periode_id.currency_id', store=True, string='Mata Uang',
    )

    # --- Khusus tukang (§3.2) ---
    hari_kerja = fields.Float(
        string='Hari Kerja', compute='_compute_hari_kerja_tukang', store=True,
    )
    hari_lembur = fields.Float(
        string='Hari Lembur', compute='_compute_hari_kerja_tukang', store=True,
    )

    # --- Khusus staf (§3.3) ---
    hari_hadir = fields.Integer(
        string='Hari Hadir', compute='_compute_hari_staf', store=True,
    )
    hari_disiplin = fields.Integer(
        string='Hari Disiplin', compute='_compute_hari_staf', store=True,
    )
    hari_lembur_staf = fields.Float(
        string='Hari Lembur (Staf)', default=0.0,
        help='Input manual. Lembur staf tidak tercatat otomatis dari absensi sekarang.',
    )

    # --- Tarif snapshot, disalin dari hr.employee saat "Hitung Upah" (§4) ---
    tarif_pokok = fields.Monetary(string='Tarif Pokok', currency_field='currency_id')
    tarif_harian = fields.Monetary(string='Tarif Harian', currency_field='currency_id')
    tarif_disiplin = fields.Monetary(string='Tarif Disiplin', currency_field='currency_id')
    tarif_transpor = fields.Monetary(string='Tarif Transpor', currency_field='currency_id')
    tarif_lembur = fields.Monetary(string='Tarif Lembur', currency_field='currency_id')
    bonus = fields.Monetary(string='Bonus', currency_field='currency_id', default=0.0)

    upah_kotor = fields.Monetary(
        string='Upah Kotor', currency_field='currency_id',
        compute='_compute_upah_kotor', store=True,
    )
    # TODO: ganti jadi computed field setelah hociro.pembayaran dibangun
    # Saat ini diinput manual sebagai bridge dari Excel lama
    total_dibayar = fields.Monetary(
        string='Total Dibayar',
        currency_field='currency_id',
        default=0.0,
        help='Diisi manual. Akan otomatis dari pembayaran setelah modul kasbon jadi.',
    )
    saldo_awal = fields.Monetary(string='Saldo Awal', currency_field='currency_id', default=0.0)
    saldo_akhir = fields.Monetary(
        string='Saldo Akhir', currency_field='currency_id',
        compute='_compute_saldo_akhir', store=True,
    )
    catatan = fields.Char()

    # Field ini TIDAK auto-refresh kalau absensi diedit setelah line dibuat
    # — harus klik "Hitung Upah" ulang untuk sinkron.
    @api.depends(
        'tipe_pekerja', 'employee_id',
        'periode_id.tanggal_mulai', 'periode_id.tanggal_selesai',
    )
    def _compute_hari_kerja_tukang(self):
        for line in self:
            if line.tipe_pekerja != 'tukang' or not line.periode_id or not line.employee_id:
                line.hari_kerja = 0.0
                line.hari_lembur = 0.0
                continue
            absensi = self.env['hociro.absensi.tukang'].search([
                ('employee_id', '=', line.employee_id.id),
                ('tanggal', '>=', line.periode_id.tanggal_mulai),
                ('tanggal', '<=', line.periode_id.tanggal_selesai),
                ('state', '=', 'dikuatkan'),
            ])
            line.hari_kerja = sum(absensi.mapped('hari_kerja'))
            line.hari_lembur = sum(absensi.mapped('lembur'))

    # Field ini TIDAK auto-refresh kalau absensi diedit setelah line dibuat
    # — harus klik "Hitung Upah" ulang untuk sinkron.
    @api.depends(
        'tipe_pekerja', 'employee_id',
        'periode_id.tanggal_mulai', 'periode_id.tanggal_selesai',
    )
    def _compute_hari_staf(self):
        for line in self:
            if line.tipe_pekerja != 'staf' or not line.periode_id or not line.employee_id:
                line.hari_hadir = 0
                line.hari_disiplin = 0
                continue
            absensi = self.env['hociro.absensi.staf'].search([
                ('employee_id', '=', line.employee_id.id),
                ('tanggal', '>=', line.periode_id.tanggal_mulai),
                ('tanggal', '<=', line.periode_id.tanggal_selesai),
            ])
            line.hari_hadir = len(absensi.filtered(lambda a: a.status == 'hadir'))
            line.hari_disiplin = len(absensi.filtered(lambda a: a.dapat_disiplin))

    @api.depends(
        'tipe_pekerja', 'hari_kerja', 'tarif_harian', 'hari_lembur', 'tarif_lembur',
        'tarif_pokok', 'hari_hadir', 'tarif_disiplin', 'hari_disiplin', 'tarif_transpor',
        'hari_lembur_staf', 'bonus',
    )
    def _compute_upah_kotor(self):
        for line in self:
            if line.tipe_pekerja == 'tukang':
                line.upah_kotor = (
                    (line.hari_kerja * line.tarif_harian)
                    + (line.hari_lembur * line.tarif_lembur)
                )
            elif line.tipe_pekerja == 'staf':
                line.upah_kotor = (
                    line.tarif_pokok
                    + (line.hari_hadir * line.tarif_harian)
                    + (line.hari_disiplin * line.tarif_disiplin)
                    + (line.hari_hadir * line.tarif_transpor)
                    + (line.hari_lembur_staf * line.tarif_lembur)
                    + line.bonus
                )
            else:
                line.upah_kotor = 0.0

    @api.depends('saldo_awal', 'upah_kotor', 'total_dibayar')
    def _compute_saldo_akhir(self):
        for line in self:
            line.saldo_akhir = line.saldo_awal + line.upah_kotor - line.total_dibayar

    def write(self, vals):
        if any(line.periode_id.state == 'ditutup' for line in self):
            raise UserError(
                'Baris upah pada periode yang sudah ditutup tidak bisa diubah. '
                'Buka kembali periode terlebih dahulu.'
            )
        return super().write(vals)

    def unlink(self):
        if any(line.periode_id.state == 'ditutup' for line in self):
            raise UserError(
                'Baris upah pada periode yang sudah ditutup tidak bisa dihapus.'
            )
        return super().unlink()
