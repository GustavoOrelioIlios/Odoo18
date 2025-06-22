# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Base Payment Itaú',
    'version': '1.0.0',
    'category': 'Technical Settings',
    'website': 'https://iliossistemas.com.br',
    'summary': 'Integração específica do Banco Itaú para pagamentos',
    'description': """
        Módulo específico para integração com API do Banco Itaú.
        
        Funcionalidades Itaú:
        * Geração de token OAuth2
        * Emissão de boletos
        * Consulta de boletos
        * Testes de API específicos do Itaú
        
        Endpoints implementados:
        * POST: Criação de boletos
        * GET: Consulta de boletos
        * OAuth: Autenticação via token
        
        Este módulo herda e estende o módulo base_payment_api.
    """,
    'depends': [
        'base_payment_api',
    ],
    'external_dependencies': {
        'python': ['requests'],
    },
    'data': [
        'security/ir.model.access.csv',
        # 'data/migration_data.xml',
        'views/base_payment_itau_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'Other proprietary',
} 