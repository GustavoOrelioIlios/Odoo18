# -*- coding: utf-8 -*-

from odoo import models, fields, api

class AccountJournal(models.Model):
    _inherit = 'account.journal'

    # NOVO CAMPO
    itau_wallet_code = fields.Char(
        string='Código da Carteira de Cobrança (Itaú)',
        help='Código da Carteira de Cobrança fornecido pelo Itaú.'
    )

    # NOVO CAMPO com códigos ajustados
    l10n_br_is_payment_mode_id = fields.Selection(
        selection=[
            ('01', 'DM - Duplicata Mercantil'),
            ('02', 'NP - Nota Promissória'),
            ('03', 'NS - Nota de Seguro'),
            ('04', 'ME - Mensalidade Escolar'),
            ('05', 'RC - Recibo'),
            ('06', 'CT - Contrato'),
            ('07', 'Cosseguros'),
            ('08', 'DS - Duplicata de Serviço'),
            ('09', 'LC - Letra de Câmbio'),
            ('13', 'Nota de débitos'),
            ('14', 'CBI - Cédula de crédito Bancário por Indicação'),
            ('15', 'DD - Documento de Dívida'),
            ('16', 'EC - Encargos condominiais'),
            ('17', 'FS - Prestação de Serviços'),
            ('18', 'BDP - Boleto proposta'),
            ('33', 'BOLETO APORTE'),
            ('88', 'CBI - Cédula de crédito Bancário por Indicação'),
            ('89', 'CC - Contrato de Câmbio'),
            ('90', 'CCB - Cédula de Crédito Bancário'),
            ('91', 'CD - Confissão de Dívida'),
            ('92', 'CH - Cheque'),
            ('93', 'CM - Contrato de Mútuo'),
            ('94', 'CPS - Conta de Prestação de Serv.'),
            ('95', 'DMI - Duplicata de venda Mercantil por Indicação'),
            ('96', 'DSI - Duplicata de prestação de Serviços por Indicação'),
            ('97', 'RA - Recibo de Aluguel'),
            ('98', 'TA - Termo de Acordo'),
            ('99', 'DV - Diversos'),
        ],
        string='Código da Espécie do Título (Itaú)'
    )

    # NOVO CAMPO
    l10n_br_is_payment_mode_description = fields.Char(
        string='Descrição da Espécie',
        compute='_compute_payment_mode_description',
        store=True
    )

    @api.depends('l10n_br_is_payment_mode_id')
    def _compute_payment_mode_description(self):
        for journal in self:
            if journal.l10n_br_is_payment_mode_id:
                journal.l10n_br_is_payment_mode_description = dict(
                    journal._fields['l10n_br_is_payment_mode_id'].selection
                ).get(journal.l10n_br_is_payment_mode_id)
            else:
                journal.l10n_br_is_payment_mode_description = False 