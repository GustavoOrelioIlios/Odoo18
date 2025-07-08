# -*- coding: utf-8 -*-

from odoo import models, fields

class MoveBoletoSicoob(models.Model):
    _inherit = 'move.boleto'
    _description = 'Registro de Boleto Bancário - Sicoob'

    # --- Campos Específicos do Sicoob ---

    # sicoob_company_boleto_id = fields.Char(
    #     string='ID do Boleto na Empresa (Sicoob)',
    #     copy=False,
    #     size=25,
    #     readonly=True,
    #     help="Campo para uso da empresa do beneficiário para identificação do boleto no Sicoob. Tamanho máximo 25 caracteres."
    # )

    sicoob_api_boleto_id = fields.Char(
        string='ID do Boleto no Sicoob',
        copy=False,
        index=True,
        readonly=True,
        help="ID único retornado pela API do Sicoob ou um UUID local para referência, similar ao ID Itaú."
    ) 