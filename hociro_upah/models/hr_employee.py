from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    # Hanya field yang dibutuhkan sebagai domain oleh hociro.absensi.tukang
    # (spec §3.4). Field upah lain di spec §3.3 belum diimplementasikan di sini.
    x_tipe_pekerja = fields.Selection(
        [('staf', 'Staf'), ('tukang', 'Tukang')],
        string='Tipe Pekerja',
    )
