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
    # currency_id sudah disediakan oleh hr.employee core (addons/hr,
    # related company_id.currency_id) sejak employee/contract dilebur di v19
    # — jangan didefinisikan ulang di sini. currency_field diisi eksplisit
    # karena Monetary tidak menulis balik hasil auto-deteksinya ke
    # ir.model.fields (lihat addons/hr_hourly_cost/models/hr_employee.py
    # untuk pola yang sama di core Odoo).
    x_upah_harian = fields.Monetary(
        string='Upah Harian',
        currency_field='currency_id',
        help='Berlaku untuk tukang.',
    )
    x_tarif_lembur = fields.Monetary(
        string='Tarif Lembur',
        currency_field='currency_id',
        help='Flat per hari. Berlaku untuk tukang & staf.',
    )
