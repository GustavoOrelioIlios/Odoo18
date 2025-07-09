# -*- coding: utf-8 -*-

from odoo import models, fields


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # === EXTENSÃO DOS CAMPOS GENÉRICOS COM VALORES ESPECÍFICOS DO ITAÚ ===
    payment_interest_code = fields.Selection(
        selection_add=[
            ('90', 'Percentual Mensal'),
            ('91', 'Percentual Diário'),
            ('92', 'Percentual Anual'),
            ('93', 'Valor Diário'),
            ('05', 'Isento'),
        ],
        ondelete={
            '90': 'cascade',
            '91': 'cascade',
            '92': 'cascade',
            '93': 'cascade',
            '05': 'cascade',
        }
    )
    
    payment_penalty_code = fields.Selection(
        selection_add=[
            ('01', 'Valor Fixo'),
            ('02', 'Percentual'),
            ('03', 'Isento'),
        ],
        ondelete={
            '01': 'cascade',
            '02': 'cascade',
            '03': 'cascade',
        }
    ) 