# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Base Payment API',
    'version': '1.0',
    'category': 'Accounting/Payment',
    'summary': 'Base module for payment integrations',
    'description': """
        Base module that provides common functionality for payment integrations.
    """,
    'depends': ['base', 'account'],
    'data': [
        'views/account_journal_views.xml',
        'views/res_partner_views.xml',
        'views/account_move_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
} 