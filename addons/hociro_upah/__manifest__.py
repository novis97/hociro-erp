{
    'name': 'Hociro — Upah Harian',
    'version': '19.0.1.0.0',
    'category': 'Human Resources',
    'summary': 'Absensi dan upah tukang, kuli, dan staf Hociro/Hananikasha',
    'license': 'LGPL-3',
    'depends': ['hr', 'analytic'],
    'data': [
        'security/ir.model.access.csv',
        'views/hociro_absensi_tukang_views.xml',
    ],
    'installable': True,
    'application': False,
}
