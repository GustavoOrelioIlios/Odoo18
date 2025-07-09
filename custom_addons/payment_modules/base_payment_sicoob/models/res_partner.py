# -*- coding: utf-8 -*-

from odoo import models, fields


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # === EXTENSÃO DOS CAMPOS GENÉRICOS COM VALORES ESPECÍFICOS DO SICOOB ===
    payment_interest_code = fields.Selection(
        selection_add=[
            ('1', 'Valor por dia'),
            ('2', 'Taxa Mensal'),
            ('3', 'Isento'),
        ],
        ondelete={
            '1': 'cascade',
            '2': 'cascade',
            '3': 'cascade',
        }
    )
    
    payment_penalty_code = fields.Selection(
        selection_add=[
            ('1', 'Valor Fixo'),
            ('2', 'Percentual'),
            ('0', 'Isento'),
        ],
        ondelete={
            '1': 'cascade',
            '2': 'cascade',
            '0': 'cascade',
        }
    ) 