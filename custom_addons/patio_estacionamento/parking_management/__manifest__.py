# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name' : 'Gestão de Pátio',
    'version' : '0.1',
    'category': 'ILIOSSISTEMAS/CUSTOMIZAÇÃO',
    'website' : 'https://iliossistemas.com.br',
    'summary' : 'Modulo customizado para gestão de pátios grupo G10 Transportes',
    'description' : """
         Registro dos agendamentos, entradas e saídas dos veículos no Pátio.
    """,
    'depends': [
        'base',
        'mail',
        'camera_management',
        'parking_registerbox',
    ],
    'data': [
        'security/parking_security.xml',
        'security/ir.model.access.csv',
        'wizards/parking_payment_wizard_views.xml',
        'views/parking_booking_views.xml',
        'views/parking_queue_views.xml',
        'views/parking_slots_views.xml',
        'views/parking_views.xml',
        # 'views/templates.xml',
    ],

    'installable': True,
    'application': True,
    'assets': {
        'web.assets_frontend': [
            'parking_management/static/src/portal_component/**/*',
        ],
    },
    'license': 'Other proprietary',
}
