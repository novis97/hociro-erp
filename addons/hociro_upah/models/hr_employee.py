from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    # Field upah lain di spec §3.3 (x_gaji_pokok, x_tarif_harian,
    # x_tarif_disiplin, x_tarif_transpor, x_batas_jam_disiplin) belum
    # diimplementasikan di sini.
    x_tipe_pekerja = fields.Selection(
        [('staf', 'Staf'), ('tukang', 'Tukang')],
        string='Tipe Pekerja',
    )
    # hr.employee tidak punya currency_id bawaan; dibutuhkan agar field
    # Monetary di bawah bisa di-setup oleh registry.
    currency_id = fields.Many2one(
        'res.currency',
        related='company_id.currency_id',
        string='Mata Uang',
    )
    x_upah_harian = fields.Monetary(
        string='Upah Harian',
        help='Berlaku untuk tukang.',
    )
    x_tarif_lembur = fields.Monetary(
        string='Tarif Lembur',
        help='Flat per hari. Berlaku untuk tukang & staf.',
    )
