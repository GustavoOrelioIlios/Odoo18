# -*- coding: utf-8 -*-
{
    'name': 'Integração de Pagamentos Sicoob',
    'version': '1.0.0',
    'category': 'Accounting/Payment',
    'summary': 'Integração com o sistema de pagamentos Sicoob',
    'description': '''
        Módulo para integração com o sistema de pagamentos Sicoob.
        
        Funcionalidades:
        - Gerenciamento de números de cliente Sicoob
        - Códigos de modalidade para cobrança
        - Números de contrato para faturas
        - Integração com API do Sicoob
        - Validação de dados via Pydantic
        - Emissão de boletos bancários
    ''',
    'author': 'Seu Nome',
    'website': 'https://www.seusite.com.br',
    'depends': [
        'base_payment_api',
        'contacts',
        'account',
    ],
    'external_dependencies': {
        'python': ['pydantic', 'requests'],
    },
    'data': [
        'security/ir.model.access.csv',
        'views/res_partner_bank_views.xml',
        'views/res_partner_views.xml',
        'views/account_journal_views.xml',
        'views/account_move_views.xml',
        'views/base_payment_sicoob_views.xml',
        'views/res_company_views.xml',
        'views/move_boleto_views.xml',
        'data/ir_sequence_data.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
} 