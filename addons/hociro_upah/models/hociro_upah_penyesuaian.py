from odoo import api, fields, models


class HociroUpahPenyesuaian(models.Model):
    # PROTOTIPE — dibuat untuk menjawab satu pertanyaan: apakah line_id tetap
    # menunjuk ke baris yang benar setelah action_hitung_upah() unlink+create
    # ulang seluruh hociro.upah.line. Bukan implementasi issue #4 yang lengkap
    # (tidak ada jenis/keterangan, tidak ada guard periode ditutup, tidak ada view).
    _name = 'hociro.upah.penyesuaian'
    _description = 'PROTOTIPE — Penyesuaian Upah (uji mekanisme line_id)'

    periode_id = fields.Many2one('hociro.periode.upah', string='Periode', required=True)
    employee_id = fields.Many2one('hr.employee', string='Karyawan', required=True)
    nilai = fields.Float(string='Nilai')
    line_id = fields.Many2one(
        'hociro.upah.line', string='Baris Upah',
        compute='_compute_line_id', store=True,
    )

    # depends hanya periode_id/employee_id — sama seperti desain issue #4.
    # Ini SENGAJA tidak bisa menangkap "line lama dihapus, line baru dibuat"
    # karena periode_id/employee_id tidak berubah saat itu terjadi. Itulah
    # yang diuji lewat pemanggilan recompute eksplisit di action_hitung_upah().
    @api.depends('periode_id', 'employee_id')
    def _compute_line_id(self):
        for rec in self:
            if not rec.periode_id or not rec.employee_id:
                rec.line_id = False
                continue
            rec.line_id = self.env['hociro.upah.line'].search([
                ('periode_id', '=', rec.periode_id.id),
                ('employee_id', '=', rec.employee_id.id),
            ], limit=1)
