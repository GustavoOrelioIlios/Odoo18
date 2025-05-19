{
    'name': 'Gestão de Câmeras',
    'version': '1.0',
    'category': 'Tools',
    "license": 'OEEL-1',
    'summary': 'Cadastro e gerenciamento de câmeras de segurança',
    'author': 'Ilios Sistemas',
    'depends': ['base','mail'],
    'data': [
        'security/ir.model.access.csv',
        'views/camera_views.xml',
    ],
    'installable': True,
    'application': True,
}
