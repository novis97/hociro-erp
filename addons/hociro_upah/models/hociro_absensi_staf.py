from odoo import api, fields, models


class HociroAbsensiStaf(models.Model):
    _name = 'hociro.absensi.staf'
    _description = 'Absensi Harian Staf Studio'
    _order = 'tanggal desc, employee_id'

    tanggal = fields.Date(required=True, default=fields.Date.context_today)
    employee_id = fields.Many2one(
        'hr.employee', string='Staf', required=True,
        domain=[('x_tipe_pekerja', '=', 'staf')],
    )
    status = fields.Selection([
        ('hadir', 'Hadir'),
        ('sakit', 'Sakit'),
        ('izin', 'Izin'),
        ('cuti', 'Cuti'),
        ('alfa', 'Alfa'),
    ], required=True, default='hadir')
    jam_masuk = fields.Float(
        string='Jam Masuk',
        help='Diisi dari timestamp Google Form. Format: 8.5 = 08:30',
    )
    dapat_disiplin = fields.Boolean(
        compute='_compute_dapat_disiplin',
        store=True,
        string='Dapat Disiplin',
    )
    url_foto = fields.Char(
        string='Foto Kehadiran',
        help='Link Google Drive dari upload form absensi. Klik untuk buka foto.',
    )
    catatan = fields.Char()

    _tanggal_employee_uniq = models.Constraint(
        'unique(tanggal, employee_id)',
        'Sudah ada absensi untuk staf ini pada tanggal yang sama.',
    )

    @api.depends('status', 'jam_masuk', 'employee_id.x_batas_jam_disiplin')
    def _compute_dapat_disiplin(self):
        for rec in self:
            if rec.status != 'hadir':
                rec.dapat_disiplin = False
            else:
                batas = rec.employee_id.x_batas_jam_disiplin or 8.5
                rec.dapat_disiplin = (rec.jam_masuk > 0 and rec.jam_masuk <= batas)
