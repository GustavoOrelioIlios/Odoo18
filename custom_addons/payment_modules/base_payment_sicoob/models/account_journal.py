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

    # === CAMPOS DE JUROS SICOOB ===
    sicoob_interest_code = fields.Selection([
        ('1', 'Valor por dia'),
        ('2', 'Taxa Mensal'),
        ('3', 'Isento'),
    ], string='Código de Juros',
        help='Código do tipo de juros aplicado após o vencimento'
    )
    
    sicoob_interest_percent = fields.Float(
        string='Percentual de Juros',
        digits='Account',
        help='Percentual de juros aplicado (quando aplicável)'
    )
    
    sicoob_interest_value = fields.Float(
        string='Valor Fixo de Juros',
        digits='Account',
        help='Valor fixo de juros aplicado (quando aplicável)'
    )
    
    sicoob_interest_date_start = fields.Integer(
        string='Dias para Início dos Juros',
        default=1,
        help='Número de dias após o vencimento para iniciar a cobrança de juros'
    )

    # === CAMPOS DE MULTA SICOOB ===
    sicoob_penalty_code = fields.Selection([
        ('1', 'Valor Fixo'),
        ('2', 'Percentual'),
        ('0', 'Isento'),
    ], string='Código de Multa',
        help='Código do tipo de multa aplicado após o vencimento'
    )
    
    sicoob_penalty_percent = fields.Float(
        string='Percentual de Multa',
        digits='Account',
        help='Percentual de multa aplicado (quando aplicável)'
    )
    
    sicoob_penalty_value = fields.Float(
        string='Valor Fixo de Multa',
        digits='Account',
        help='Valor fixo de multa aplicado (quando aplicável)'
    )
    
    sicoob_penalty_date_start = fields.Integer(
        string='Dias para Início da Multa',
        default=1,
        help='Número de dias após o vencimento para iniciar a cobrança da multa'
    )

    # Novos campos
    narration = fields.Text(
        string='Mensagens de Instrução',
        help='Mensagens de instrução para o boleto Sicoob'
    )

    sicoob_emission_type = fields.Selection([
        ('1', 'Banco Emite'),
        ('2', 'Cliente Emite')
    ], string='Quem emite o boleto',
        help='Código de identificação de emissão do boleto',
        default='2',
        copy=False
    )

    sicoob_distribution_type = fields.Selection([
        ('1', 'Banco Distribui'),
        ('2', 'Cliente Distribui')
    ], string='Quem distribui o boleto',
        help='Código de identificação de distribuição do boleto',
        default='2',
        copy=False
    )

    sicoob_generate_pdf = fields.Boolean(
        string='Gerar PDF na API',
        help='Define se o PDF do boleto deve ser gerado pela API do Sicoob',
        default=False
    )

    sicoob_generate_pix = fields.Boolean(
        string='Gerar PIX no boleto',
        help='Define se deve ser gerado um código PIX junto ao boleto',
        default=False
    )

    @api.onchange('sicoob_especie_documento')
    def _onchange_sicoob_especie_documento(self):
        """Log para debug do valor do campo"""
        _logger = logging.getLogger(__name__)
        _logger.info("[Sicoob] Valor do campo sicoob_especie_documento alterado para: %s", self.sicoob_especie_documento)

    @api.onchange('sicoob_interest_code')
    def _onchange_sicoob_interest_code(self):
        """Limpa campos relacionados quando o código de juros é alterado"""
        if self.sicoob_interest_code:
            self.sicoob_interest_percent = 0.0
            self.sicoob_interest_value = 0.0

    @api.onchange('sicoob_penalty_code')
    def _onchange_sicoob_penalty_code(self):
        """Limpa campos relacionados quando o código de multa é alterado"""
        if self.sicoob_penalty_code:
            self.sicoob_penalty_percent = 0.0
            self.sicoob_penalty_value = 0.0 