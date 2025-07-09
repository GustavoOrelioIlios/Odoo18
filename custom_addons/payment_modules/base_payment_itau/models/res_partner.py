# -*- coding: utf-8 -*-

from odoo import models, fields


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # === CAMPOS ESPECÍFICOS DO ITAÚ ===
    itau_interest_code = fields.Selection([
        ('90', 'Percentual Mensal'),
        ('91', 'Percentual Diário'),
        ('92', 'Percentual Anual'),
        ('93', 'Valor Diário'),
        ('05', 'Isento'),
    ], string='Código de Juros (Itaú)',
       help='Código do tipo de juros aplicado após o vencimento')
    
    itau_interest_percent = fields.Float(
        string='Percentual de Juros (Itaú)',
        digits='Account',
        help='Percentual de juros aplicado (quando aplicável)'
    )
    
    itau_interest_value = fields.Float(
        string='Valor Fixo de Juros (Itaú)',
        digits='Account',
        help='Valor fixo de juros aplicado (quando aplicável)'
    )
    
    itau_interest_date_start = fields.Integer(
        string='Dias para Início dos Juros (Itaú)',
        default=1,
        help='Número de dias após o vencimento para iniciar a cobrança de juros'
    )

    # === CAMPOS DE MULTA ===
    itau_penalty_code = fields.Selection([
        ('01', 'Valor Fixo'),
        ('02', 'Percentual'),
        ('03', 'Isento'),
    ], string='Código de Multa (Itaú)',
       help='Código do tipo de multa aplicado após o vencimento')
    
    itau_penalty_percent = fields.Float(
        string='Percentual de Multa (Itaú)',
        digits='Account',
        help='Percentual de multa aplicado (quando aplicável)'
    )
    
    itau_penalty_value = fields.Float(
        string='Valor Fixo de Multa (Itaú)',
        digits='Account',
        help='Valor fixo de multa aplicado (quando aplicável)'
    )
    
    itau_penalty_date_start = fields.Integer(
        string='Dias para Início da Multa (Itaú)',
        default=1,
        help='Número de dias após o vencimento para iniciar a cobrança da multa'
    ) 