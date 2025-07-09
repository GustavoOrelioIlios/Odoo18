# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Base Payment API',
    'version': '1.0.0',
    'category': 'Technical Settings',
    'website': 'https://iliossistemas.com.br',
    'summary': 'Módulo base para integrações de pagamento via API',
    'description': """
        Módulo base para configurar integrações de pagamento com diferentes bancos e APIs.
        
        Configurações Genéricas:
        * Configurações de conexão API
        * Gestão de ambientes (Sandbox/Produção)
        * Parâmetros de autenticação
        * Vinculação com bancos (res.bank)
        * Sistema de testes de conexão
        
        Funcionalidades:
        * Teste de token de autenticação
        * Interface padronizada para integrações
        * Logs e monitoramento de conexões
    """,
    'depends': [
        'base',
        'mail',
        'account',
        'contacts',
    ],
    'external_dependencies': {
        'python': ['requests'],
    },
    'data': [
        'security/ir.model.access.csv',
        'views/base_payment_api_views.xml',
        'views/payment_test_result_wizard_views.xml',
        'views/res_partner_views.xml',
        'views/account_journal_views.xml',
        'views/move_boleto_views.xml',
        'views/account_move_views.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'Other proprietary',
} 