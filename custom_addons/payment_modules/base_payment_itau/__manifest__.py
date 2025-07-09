# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Base Payment Itau',
    'version': '1.0',
    'category': 'Accounting/Payment',
    'summary': 'Integration with Itau payment system',
    'description': """
        Module for integration with Itau payment system.
        Provides functionality for generating and managing Itau bank slips.
    """,
    'depends': ['base_payment_api'],
    'data': [
        'views/account_journal_views.xml',
        'views/res_partner_views.xml',
        'views/account_move_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
} 