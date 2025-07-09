# -*- coding: utf-8 -*-

from odoo import models, fields

class MoveBoleto(models.Model):
    _name = 'move.boleto'
    _description = 'Registro de Boleto Bancário Genérico'
    _order = 'invoice_id, data_emissao desc'

    invoice_id = fields.Many2one(
        'account.move',
        string='Fatura',
        required=True,
        ondelete='cascade',
        index=True,
        help="Fatura de origem à qual este boleto está vinculado."
    )

    bank_type = fields.Selection([
        ('itau', 'Itaú'),
        ('sicoob', 'Sicoob')
    ], string='Banco',
        required=True,
        readonly=True,
        help="Identifica o banco ao qual este boleto pertence"
    )

    data_emissao = fields.Date(
        string='Data de Emissão',
        related='invoice_id.invoice_date',
        store=True,
        readonly=True,
        help="Data de emissão da fatura, usada como data de emissão do boleto."
    )
    data_limite_pagamento = fields.Date(
        string='Data Limite para Pagamento',
        related='invoice_id.invoice_date_due',
        store=True,
        readonly=True,
        help="Data de vencimento da fatura, usada como data limite para pagamento."
    )
    l10n_br_is_own_number = fields.Char(
        string='Nosso Número',
        copy=False,
        readonly=True,
        help="Nosso Número, o identificador único do boleto no banco."
    )
    l10n_br_is_barcode = fields.Char(
        string='Código de Barras',
        copy=False,
        readonly=True
    )
    l10n_br_is_barcode_formatted = fields.Char(
        string='Linha Digitável',
        copy=False,
        readonly=True
    )
    
    sicoob_nosso_numero = fields.Char(
        string='Nosso Número (Sicoob)',
        copy=False,
        readonly=True,
        help="Número sequencial gerado para identificação do boleto no Sicoob."
    ) 