# -*- coding: utf-8 -*-

from odoo import models, fields


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # === CAMPOS ESPECÍFICOS DO SICOOB ===
    sicoob_interest_code = fields.Selection([
        ('1', 'Valor por dia'),
        ('2', 'Taxa Mensal'),
        ('3', 'Isento'),
    ], string='Código de Juros (Sicoob)',
       help='Código do tipo de juros aplicado após o vencimento')
    
    sicoob_interest_percent = fields.Float(
        string='Percentual de Juros (Sicoob)',
        digits='Account',
        help='Percentual de juros aplicado (quando aplicável)'
    )
    
    sicoob_interest_value = fields.Float(
        string='Valor Fixo de Juros (Sicoob)',
        digits='Account',
        help='Valor fixo de juros aplicado (quando aplicável)'
    )
    
    sicoob_interest_date_start = fields.Integer(
        string='Dias para Início dos Juros (Sicoob)',
        default=1,
        help='Número de dias após o vencimento para iniciar a cobrança de juros'
    )

    # === CAMPOS DE MULTA ===
    sicoob_penalty_code = fields.Selection([
        ('1', 'Valor Fixo'),
        ('2', 'Percentual'),
        ('0', 'Isento'),
    ], string='Código de Multa (Sicoob)',
       help='Código do tipo de multa aplicado após o vencimento')
    
    sicoob_penalty_percent = fields.Float(
        string='Percentual de Multa (Sicoob)',
        digits='Account',
        help='Percentual de multa aplicado (quando aplicável)'
    )
    
    sicoob_penalty_value = fields.Float(
        string='Valor Fixo de Multa (Sicoob)',
        digits='Account',
        help='Valor fixo de multa aplicado (quando aplicável)'
    )
    
    sicoob_penalty_date_start = fields.Integer(
        string='Dias para Início da Multa (Sicoob)',
        default=1,
        help='Número de dias após o vencimento para iniciar a cobrança da multa'
    ) 