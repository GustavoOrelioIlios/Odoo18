{
    'name': 'Parking Register Box',
    'version': '1.0',
    'summary': 'Gestão de caixas para estacionamento',
    'description': 'Módulo para controle de abertura, sangria, suprimento, estorno e fechamento de caixas.',
    'author': 'Ilios Sistemas',
    'category': 'Parking',
    'depends': ['base', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'views/parking_registerbox_wizard_views.xml',
        'views/parking_registerbox_views.xml',
        'views/parking_registerbox_line_views.xml',
        'views/parking_payment_form_views.xml',
        'views/parking_cost_views.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
} 