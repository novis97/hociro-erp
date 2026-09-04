from odoo import api, fields, models
from odoo.exceptions import UserError

SESI_SELECTION = [
    ('0', '0'),
    ('0.5', '0.5'),
    ('1', '1'),
]

FIELD_TERKUNCI_SAAT_DIKUATKAN = {
    'tanggal', 'employee_id', 'proyek_id', 'sesi_pagi', 'sesi_siang', 'lembur',
}


class HociroAbsensiTukang(models.Model):
    _name = 'hociro.absensi.tukang'
    _description = 'Absensi Harian Tukang'
    _order = 'tanggal desc, employee_id'

    tanggal = fields.Date(required=True, default=fields.Date.context_today)
    employee_id = fields.Many2one(
        'hr.employee', string='Tukang', required=True,
        domain=[('x_tipe_pekerja', '=', 'tukang')],
    )
    # Asumsi belum terverifikasi: account.analytic.account punya field
    # relasional `plan_id` -> account.analytic.plan di Odoo 19 (analytic
    # plan-based sejak v17, lihat v19-conventions.md §2.3). Verifikasi ke
    # $ODOO_SRC/addons/analytic/models/analytic_account.py sebelum install.
    proyek_id = fields.Many2one(
        'account.analytic.account', string='Proyek',
        domain=[('plan_id.name', '=', 'Project')],
    )
    sesi_pagi = fields.Selection(SESI_SELECTION, string='Pagi', default='1', required=True)
    sesi_siang = fields.Selection(SESI_SELECTION, string='Siang', default='1', required=True)
    lembur = fields.Float(string='Lembur (hari)', default=0.0)
    hari_kerja = fields.Float(string='Hari Kerja', compute='_compute_hari_kerja', store=True)
    pengawas_id = fields.Many2one(
        'res.users', string='Pengawas', default=lambda self: self.env.user,
    )
    state = fields.Selection(
        [('draft', 'Draft'), ('dikuatkan', 'Dikuatkan')],
        string='Status', default='draft', required=True,
    )
    catatan = fields.Char()

    _tanggal_employee_uniq = models.Constraint(
        'unique(tanggal, employee_id)',
        'Sudah ada absensi untuk tukang ini pada tanggal yang sama.',
    )

    @api.depends('sesi_pagi', 'sesi_siang')
    def _compute_hari_kerja(self):
        for rec in self:
            rec.hari_kerja = (float(rec.sesi_pagi) + float(rec.sesi_siang)) / 2

    def write(self, vals):
        if FIELD_TERKUNCI_SAAT_DIKUATKAN.intersection(vals) and any(
            rec.state == 'dikuatkan' for rec in self
        ):
            raise UserError(
                'Absensi yang sudah dikuatkan tidak boleh diubah. '
                'Kembalikan ke draft terlebih dahulu (tombol "Kembalikan ke Draft").'
            )
        return super().write(vals)

    def action_dikuatkan(self):
        self.write({'state': 'dikuatkan'})

    def action_draft(self):
        self.write({'state': 'draft'})

    def unlink(self):
        if any(rec.state == 'dikuatkan' for rec in self):
            raise UserError(
                'Absensi yang sudah dikuatkan tidak boleh dihapus. '
                'Kembalikan ke draft terlebih dahulu.'
            )
        return super().unlink()
