# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import re
from datetime import date, timedelta, datetime
import logging
import uuid


class AccountMove(models.Model):
    _inherit = 'account.move'

    sicoob_contract_number = fields.Char(
        string='Número do Contrato de Cobrança (Sicoob)',
        help='Número do contrato Sicoob associado à fatura',
        compute='_compute_sicoob_contract_number',
        store=True,
    )

    sicoob_nosso_numero = fields.Char(
        string='Nosso Número (Sicoob)',
        copy=False,
        readonly=True,
        help="Número sequencial gerado para identificação do boleto no Sicoob."
    )

    sicoob_payment_limit_date = fields.Date(
        string='Data Limite para Pagamento (Sicoob)',
        help='Data limite para pagamento do boleto. Se não informada, será igual à data de vencimento',
        copy=False
    )

    sicoob_especie_documento = fields.Selection(
        related='payment_journal_id.sicoob_especie_documento',
        string='Espécie do Documento (Sicoob)',
        help='Espécie do documento para boletos Sicoob',
        readonly=True
    )

    test_json_enviado = fields.Text(
        string='JSON Enviado (Sicoob)',
        help='JSON enviado para a API do Sicoob',
        copy=False
    )

    test_json_retorno = fields.Text(
        string='JSON Retornado (Sicoob)',
        help='JSON retornado pela API do Sicoob',
        copy=False
    )

    sicoob_status = fields.Selection([
        ('pending', 'Pendente'),
        ('success', 'Sucesso'),
        ('error', 'Erro')
    ], string='Status Sicoob', copy=False)

    sicoob_date = fields.Datetime(
        string='Data Última Atualização',
        help='Data da última atualização do status Sicoob',
        copy=False
    )

    sicoob_error_message = fields.Text(
        string='Mensagem de Erro Sicoob',
        help='Última mensagem de erro retornada pela API do Sicoob',
        copy=False
    )

    payment_journal_id = fields.Many2one(
        'account.journal',
        string='Diário de Pagamento',
        compute='_compute_payment_journal_id',
        store=True,
        help='Diário associado à forma de pagamento selecionada'
    )

    boleto_ids = fields.One2many(
        'move.boleto',
        'invoice_id',
        string='Boletos Bancários (Sicoob)',
        help="Boletos bancários gerados para esta fatura via Sicoob."
    )

    @api.depends('ref')
    def _compute_sicoob_contract_number(self):
        for record in self:
            record.sicoob_contract_number = record.ref

    @api.depends('preferred_payment_method_line_id')
    def _compute_payment_journal_id(self):
        """Computa o diário baseado na forma de pagamento selecionada"""
        for record in self:
            record.payment_journal_id = record.preferred_payment_method_line_id.journal_id if record.preferred_payment_method_line_id else False

    @api.constrains('sicoob_contract_number')
    def _check_sicoob_contract_number(self):
        """Validação do número do contrato Sicoob"""
        for record in self:
            if record.sicoob_contract_number:
                clean_number = ''.join(filter(str.isdigit, record.sicoob_contract_number))
                if not clean_number:
                    raise ValidationError(_('O número do contrato Sicoob deve conter pelo menos um dígito numérico.'))
                if len(clean_number) > 20:
                    raise ValidationError(_('O número do contrato Sicoob não pode ter mais de 20 dígitos.'))

    def _get_sicoob_pagador_data_from_invoice(self):
        """
        Extrai dados do pagador (cliente da fatura) e os formata para PagadorModel do Pydantic.
        """
        self.ensure_one()
        partner = self.partner_id

        endereco_cobranca = partner
        if partner.child_ids:
            endereco_faturamento = partner.child_ids.filtered(lambda c: c.type == 'invoice')
            if endereco_faturamento:
                endereco_cobranca = endereco_faturamento[0]

        vat = re.sub(r'[^\d]', '', partner.vat or '') if partner.vat else ''
        if not vat:
            raise UserError(_('O cliente não possui CPF/CNPJ cadastrado.'))

        cep = re.sub(r'[^\d]', '', endereco_cobranca.zip or '') if endereco_cobranca.zip else ''
        if not cep:
            raise UserError(_('O cliente não possui CEP cadastrado.'))

        uf = endereco_cobranca.state_id.code if endereco_cobranca.state_id else ''
        if not uf:
            raise UserError(_('O cliente não possui UF cadastrada.'))

        endereco = endereco_cobranca.street or ''
        if endereco_cobranca.street2:
            endereco = f"{endereco}, {endereco_cobranca.street2}"

        bairro = endereco_cobranca.street2 or ''

        pagador_data = {
            'numeroCpfCnpj': vat,
            'nome': partner.name or '',
            'endereco': endereco,
            'bairro': bairro,
            'cidade': endereco_cobranca.city or '',
            'cep': cep,
            'uf': uf,
            'email': partner.email or None
        }

        return pagador_data

    def _get_sicoob_beneficiario_final_data(self):
        """
        Extrai dados do beneficiário final (empresa que está emitindo o boleto)
        e os formata para BeneficiarioFinalModel do Pydantic.
        """
        self.ensure_one()
        company = self.company_id

        vat = re.sub(r'[^\d]', '', company.vat or '') if company.vat else ''
        if not vat:
            raise UserError(_('A empresa não possui CNPJ cadastrado.'))

        beneficiario_final_data = {
            'numeroCpfCnpj': vat,
            'nome': company.name or ''
        }

        return beneficiario_final_data

    def _get_sicoob_interest_penalty_info(self):
        """
        Obtém informações de juros e multa específicas do Sicoob.
        
        Ordem de prioridade:
        1. Configurações do cliente (partner_id)
        2. Configurações do diário (payment_journal_id)
        
        Returns:
            dict: Dicionário com informações de juros e multa
        """
        self.ensure_one()
        _logger = logging.getLogger(__name__)
        
        journal = self.payment_journal_id
        _logger.info("[Sicoob] Obtendo informações de juros e multa do diário %s (id: %s)", 
                    journal.name if journal else 'N/A', 
                    journal.id if journal else 'N/A')
        
        result = {
            'interest': {
                'code': None,
                'value': 0.0,
                'percent': 0.0,
                'date_start': 0
            },
            'penalty': {
                'code': None,
                'value': 0.0,
                'percent': 0.0,
                'date_start': 0
            }
        }
        
        if self.partner_id.sicoob_interest_code:
            result['interest']['code'] = self.partner_id.sicoob_interest_code
            result['interest']['date_start'] = self.partner_id.sicoob_interest_date_start or 0
            
            if self.partner_id.sicoob_interest_code == '1':
                result['interest']['value'] = self.partner_id.sicoob_interest_value
            elif self.partner_id.sicoob_interest_code == '2':
                result['interest']['percent'] = self.partner_id.sicoob_interest_percent
        
        elif journal and journal.sicoob_interest_code:
            result['interest']['code'] = journal.sicoob_interest_code
            result['interest']['date_start'] = journal.sicoob_interest_date_start or 0
            
            if journal.sicoob_interest_code == '1':
                result['interest']['value'] = journal.sicoob_interest_value
            elif journal.sicoob_interest_code == '2':
                result['interest']['percent'] = journal.sicoob_interest_percent
        
        if self.partner_id.sicoob_penalty_code:
            result['penalty']['code'] = self.partner_id.sicoob_penalty_code
            result['penalty']['date_start'] = self.partner_id.sicoob_penalty_date_start or 0
            
            if self.partner_id.sicoob_penalty_code == '1':
                result['penalty']['value'] = self.partner_id.sicoob_penalty_value
            elif self.partner_id.sicoob_penalty_code == '2':
                result['penalty']['percent'] = self.partner_id.sicoob_penalty_percent
        
        elif journal and journal.sicoob_penalty_code:
            result['penalty']['code'] = journal.sicoob_penalty_code
            result['penalty']['date_start'] = journal.sicoob_penalty_date_start or 0
            
            if journal.sicoob_penalty_code == '1':
                result['penalty']['value'] = journal.sicoob_penalty_value
            elif journal.sicoob_penalty_code == '2':
                result['penalty']['percent'] = journal.sicoob_penalty_percent
        
        return result

    def _get_discount_info_from_payment_terms(self):
        """
        Obtém informações de desconto baseadas no termo de pagamento da fatura.
        
        Returns:
            dict: Dicionário com estrutura de desconto da API Sicoob
        """
        self.ensure_one()
        
        if not self.invoice_payment_term_id:
            return {}
        
        payment_term = self.invoice_payment_term_id
        
        if hasattr(payment_term, 'sicoob_discount_line_ids') and payment_term.sicoob_discount_line_ids:
            discount_data = payment_term.get_sicoob_discount_data(self.invoice_date)
            return discount_data
        
        else:
            payment_term_lines = payment_term.line_ids.filtered(
                lambda line: line.value == 'discount'
            ).sorted('sequence')
            
            if payment_term_lines:
                line = payment_term_lines[0]
                if line.value_amount != 0:
                    discount_date = self.invoice_date
                    if line.days > 0:
                        discount_date = self.invoice_date + timedelta(days=line.days)
                    
                    percentual_absoluto = abs(line.value_amount)
                    
                    return {
                        'tipoDesconto': '2',
                        'dataPrimeiroDesconto': discount_date.strftime('%Y-%m-%d'),
                        'valorPrimeiroDesconto': percentual_absoluto
                    }
            
            return {}

    def _get_sicoob_boleto_details_data(self):
        """
        Gera estrutura de dados para o boleto Sicoob
        
        Returns:
            dict: Estrutura de dados para API do Sicoob
        """
        self.ensure_one()
        _logger = logging.getLogger(__name__)
        
        if not self.sicoob_nosso_numero:
            nosso_numero_gerado = self.env['ir.sequence'].next_by_code('sicoob.nosso.numero')
            if not nosso_numero_gerado:
                raise UserError(_("A sequência para 'Nosso Número' (sicoob.nosso.numero) não pôde ser gerada. Verifique as configurações da sequência."))
            self.sicoob_nosso_numero = nosso_numero_gerado

        journal = self.payment_journal_id
        _logger.info("[Sicoob] Usando diário %s (id: %s) para configurações do boleto", 
                    journal.name if journal else 'N/A', 
                    journal.id if journal else 'N/A')
        
        if not journal:
            raise UserError(_('A fatura precisa ter uma forma de pagamento com diário Sicoob configurado.'))
        
        juros_multa_info = self._get_sicoob_interest_penalty_info()
        
        desconto_info = self._get_discount_info_from_payment_terms()
        
        pagador_data = self._get_sicoob_pagador_data_from_invoice()
        
        beneficiario_final_data = self._get_sicoob_beneficiario_final_data()
        
        bank_account = self.company_id.sicoob_partner_bank_id
        if not bank_account:
            raise UserError(_('Conta bancária Sicoob não configurada para a empresa.'))
        
        boleto_data = {
            'seuNumero': self.name,
            'nossoNumero': int(self.sicoob_nosso_numero) if self.sicoob_nosso_numero else 0,
            'dataEmissao': self.invoice_date.strftime('%Y-%m-%d'),
            'dataVencimento': self.invoice_date_due.strftime('%Y-%m-%d'),
            'dataLimitePagamento': (self.sicoob_payment_limit_date or self.invoice_date_due).strftime('%Y-%m-%d'),
            'valor': float(self.amount_total),
            'aceite': True,
            'codigoEspecieDocumento': journal.sicoob_especie_documento,
            'numeroCliente': int(bank_account.sicoob_client_number),
            'codigoModalidade': int(journal.sicoob_modality_code),
            'numeroContaCorrente': int(bank_account.acc_number),
            'pagador': pagador_data,
            'beneficiarioFinal': beneficiario_final_data,
            'tipoDesconto': 0,
            'numeroParcela': 1,
            'identificacaoEmissaoBoleto': int(journal.sicoob_emission_type),
            'identificacaoDistribuicaoBoleto': int(journal.sicoob_distribution_type),
        }

        if journal.narration:
            boleto_data['mensagensInstrucao'] = journal.narration.split('\n')
        
        if self.sicoob_contract_number:
            boleto_data['numeroContratoCobranca'] = int(self.sicoob_contract_number)
        
        _logger.info("[Sicoob] Adicionando informações de juros ao boleto:")
        _logger.info("- Código de juros recebido: %s", juros_multa_info['interest']['code'])
        
        boleto_data['tipoJurosMora'] = juros_multa_info['interest']['code'] or '3'
        _logger.info("- tipoJurosMora definido como: %s", boleto_data['tipoJurosMora'])
        
        if juros_multa_info['interest']['code'] and juros_multa_info['interest']['code'] != '3':
            data_juros = self.invoice_date_due + timedelta(days=juros_multa_info['interest']['date_start'])
            boleto_data['dataJurosMora'] = data_juros.strftime('%Y-%m-%d')
            _logger.info("- Data de juros calculada: %s (vencimento: %s + %s dias)", 
                        boleto_data['dataJurosMora'], 
                        self.invoice_date_due, 
                        juros_multa_info['interest']['date_start'])
            
            if juros_multa_info['interest']['code'] == '1':
                boleto_data['valorJurosMora'] = juros_multa_info['interest']['value']
                _logger.info("- Valor de juros por dia: %s", boleto_data['valorJurosMora'])
            elif juros_multa_info['interest']['code'] == '2':
                boleto_data['valorJurosMora'] = juros_multa_info['interest']['percent']
                _logger.info("- Percentual de juros mensal: %s", boleto_data['valorJurosMora'])
        
        _logger.info("[Sicoob] Adicionando informações de multa ao boleto:")
        _logger.info("- Código de multa recebido: %s", juros_multa_info['penalty']['code'])
        
        boleto_data['tipoMulta'] = juros_multa_info['penalty']['code'] or '0'
        _logger.info("- tipoMulta definido como: %s", boleto_data['tipoMulta'])
        
        if juros_multa_info['penalty']['code'] and juros_multa_info['penalty']['code'] != '0':
            data_multa = self.invoice_date_due + timedelta(days=juros_multa_info['penalty']['date_start'])
            boleto_data['dataMulta'] = data_multa.strftime('%Y-%m-%d')
            _logger.info("- Data de multa calculada: %s (vencimento: %s + %s dias)", 
                        boleto_data['dataMulta'], 
                        self.invoice_date_due, 
                        juros_multa_info['penalty']['date_start'])
            
            if juros_multa_info['penalty']['code'] == '1':
                boleto_data['valorMulta'] = juros_multa_info['penalty']['value']
                _logger.info("- Valor fixo de multa: %s", boleto_data['valorMulta'])
            elif juros_multa_info['penalty']['code'] == '2':
                boleto_data['valorMulta'] = juros_multa_info['penalty']['percent']
                _logger.info("- Percentual de multa: %s", boleto_data['valorMulta'])
        
        if desconto_info:
            boleto_data.update({
                'tipoDesconto': desconto_info.get('tipoDesconto', '0'),
                'dataPrimeiroDesconto': desconto_info.get('dataPrimeiroDesconto'),
                'valorPrimeiroDesconto': desconto_info.get('valorPrimeiroDesconto'),
            })
        
        _logger.info("[Sicoob] Estrutura final de juros e multa no boleto:")
        _logger.info("=== JUROS ===")
        _logger.info("- tipoJurosMora: %s", boleto_data.get('tipoJurosMora'))
        _logger.info("- dataJurosMora: %s", boleto_data.get('dataJurosMora'))
        _logger.info("- valorJurosMora: %s", boleto_data.get('valorJurosMora'))
        _logger.info("=== MULTA ===")
        _logger.info("- tipoMulta: %s", boleto_data.get('tipoMulta'))
        _logger.info("- dataMulta: %s", boleto_data.get('dataMulta'))
        _logger.info("- valorMulta: %s", boleto_data.get('valorMulta'))
        
        return boleto_data

    def action_emitir_boleto_sicoob(self):
        """Emite um boleto Sicoob para a fatura atual"""
        self.ensure_one()
        _logger = logging.getLogger(__name__)
        _logger.info("[Sicoob] Iniciando emissão de boleto para fatura %s", self.name)

        if self.state != 'posted':
            _logger.error("[Sicoob] Fatura %s não está confirmada (state: %s)", self.name, self.state)
            raise UserError(_('A fatura precisa estar confirmada para emitir o boleto.'))

        if self.payment_state in ['paid', 'in_payment']:
            _logger.error("[Sicoob] Fatura %s já está paga (payment_state: %s)", self.name, self.payment_state)
            raise UserError(_('A fatura já está paga ou em processo de pagamento.'))

        if self.move_type not in ['out_invoice', 'out_refund']:
            _logger.error("[Sicoob] Fatura %s não é uma fatura de cliente (move_type: %s)", self.name, self.move_type)
            raise UserError(_('Boletos só podem ser emitidos para faturas de cliente.'))

        if not self.partner_bank_id:
            _logger.error("[Sicoob] Fatura %s não tem conta bancária configurada", self.name)
            raise UserError(_('A fatura precisa ter uma conta bancária configurada.'))

        if not self.partner_bank_id.journal_id:
            _logger.error("[Sicoob] Conta bancária %s não tem diário associado", self.partner_bank_id.acc_number)
            raise UserError(_('A conta bancária precisa ter um diário associado.'))

        if not self.company_id.sicoob_partner_bank_id:
            _logger.error("[Sicoob] Empresa %s não tem conta bancária Sicoob configurada", self.company_id.name)
            raise UserError(_(
                'A empresa "%s" não possui conta bancária Sicoob configurada.\n'
                'Configure em: Configurações → Empresas → %s → Configurações Sicoob → Conta Bancária Sicoob'
            ) % (self.company_id.name, self.company_id.name))

        bank_account = self.company_id.sicoob_partner_bank_id
        _logger.info("[Sicoob] Detalhes da conta bancária:")
        _logger.info("- ID: %s", bank_account.id)
        _logger.info("- Número da Conta: %s", bank_account.acc_number)
        _logger.info("- Banco: %s", bank_account.bank_id.name if bank_account.bank_id else 'Não configurado')
        _logger.info("- Número Cliente Sicoob: %s", bank_account.sicoob_client_number)

        if not bank_account.bank_id:
            _logger.error("[Sicoob] Conta bancária %s não tem banco configurado", bank_account.acc_number)
            raise UserError(_('A conta bancária não tem um banco configurado. Configure em:\nConfigurações → Empresas → %s → Configurações Sicoob → Conta Bancária Sicoob → Banco') % self.company_id.name)

        if not bank_account.bank_id.name or 'sicoob' not in bank_account.bank_id.name.lower():
            _logger.error("[Sicoob] Conta bancária %s não é do Sicoob (banco: %s)", bank_account.acc_number, bank_account.bank_id.name)
            raise UserError(_('A conta bancária deve ser do Sicoob. Configure em:\nConfigurações → Empresas → %s → Configurações Sicoob → Conta Bancária Sicoob → Banco') % self.company_id.name)

        if not bank_account.sicoob_client_number:
            _logger.error("[Sicoob] Conta bancária %s não tem número de cliente Sicoob", bank_account.acc_number)
            raise UserError(_('A conta bancária não tem um número de cliente Sicoob configurado. Configure em:\nConfigurações → Empresas → %s → Configurações Sicoob → Conta Bancária Sicoob → Número do Cliente Sicoob') % self.company_id.name)

        sicoob_api = self.env['base.payment.api'].search([
            ('integracao', '=', 'sicoob_boleto'),
            ('company_id', '=', self.company_id.id),
            ('active', '=', True)
        ], limit=1)

        if not sicoob_api:
            _logger.error("[Sicoob] Não há integração Sicoob configurada para a empresa %s", self.company_id.name)
            raise UserError(_('Não há uma integração Sicoob configurada para esta empresa.'))

        _logger.info("[Sicoob] Integração encontrada (id: %s)", sicoob_api.id)

        return sicoob_api._emitir_boleto_sicoob(self)

    def _create_boleto_record_from_sicoob_api_response(self, response_data):
        """
        Processa a resposta da API do Sicoob e cria/atualiza o registro move.boleto.
        """
        self.ensure_one()
        _logger = logging.getLogger(__name__)
        _logger.info("[Sicoob] Criando registro move.boleto a partir da resposta da API para a fatura %s", self.name)

        if not response_data:
            _logger.warning("[Sicoob] A resposta da API (response_data) está vazia. Não é possível registrar o boleto para a fatura %s.", self.name)
            return

        codigo_barras = response_data.get('codigoBarras')
        linha_digitavel = response_data.get('linhaDigitavel')

        boleto_vals = {
            'invoice_id': self.id,
            'bank_type': 'sicoob',
            'l10n_br_is_own_number': self.sicoob_nosso_numero,
            'l10n_br_is_barcode': codigo_barras,
            'l10n_br_is_barcode_formatted': linha_digitavel,
            'sicoob_api_boleto_id': str(uuid.uuid4()),
            'sicoob_nosso_numero': self.sicoob_nosso_numero,
        }

        existing_boleto = self.env['move.boleto'].search([
            ('invoice_id', '=', self.id),
            ('bank_type', '=', 'sicoob')
        ], limit=1)

        if existing_boleto:
            _logger.info("[Sicoob] Atualizando boleto existente (ID: %s) para a fatura %s.", existing_boleto.id, self.name)
            existing_boleto.write(boleto_vals)
        else:
            _logger.info("[Sicoob] Criando novo boleto para a fatura %s.", self.name)
            self.env['move.boleto'].create(boleto_vals) 