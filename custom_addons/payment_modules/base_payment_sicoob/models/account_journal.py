# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    sicoob_modality_code = fields.Selection([
        ('1', 'SIMPLES COM REGISTRO')
    ], string='Código da Modalidade (Sicoob)',
        help='Código da modalidade de cobrança no Sicoob',
        copy=False
    )

    sicoob_especie_documento = fields.Selection([
        ('CH', 'Cheque'),
        ('DM', 'Duplicata Mercantil'),
        ('DMI', 'Duplicata Mercantil p/ Indicação'),
        ('DS', 'Duplicata de Serviço'),
        ('DSI', 'Duplicata de Serviço p/ Indicação'),
        ('DR', 'Duplicata Rural'),
        ('LC', 'Letra de Câmbio'),
        ('NCC', 'Nota de Crédito Comercial'),
        ('NCE', 'Nota de Crédito a Exportação'),
        ('NCI', 'Nota de Crédito Industrial'),
        ('NCR', 'Nota de Crédito Rural'),
        ('NP', 'Nota Promissória'),
        ('NPR', 'Nota Promissória Rural'),
        ('TM', 'Triplicata Mercantil'),
        ('TS', 'Triplicata de Serviço'),
        ('NS', 'Nota de Seguro'),
        ('RC', 'Recibo'),
        ('FAT', 'Fatura'),
        ('ND', 'Nota de Débito'),
        ('AP', 'Apólice de Seguro'),
        ('ME', 'Mensalidade Escolar'),
        ('PC', 'Parcela de Consórcio'),
        ('NF', 'Nota Fiscal'),
        ('DD', 'Documento de Dívida'),
        ('CPR', 'Cédula de Produto Rural'),
        ('WR', 'Warrant'),
        ('DAE', 'Dívida Ativa de Estado'),
        ('DAM', 'Dívida Ativa de Município'),
        ('DAU', 'Dívida Ativa da União'),
        ('EC', 'Encargos Condominiais'),
        ('CPS', 'Conta de Prestação de Serviços'),
        ('OUT', 'Outros')
    ], string='Espécie do Documento (Sicoob)',
        help='Espécie do documento para boletos Sicoob',
        copy=False,
        required=True
    )

    @api.onchange('sicoob_especie_documento')
    def _onchange_sicoob_especie_documento(self):
        """Log para debug do valor do campo"""
        _logger = logging.getLogger(__name__)
        _logger.info("[Sicoob] Valor do campo sicoob_especie_documento alterado para: %s", self.sicoob_especie_documento) 