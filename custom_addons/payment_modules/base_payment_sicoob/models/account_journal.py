# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    sicoob_modality_code = fields.Selection([
        ('1', 'SIMPLES COM REGISTRO')
    ], string='Código da Modalidade de Cobrança (Sicoob)',
        default='1',
        help='Código que identifica a modalidade de cobrança no Sicoob'
    ) 