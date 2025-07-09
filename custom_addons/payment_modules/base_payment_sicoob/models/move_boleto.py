# -*- coding: utf-8 -*-

from odoo import models, fields

class MoveBoletoSicoob(models.Model):
    _inherit = 'move.boleto'
    _description = 'Registro de Boleto Bancário - Sicoob'

    sicoob_api_boleto_id = fields.Char(
        string='ID do Boleto no Sicoob',
        copy=False,
        index=True,
        readonly=True,
        help="ID único retornado pela API do Sicoob ou um UUID local para referência, similar ao ID Itaú."
    ) 