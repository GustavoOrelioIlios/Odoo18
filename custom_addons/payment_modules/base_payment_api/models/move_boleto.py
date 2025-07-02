# -*- coding: utf-8 -*-

from odoo import models, fields, api
import uuid

class MoveBoleto(models.Model):
    _name = 'move.boleto'
    _description = 'Registro de Boleto Bancário'

    # Relacionamento com a Fatura
    invoice_id = fields.Many2one(
        'account.move',
        string='Fatura',
        required=True,
        ondelete='cascade'
    )

    # Código de Barras e Linha Digitável
    l10n_br_is_barcode = fields.Char(
        string='Código de Barras',
        copy=False
    )
    l10n_br_is_barcode_formatted = fields.Char(
        string='Linha Digitável',
        copy=False
    )

    # Nosso Número
    l10n_br_is_own_number = fields.Char(
        string='Nosso Número',
        copy=False,
        readonly=True,
        help="Nosso Número do boleto."
    )

    # Datas
    data_emissao = fields.Date(
        string='Data de Emissão do Boleto',
        default=fields.Date.context_today
    )
    data_limite_pagamento = fields.Date(
        string='Data Limite para Pagamento'
    ) 