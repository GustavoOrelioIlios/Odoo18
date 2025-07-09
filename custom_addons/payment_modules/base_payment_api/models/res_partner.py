# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # === CAMPOS DE JUROS ===
    payment_interest_code = fields.Selection(
        selection=[],
        string='Código de Juros',
        help='Código do tipo de juros aplicado após o vencimento'
    )
    
    payment_interest_percent = fields.Float(
        string='Percentual de Juros',
        digits='Account',
        help='Percentual de juros aplicado (quando aplicável)'
    )
    
    payment_interest_value = fields.Float(
        string='Valor Fixo de Juros',
        digits='Account',
        help='Valor fixo de juros aplicado (quando aplicável)'
    )
    
    payment_interest_date_start = fields.Integer(
        string='Dias para Início dos Juros',
        default=1,
        help='Número de dias após o vencimento para iniciar a cobrança de juros'
    )

    # === CAMPOS DE MULTA ===
    payment_penalty_code = fields.Selection(
        selection=[],
        string='Código de Multa',
        help='Código do tipo de multa aplicado após o vencimento'
    )
    
    payment_penalty_percent = fields.Float(
        string='Percentual de Multa',
        digits='Account',
        help='Percentual de multa aplicado (quando aplicável)'
    )
    
    payment_penalty_value = fields.Float(
        string='Valor Fixo de Multa',
        digits='Account',
        help='Valor fixo de multa aplicado (quando aplicável)'
    )
    
    payment_penalty_date_start = fields.Integer(
        string='Dias para Início da Multa',
        default=1,
        help='Número de dias após o vencimento para iniciar a cobrança da multa'
    )

    @api.onchange('payment_interest_code')
    def _onchange_payment_interest_code(self):
        """Limpa campos relacionados quando o código de juros é alterado"""
        if self.payment_interest_code:
            # Reset dos valores para permitir reconfiguração
            self.payment_interest_percent = 0.0
            self.payment_interest_value = 0.0

    @api.onchange('payment_penalty_code')
    def _onchange_payment_penalty_code(self):
        """Limpa campos relacionados quando o código de multa é alterado"""
        if self.payment_penalty_code:
            # Reset dos valores para permitir reconfiguração
            self.payment_penalty_percent = 0.0
            self.payment_penalty_value = 0.0 