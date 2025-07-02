# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import re
from datetime import date, timedelta
import logging


class AccountMove(models.Model):
    _inherit = 'account.move'

    sicoob_contract_number = fields.Char(
        string='Número do Contrato de Cobrança (Sicoob)',
        help='Número do contrato Sicoob associado à fatura',
        copy=False
    )

    test_json_enviado = fields.Text(
        string='JSON Enviado',
        help='JSON enviado para a API do Sicoob',
        copy=False
    )

    test_json_retorno = fields.Text(
        string='JSON Retornado',
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
        help='Última mensagem de erro retornada pela API Sicoob',
        copy=False
    )

    @api.constrains('sicoob_contract_number')
    def _check_sicoob_contract_number(self):
        """Validação do número do contrato Sicoob"""
        for record in self:
            if record.sicoob_contract_number:
                # Remove caracteres não numéricos para validação
                clean_number = ''.join(filter(str.isdigit, record.sicoob_contract_number))
                if not clean_number:
                    raise ValidationError(_('O número do contrato Sicoob deve conter pelo menos um dígito numérico.'))
                if len(clean_number) > 20:  # Limite máximo de 20 dígitos
                    raise ValidationError(_('O número do contrato Sicoob não pode ter mais de 20 dígitos.'))

    def _get_sicoob_pagador_data_from_invoice(self):
        """
        Extrai dados do pagador (cliente da fatura) e os formata para PagadorModel do Pydantic.
        """
        self.ensure_one()
        partner = self.partner_id  # O cliente da fatura

        # Determina o endereço para cobrança
        endereco_cobranca = partner
        if partner.child_ids:
            endereco_faturamento = partner.child_ids.filtered(lambda c: c.type == 'invoice')
            if endereco_faturamento:
                endereco_cobranca = endereco_faturamento[0]

        # Limpa o CPF/CNPJ
        vat = re.sub(r'[^\d]', '', partner.vat or '') if partner.vat else ''
        if not vat:
            raise UserError(_('O cliente não possui CPF/CNPJ cadastrado.'))

        # Limpa o CEP
        cep = re.sub(r'[^\d]', '', endereco_cobranca.zip or '') if endereco_cobranca.zip else ''
        if not cep:
            raise UserError(_('O cliente não possui CEP cadastrado.'))

        # Obtém o código UF
        uf = endereco_cobranca.state_id.code if endereco_cobranca.state_id else ''
        if not uf:
            raise UserError(_('O cliente não possui UF cadastrada.'))

        # Monta o endereço completo
        endereco = endereco_cobranca.street or ''
        if endereco_cobranca.street2:
            endereco = f"{endereco}, {endereco_cobranca.street2}"

        # Usa o street2 como bairro
        bairro = endereco_cobranca.street2 or ''

        pagador_data = {
            'numeroCpfCnpj': vat,
            'nome': partner.name or '',
            'endereco': endereco,
            'bairro': bairro,
            'cidade': endereco_cobranca.city or '',
            'cep': cep,
            'uf': uf,
            'email': partner.email or None  # None para que seja omitido se não existir
        }

        return pagador_data

    def _get_sicoob_beneficiario_final_data(self):
        """
        Extrai dados do beneficiário final (empresa que está emitindo o boleto)
        e os formata para BeneficiarioFinalModel do Pydantic.
        """
        self.ensure_one()
        company = self.company_id

        # Limpa o CNPJ da empresa
        vat = re.sub(r'[^\d]', '', company.vat or '') if company.vat else ''
        if not vat:
            raise UserError(_('A empresa não possui CNPJ cadastrado.'))

        beneficiario_final_data = {
            'numeroCpfCnpj': vat,
            'nome': company.name or ''
        }

        return beneficiario_final_data

    def _get_sicoob_boleto_details_data(self):
        """
        Coleta todos os dados necessários para emissão do boleto Sicoob.
        """
        self.ensure_one()
        _logger = logging.getLogger(__name__)
        _logger.info("[Sicoob] Coletando dados para boleto da fatura %s", self.name)

        # Obtém os dados do pagador e beneficiário final
        pagador_data = self._get_sicoob_pagador_data_from_invoice()
        beneficiario_final_data = self._get_sicoob_beneficiario_final_data()

        # Verifica se tem um diário configurado
        if not self.journal_id:
            _logger.error("[Sicoob] Fatura %s não tem diário configurado", self.name)
            raise UserError(_('A fatura precisa ter um diário configurado.'))

        # Verifica se a empresa tem conta bancária Sicoob configurada
        if not self.company_id.sicoob_partner_bank_id:
            _logger.error("[Sicoob] Empresa %s não tem conta bancária Sicoob configurada", self.company_id.name)
            raise UserError(_(
                'A empresa "%s" não possui conta bancária Sicoob configurada.\n'
                'Configure em: Configurações → Empresas → %s → Configurações Sicoob → Conta Bancária Sicoob'
            ) % (self.company_id.name, self.company_id.name))

        # Log detalhado da conta bancária e suas relações
        bank_account = self.company_id.sicoob_partner_bank_id
        _logger.info("[Sicoob] Detalhes da conta bancária:")
        _logger.info("- ID: %s", bank_account.id)
        _logger.info("- Número da Conta: %s", bank_account.acc_number)
        _logger.info("- Banco: %s", bank_account.bank_id.name if bank_account.bank_id else 'Não configurado')
        _logger.info("- Número Cliente Sicoob: %s", bank_account.sicoob_client_number)

        # Validação do banco
        if not bank_account.bank_id:
            _logger.error("[Sicoob] Conta bancária %s não tem banco configurado", bank_account.acc_number)
            raise UserError(_('A conta bancária não tem um banco configurado. Configure em:\nConfigurações → Empresas → %s → Configurações Sicoob → Conta Bancária Sicoob → Banco') % self.company_id.name)

        if not bank_account.bank_id.name or 'sicoob' not in bank_account.bank_id.name.lower():
            _logger.error("[Sicoob] Conta bancária %s não é do Sicoob (banco: %s)", bank_account.acc_number, bank_account.bank_id.name)
            raise UserError(_('A conta bancária deve ser do Sicoob. Configure em:\nConfigurações → Empresas → %s → Configurações Sicoob → Conta Bancária Sicoob → Banco') % self.company_id.name)

        # Validação do número do cliente Sicoob
        if not bank_account.sicoob_client_number:
            _logger.error("[Sicoob] Conta bancária %s não tem número de cliente Sicoob", bank_account.acc_number)
            raise UserError(_('A conta bancária não tem um número de cliente Sicoob configurado. Configure em:\nConfigurações → Empresas → %s → Configurações Sicoob → Conta Bancária Sicoob → Número do Cliente Sicoob') % self.company_id.name)

        # Obtém o nosso número
        nosso_numero = int(self.env['ir.sequence'].next_by_code('sicoob.nosso.numero'))
        _logger.info("[Sicoob] Nosso número gerado: %s", nosso_numero)

        # Calcula datas
        data_emissao = self.invoice_date or fields.Date.today()
        data_vencimento = self.invoice_date_due or (data_emissao + timedelta(days=30))
        data_limite = data_vencimento  # Por padrão, igual ao vencimento
        data_multa = data_vencimento + timedelta(days=1)  # 1 dia após vencimento
        data_juros = data_vencimento + timedelta(days=1)  # 1 dia após vencimento
        data_desconto = data_vencimento - timedelta(days=5)

        _logger.info("[Sicoob] Datas do boleto:")
        _logger.info("- Emissão: %s", data_emissao)
        _logger.info("- Vencimento: %s", data_vencimento)
        _logger.info("- Limite: %s", data_limite)
        _logger.info("- Multa: %s", data_multa)
        _logger.info("- Juros: %s", data_juros)
        _logger.info("- Desconto: %s", data_desconto)

        # Monta o payload completo
        payload = {
            'numeroCliente': int(bank_account.sicoob_client_number),
            'codigoModalidade': 1,  # SIMPLES COM REGISTRO
            'numeroContaCorrente': int(bank_account.acc_number or 0),
            'codigoEspecieDocumento': 'DM',  # Duplicata Mercantil
            'dataEmissao': data_emissao.isoformat(),  # Converte para string ISO
            'nossoNumero': nosso_numero,
            'seuNumero': self.name or '',  # Número da fatura
            'identificacaoBoletoEmpresa': self.ref or str(self.id),  # Referência externa ou ID
            'identificacaoEmissaoBoleto': 1,  # Banco Emite
            'identificacaoDistribuicaoBoleto': 1,  # Banco Distribui
            'valor': float(self.amount_residual),
            'dataVencimento': data_vencimento.isoformat(),  # Converte para string ISO
            'dataLimitePagamento': data_limite.isoformat(),  # Converte para string ISO
            'valorAbatimento': 0.0,
            'tipoDesconto': 1,  # Valor Fixo até a Data Informada
            'dataPrimeiroDesconto': data_desconto.isoformat(),  # Converte para string ISO
            'valorPrimeiroDesconto': 0.0,
            'dataSegundoDesconto': None,
            'valorSegundoDesconto': None,
            'dataTerceiroDesconto': None,
            'valorTerceiroDesconto': None,
            'tipoMulta': 1,  # Valor Fixo
            'dataMulta': data_multa.isoformat(),  # Converte para string ISO
            'valorMulta': float(self.amount_residual * 0.02),  # 2% de multa
            'tipoJurosMora': 1,  # Valor Fixo
            'dataJurosMora': data_juros.isoformat(),  # Converte para string ISO
            'valorJurosMora': float(self.amount_residual * 0.001),
            'numeroParcela': 1,  # Parcela única
            'aceite': True,
            'codigoNegativacao': None,  # Sem negativação
            'numeroDiasNegativacao': None,
            'codigoProtesto': None,  # Sem protesto
            'numeroDiasProtesto': None,
            'pagador': pagador_data,
            'beneficiarioFinal': beneficiario_final_data,
            'mensagensInstrucao': [
                'Após vencimento cobrar multa de 2%',
                'Após vencimento cobrar juros de 0,1% ao dia',
                'Não receber após 30 dias de vencido'
            ],
            'gerarPdf': True,  # Gerar PDF do boleto
            'rateioCreditos': None,  # Sem rateio de créditos
            'codigoCadastrarPIX': None,  # Sem PIX
            'numeroContratoCobranca': int(self.sicoob_contract_number) if self.sicoob_contract_number else None
        }

        _logger.info("[Sicoob] Payload montado com sucesso para fatura %s", self.name)
        return payload

    def action_emitir_boleto_sicoob(self):
        """Emite um boleto Sicoob para a fatura atual"""
        self.ensure_one()
        _logger = logging.getLogger(__name__)
        _logger.info("[Sicoob] Iniciando emissão de boleto para fatura %s", self.name)

        # Verifica se a fatura está confirmada
        if self.state != 'posted':
            _logger.error("[Sicoob] Fatura %s não está confirmada (state: %s)", self.name, self.state)
            raise UserError(_('A fatura precisa estar confirmada para emitir o boleto.'))

        # Verifica se a fatura já está paga
        if self.payment_state in ['paid', 'in_payment']:
            _logger.error("[Sicoob] Fatura %s já está paga (payment_state: %s)", self.name, self.payment_state)
            raise UserError(_('A fatura já está paga ou em processo de pagamento.'))

        # Verifica se é uma fatura de cliente
        if self.move_type not in ['out_invoice', 'out_refund']:
            _logger.error("[Sicoob] Fatura %s não é uma fatura de cliente (move_type: %s)", self.name, self.move_type)
            raise UserError(_('Boletos só podem ser emitidos para faturas de cliente.'))

        # Verifica se tem um diário configurado
        if not self.journal_id:
            _logger.error("[Sicoob] Fatura %s não tem diário configurado", self.name)
            raise UserError(_('A fatura precisa ter um diário configurado.'))

        # Verifica se a empresa tem conta bancária Sicoob configurada
        if not self.company_id.sicoob_partner_bank_id:
            _logger.error("[Sicoob] Empresa %s não tem conta bancária Sicoob configurada", self.company_id.name)
            raise UserError(_(
                'A empresa "%s" não possui conta bancária Sicoob configurada.\n'
                'Configure em: Configurações → Empresas → %s → Configurações Sicoob → Conta Bancária Sicoob'
            ) % (self.company_id.name, self.company_id.name))

        # Log detalhado da conta bancária e suas relações
        bank_account = self.company_id.sicoob_partner_bank_id
        _logger.info("[Sicoob] Detalhes da conta bancária:")
        _logger.info("- ID: %s", bank_account.id)
        _logger.info("- Número da Conta: %s", bank_account.acc_number)
        _logger.info("- Banco: %s", bank_account.bank_id.name if bank_account.bank_id else 'Não configurado')
        _logger.info("- Número Cliente Sicoob: %s", bank_account.sicoob_client_number)

        # Validação do banco
        if not bank_account.bank_id:
            _logger.error("[Sicoob] Conta bancária %s não tem banco configurado", bank_account.acc_number)
            raise UserError(_('A conta bancária não tem um banco configurado. Configure em:\nConfigurações → Empresas → %s → Configurações Sicoob → Conta Bancária Sicoob → Banco') % self.company_id.name)

        if not bank_account.bank_id.name or 'sicoob' not in bank_account.bank_id.name.lower():
            _logger.error("[Sicoob] Conta bancária %s não é do Sicoob (banco: %s)", bank_account.acc_number, bank_account.bank_id.name)
            raise UserError(_('A conta bancária deve ser do Sicoob. Configure em:\nConfigurações → Empresas → %s → Configurações Sicoob → Conta Bancária Sicoob → Banco') % self.company_id.name)

        # Validação do número do cliente Sicoob
        if not bank_account.sicoob_client_number:
            _logger.error("[Sicoob] Conta bancária %s não tem número de cliente Sicoob", bank_account.acc_number)
            raise UserError(_('A conta bancária não tem um número de cliente Sicoob configurado. Configure em:\nConfigurações → Empresas → %s → Configurações Sicoob → Conta Bancária Sicoob → Número do Cliente Sicoob') % self.company_id.name)

        # Obtém a API Sicoob configurada
        sicoob_api = self.env['base.payment.api'].search([
            ('integracao', '=', 'sicoob_boleto'),
            ('company_id', '=', self.company_id.id),
            ('active', '=', True)
        ], limit=1)

        if not sicoob_api:
            _logger.error("[Sicoob] Não há integração Sicoob configurada para a empresa %s", self.company_id.name)
            raise UserError(_('Não há uma integração Sicoob configurada para esta empresa.'))

        _logger.info("[Sicoob] Integração encontrada (id: %s)", sicoob_api.id)

        # Emite o boleto
        return sicoob_api._emitir_boleto_sicoob(self) 