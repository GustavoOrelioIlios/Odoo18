# -*- coding: utf-8 -*-
{
    'name': 'Base Payment Sicoob',
    'version': '1.0',
    'category': 'Accounting/Payment',
    'summary': 'Integration with Sicoob payment system',
    'description': """
        Module for integration with Sicoob payment system.
        Provides functionality for generating and managing Sicoob bank slips.
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