from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

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
    x_gaji_pokok = fields.Monetary(
        string='Gaji Pokok',
        currency_field='currency_id',
        help='Berlaku untuk staf. Kosong untuk staf harian murni (tanpa gaji pokok).',
    )
    x_tarif_harian = fields.Monetary(
        string='Tarif Harian',
        currency_field='currency_id',
        help='Berlaku untuk staf. Upah per hari hadir.',
    )
    x_tarif_disiplin = fields.Monetary(
        string='Tarif Disiplin',
        currency_field='currency_id',
        default=15000,
        help='Berlaku untuk staf. Default 15.000, bisa dioverride per-orang.',
    )
    x_tarif_transpor = fields.Monetary(
        string='Tarif Transpor',
        currency_field='currency_id',
        help='Berlaku untuk staf. Kosong kalau tidak ada tunjangan transpor.',
    )
    x_batas_jam_disiplin = fields.Float(
        string='Batas Jam Disiplin',
        default=8.5,
        help='Berlaku untuk staf. Batas cut-off jam masuk untuk dapat tarif disiplin. Default 08:30.',
    )
