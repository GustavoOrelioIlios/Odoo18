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

    # ID único do Boleto no Itaú
    itau_boleto_id = fields.Char(
        string='ID do Boleto no Itaú',
        copy=False,
        default=lambda self: str(uuid.uuid4()),
        index=True,
        readonly=True,
        help="ID único do boleto gerado pela API do Itaú ou um hash local."
    )

    # Código de Barras e Linha Digitável
    l10n_br_is_barcode = fields.Char(
        string='Código de Barras',
        copy=False
    )
    # NOVO CAMPO
    l10n_br_is_barcode_formatted = fields.Char(
        string='Linha Digitável',
        copy=False
    )

    # Datas
    data_emissao = fields.Date(
        string='Data de Emissão do Boleto',
        default=fields.Date.context_today
    )
    # NOVO CAMPO
    data_limite_pagamento = fields.Date(
        string='Data Limite para Pagamento'
    ) 