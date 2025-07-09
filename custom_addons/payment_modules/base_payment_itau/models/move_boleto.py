# -*- coding: utf-8 -*-

from odoo import models, fields, api
import uuid

class MoveBoletoItau(models.Model):
    _inherit = 'move.boleto'
    _description = 'Registro de Boleto Bancário - Itaú'

    invoice_id = fields.Many2one(
        'account.move',
        string='Fatura',
        required=True,
        ondelete='cascade'
    )

    itau_boleto_id = fields.Char(
        string='ID do Boleto no Itaú',
        copy=False,
        default=lambda self: str(uuid.uuid4()),
        index=True,
        readonly=True,
        help="ID único retornado pela API do Itaú ou um hash local para referência."
    )

    l10n_br_is_barcode = fields.Char(
        string='Código de Barras',
        copy=False
    )
    l10n_br_is_barcode_formatted = fields.Char(
        string='Linha Digitável',
        copy=False
    )

    data_emissao = fields.Date(
        string='Data de Emissão do Boleto',
        default=fields.Date.context_today
    )
    data_limite_pagamento = fields.Date(
        string='Data Limite para Pagamento'
    ) 