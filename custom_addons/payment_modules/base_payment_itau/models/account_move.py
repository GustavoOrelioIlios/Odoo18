# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime
import json
import uuid
import logging

from .pydantic_models import ValidadorBoleto, ValidadorBeneficiario

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = 'account.move'
    
    itau_boleto_status = fields.Selection([
        ('none', 'Não Emitido'),
        ('success', 'Emitido com Sucesso'),
        ('error', 'Erro na Emissão'),
    ], string='Status Boleto Itaú', default='none', tracking=True)
    
    itau_boleto_date = fields.Datetime(
        string='Data Emissão Boleto',
        readonly=True,
        help='Data e hora da última emissão de boleto Itaú'
    )
    
    itau_boleto_json_request = fields.Text(
        string='JSON Enviado',
        readonly=True,
        help='JSON que foi enviado para a API do Itaú'
    )
    
    itau_boleto_json_response = fields.Text(
        string='JSON Resposta',
        readonly=True,
        help='JSON retornado pela API do Itaú'
    )
    
    itau_boleto_error_message = fields.Text(
        string='Mensagem de Erro',
        readonly=True,
        help='Mensagem de erro caso a emissão tenha falhado'
    )
    
    itau_boleto_request_formatted = fields.Html(
        string='Requisição Formatada',
        compute='_compute_itau_boleto_formatted',
        help='JSON de requisição formatado para exibição'
    )
    
    itau_boleto_response_formatted = fields.Html(
        string='Resposta Formatada', 
        compute='_compute_itau_boleto_formatted',
        help='JSON de resposta formatado para exibição'
    )
    
    l10n_br_is_own_number = fields.Char(
        string='Nosso Número',
        copy=False,
        readonly=True,
        help="Nosso Número gerado para o boleto Itaú."
    )
    
    boleto_ids = fields.One2many(
        'move.boleto',
        'invoice_id',
        string='Boletos Bancários',
        help="Boletos bancários gerados para esta fatura"
    )
    
    itau_protest_code = fields.Selection([
        ('1', 'Protestar'),
        ('4', 'Não Protestar'),
        ('9', 'Cancelar Protesto')
    ], string='Código de Protesto',
        help="O código indica o tipo de ação de protesto a ser tomada para esta fatura."
    )
    
    itau_protest_days = fields.Integer(
        string='Dias para Protesto',
        help="Quantidade de dias após o vencimento para protestar o título. Informar entre 1 e 99 dias."
    )
    
    itau_negativation_code = fields.Selection([
        ('2', 'Negativar'),
        ('5', 'Não Negativar'),
        ('10', 'Cancelar Negativação')
    ], string='Código de Negativação',
        help="Código que indica o tipo de ação de negativação para esta fatura."
    )
    
    itau_negativation_days = fields.Integer(
        string='Dias para Negativação',
        help="Quantidade de dias após o vencimento para negativar o título. Informar entre 2 e 99 dias."
    )
    
    collection_messages = fields.Text(
        string='Mensagens de Cobrança',
        help="Campo para mensagens adicionais ou notas relacionadas à cobrança desta fatura."
    )
    
    @api.constrains('itau_protest_days')
    def _check_protest_days(self):
        for record in self:
            if record.itau_protest_code == '1' and record.itau_protest_days:
                if not (1 <= record.itau_protest_days <= 99):
                    raise ValidationError(_("Dias para protesto deve estar entre 1 e 99 dias."))

    @api.constrains('itau_negativation_days')
    def _check_negativation_days(self):
        for record in self:
            if record.itau_negativation_code == '2' and record.itau_negativation_days:
                if not (2 <= record.itau_negativation_days <= 99):
                    raise ValidationError(_("Dias para negativação deve estar entre 2 e 99 dias."))

    @api.onchange('itau_protest_code')
    def _onchange_protest_code(self):
        if self.itau_protest_code != '1':
            self.itau_protest_days = False

    @api.onchange('itau_negativation_code')
    def _onchange_negativation_code(self):
        if self.itau_negativation_code != '2':
            self.itau_negativation_days = False
    
    @api.depends('itau_boleto_json_request', 'itau_boleto_json_response')
    def _compute_itau_boleto_formatted(self):
        """Formata JSONs para exibição HTML"""
        for record in self:
            if record.itau_boleto_json_request:
                try:
                    parsed = json.loads(record.itau_boleto_json_request)
                    formatted = json.dumps(parsed, indent=2, ensure_ascii=False)
                    record.itau_boleto_request_formatted = f'<pre style="background: #f8f9fa; padding: 10px; border-radius: 5px; overflow-x: auto;">{formatted}</pre>'
                except:
                    record.itau_boleto_request_formatted = f'<pre style="background: #f8f9fa; padding: 10px; border-radius: 5px; overflow-x: auto;">{record.itau_boleto_json_request or ""}</pre>'
            else:
                record.itau_boleto_request_formatted = '<p style="color: #6c757d; font-style: italic;">Nenhuma requisição realizada ainda</p>'
            
            if record.itau_boleto_json_response:
                try:
                    parsed = json.loads(record.itau_boleto_json_response)
                    formatted = json.dumps(parsed, indent=2, ensure_ascii=False)
                    record.itau_boleto_response_formatted = f'<pre style="background: #f8f9fa; padding: 10px; border-radius: 5px; overflow-x: auto;">{formatted}</pre>'
                except:
                    record.itau_boleto_response_formatted = f'<pre style="background: #f8f9fa; padding: 10px; border-radius: 5px; overflow-x: auto;">{record.itau_boleto_json_response or ""}</pre>'
            else:
                record.itau_boleto_response_formatted = '<p style="color: #6c757d; font-style: italic;">Nenhuma resposta recebida ainda</p>'
    
    def action_emitir_boleto_itau(self):
        """
        Emite boleto Itaú para a fatura atual usando dados da empresa
        """
        self.ensure_one()
        
        if self.state != 'posted':
            raise UserError(_('Só é possível emitir boleto para faturas confirmadas.'))
            
        if self.move_type not in ['out_invoice', 'out_refund']:
            raise UserError(_('Só é possível emitir boleto para faturas de cliente.'))
        
        if not self.company_id.itau_partner_bank_id:
            raise UserError(_(
                'A empresa "%s" não possui conta bancária Itaú configurada.\n'
                'Configure em: Configurações → Empresas → %s → Configurações Itaú → Conta Bancária Itaú'
            ) % (self.company_id.name, self.company_id.name))
        
        if not self.company_id.itau_payment_api_id:
            raise UserError(_(
                'A empresa "%s" não possui configuração de API Itaú.\n'
                'Configure em: Configurações → Empresas → %s → Configurações Itaú → Configuração API Itaú'
            ) % (self.company_id.name, self.company_id.name))
        
        api_config = self.company_id.itau_payment_api_id
        
        beneficiario_data = self.company_id.get_itau_beneficiario_data()
        
        pagador_data = self._get_pagador_data_from_invoice()
        
        boleto_data = self._get_boleto_data_from_invoice()
        
        validador = ValidadorBoleto()
        sucesso, dados_validados, erros_validacao = validador.validar_dados_completos(
            beneficiario_data=beneficiario_data,
            pagador_data=pagador_data,
            boleto_data=boleto_data
        )
        
        if not sucesso:
            mensagem_erros = validador.formatar_erros_para_exibicao(erros_validacao)
            
            self.write({
                'itau_boleto_status': 'error',
                'itau_boleto_date': fields.Datetime.now(),
                'itau_boleto_error_message': f" Erro de Validação:\n{mensagem_erros}",
            })
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _(' Dados Inválidos'),
                    'message': _('Dados do boleto contêm erros. Verifique os detalhes na aba "Boleto Itaú".'),
                    'type': 'danger',
                    'sticky': True,
                }
            }
        
        try:
            result = api_config._emitir_boleto_from_invoice_data(
                beneficiario_data=dados_validados['beneficiario'],
                pagador_data=dados_validados['pagador'],
                boleto_data=dados_validados['boleto']
            )
            
            self.write({
                'itau_boleto_status': 'success',
                'itau_boleto_date': fields.Datetime.now(),
                'itau_boleto_json_request': api_config.test_json_enviado,
                'itau_boleto_json_response': api_config.test_json_retorno,
                'itau_boleto_error_message': False,
            })
            
            self._create_boleto_record_from_api_response()
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('✅ Boleto Emitido e Registrado!'),
                    'message': _('Boleto Itaú emitido com sucesso e registro criado. Verifique os detalhes na aba "Boleto Itaú".'),
                    'type': 'success',
                    'sticky': False,
                }
            }
            
        except Exception as e:
            self.write({
                'itau_boleto_status': 'error',
                'itau_boleto_date': fields.Datetime.now(),
                'itau_boleto_json_request': getattr(api_config, 'test_json_enviado', '') or '',
                'itau_boleto_json_response': getattr(api_config, 'test_json_retorno', '') or '',
                'itau_boleto_error_message': str(e),
            })
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Erro na Emissão'),
                    'message': _('Falha ao emitir boleto. Verifique os detalhes na aba "Boleto Itaú".'),
                    'type': 'danger',
                    'sticky': True,
                }
            }
    
    def _get_payment_interest_penalty_info(self):
        """
        Obtém informações de juros e multa específicas do Itaú.
        
        Ordem de prioridade:
        1. Configurações do cliente (partner_id)
        2. Configurações do diário (payment_journal_id)
        
        Returns:
            dict: Dicionário com informações de juros e multa
        """
        self.ensure_one()
        
        result = {
            'interest': {
                'code': False,
                'percent': 0.0,
                'value': 0.0,
                'date_start': 1
            },
            'penalty': {
                'code': False,
                'percent': 0.0,
                'value': 0.0,
                'date_start': 1
            }
        }
        
        journal = self.payment_journal_id
        
        if self.partner_id.itau_interest_code:
            result['interest']['code'] = self.partner_id.itau_interest_code
            result['interest']['percent'] = self.partner_id.itau_interest_percent
            result['interest']['value'] = self.partner_id.itau_interest_value
            result['interest']['date_start'] = self.partner_id.itau_interest_date_start
        elif journal and journal.payment_interest_code:
            result['interest']['code'] = journal.payment_interest_code
            result['interest']['percent'] = journal.payment_interest_percent
            result['interest']['value'] = journal.payment_interest_value
            result['interest']['date_start'] = journal.payment_interest_date_start
        
        if self.partner_id.itau_penalty_code:
            result['penalty']['code'] = self.partner_id.itau_penalty_code
            result['penalty']['percent'] = self.partner_id.itau_penalty_percent
            result['penalty']['value'] = self.partner_id.itau_penalty_value
            result['penalty']['date_start'] = self.partner_id.itau_penalty_date_start
        elif journal and journal.payment_penalty_code:
            result['penalty']['code'] = journal.payment_penalty_code
            result['penalty']['percent'] = journal.payment_penalty_percent
            result['penalty']['value'] = journal.payment_penalty_value
            result['penalty']['date_start'] = journal.payment_penalty_date_start
        
        return result
    
    def _get_discount_info_from_payment_terms(self):
        """
        Obtém informações de desconto baseadas no termo de pagamento da fatura.
        
        NOVA LÓGICA: Usa as linhas de desconto customizadas (discount_line_ids) 
        se existirem, senão mantém compatibilidade com o sistema antigo.
        
        Returns:
            dict: Dicionário com estrutura de desconto da API Itaú
        """
        self.ensure_one()
        
        if not self.invoice_payment_term_id:
            return {}
        
        payment_term = self.invoice_payment_term_id
        
        if hasattr(payment_term, 'discount_line_ids') and payment_term.discount_line_ids:
            discount_data = payment_term.get_itau_discount_data(self.invoice_date)
            return discount_data
        
        else:
            
            payment_term_lines = payment_term.line_ids.filtered(
                lambda line: line.value == 'discount'
            ).sorted('sequence')
            
            discounts_list = []
            
            for line in payment_term_lines:
                if line.value_amount != 0:
                    discount_date = self.invoice_date
                    if line.days > 0:
                        from datetime import timedelta
                        discount_date = self.invoice_date + timedelta(days=line.days)
                    
                    percentual_absoluto = abs(line.value_amount)
                    
                    percentual_formatado = "{:012.0f}".format(percentual_absoluto * 10000000000)
                    
                    discount_info = {
                        'data_desconto': discount_date.strftime('%Y-%m-%d'),
                        'percentual_desconto': percentual_formatado
                    }
                    
                    discounts_list.append(discount_info)
            
            if discounts_list:
                return {
                    'codigo_tipo_desconto': '02',
                    'descontos': discounts_list
                }
            
            return {}
    
    def _get_pagador_data_from_invoice(self):
        """
        Extrai dados do pagador (cliente) da fatura com estrutura aninhada conforme API Itaú
        """
        partner = self.partner_id
        
        endereco_cobranca = partner
        if hasattr(partner, 'child_ids'):
            endereco_faturamento = partner.child_ids.filtered(lambda c: c.type == 'invoice')
            if endereco_faturamento:
                endereco_cobranca = endereco_faturamento[0]
        
        pagador_data = {
            'pessoa': {
                'nome_pessoa': partner.name or '',
                'nome_fantasia': partner.name or '',
                'tipo_pessoa': {
                    'codigo_tipo_pessoa': 'J' if partner.is_company else 'F',
                }
            },
            'endereco': {
                'nome_logradouro': f"{endereco_cobranca.street or ''}, {getattr(endereco_cobranca, 'l10n_br_number', '') or ''}",
                'nome_bairro': getattr(endereco_cobranca, 'l10n_br_district', '') or endereco_cobranca.street2 or '',
                'nome_cidade': endereco_cobranca.city or '',
                'sigla_UF': endereco_cobranca.state_id.code if endereco_cobranca.state_id else '',
                'numero_CEP': endereco_cobranca.zip or ''
            },
            'texto_endereco_email': partner.email or ''
        }
        
        if partner.vat:
            if partner.is_company:
                pagador_data['pessoa']['tipo_pessoa']['numero_cadastro_nacional_pessoa_juridica'] = partner.vat
            else:
                pagador_data['pessoa']['tipo_pessoa']['numero_cadastro_pessoa_fisica'] = partner.vat
        
        return pagador_data
    
    def _get_boleto_data_from_invoice(self):
        """Obtém dados do boleto a partir da fatura"""
        self.ensure_one()
        
        if not self.l10n_br_is_own_number:
            nosso_numero_gerado = self.env['ir.sequence'].next_by_code('itau.nosso.numero')
            if not nosso_numero_gerado:
                raise UserError(_("A sequência para 'Nosso Número' (itau.nosso.numero) não pôde ser gerada. Verifique as configurações da sequência."))
            self.l10n_br_is_own_number = nosso_numero_gerado
        
        boleto_data = {
            'codigo_carteira': self.partner_bank_id.journal_id.itau_wallet_code or '109',
            'codigo_especie': self.partner_bank_id.journal_id.l10n_br_is_payment_mode_id or '01',
            'descricao_especie': dict(self.partner_bank_id.journal_id._fields['l10n_br_is_payment_mode_id'].selection).get(
                self.partner_bank_id.journal_id.l10n_br_is_payment_mode_id, ''
            ),
            'descricao_instrumento_cobranca': 'boleto',
            'codigo_aceite': 'S',
            'tipo_boleto': 'proposta',
            'data_emissao': fields.Date.today().strftime('%Y-%m-%d'),
            'dados_individuais_boleto': [{
                'valor_titulo': str(self.amount_total),
                'data_vencimento': self.invoice_date_due.strftime('%Y-%m-%d'),
                'data_limite_pagamento': self.invoice_date_due.strftime('%Y-%m-%d'),
                'id_boleto_individual': str(uuid.uuid4()),
                'numero_nosso_numero': self.l10n_br_is_own_number,
                'texto_seu_numero': f"NFe {self.name}" if self.name else '',
                'texto_uso_beneficiario': None
            }]
        }
        
        juros_info = self._get_payment_interest_penalty_info()
        if juros_info:
            boleto_data.update(juros_info)
        
        desconto_info = self._get_discount_info_from_payment_terms()
        if desconto_info:
            boleto_data.update(desconto_info)
        
        if self.itau_protest_code:
            boleto_data['protesto'] = {
                'codigo_tipo_protesto': int(self.itau_protest_code),
                'quantidade_dias_protesto': self.itau_protest_days if self.itau_protest_code == '1' else None,
                'protesto_falimentar': True
            }
        
        if self.itau_negativation_code:
            boleto_data['negativacao'] = {
                'codigo_tipo_negativacao': int(self.itau_negativation_code),
                'quantidade_dias_negativacao': self.itau_negativation_days if self.itau_negativation_code == '2' else None
            }
        
        return boleto_data
    
    def _create_boleto_record_from_api_response(self):
        """
        Processa a resposta da API do Itaú e cria o registro move.boleto
        """
        self.ensure_one()
        
        if not self.itau_boleto_json_response:
            raise UserError(_("A resposta da API (JSON Recebido) está vazia. Não é possível registrar o boleto."))

        try:
            response_data = json.loads(self.itau_boleto_json_response)
        except json.JSONDecodeError:
            raise UserError(_("Erro: Não foi possível decodificar a resposta JSON da API."))
        
        if response_data.get('etapa_processo_boleto') == 'efetivacao':
            
            dados_boleto_individual = response_data.get('dados_individuais_boleto', [{}])[0]

            boleto_vals = {
                'invoice_id': self.id,
                'bank_type': 'itau',
                'l10n_br_is_barcode': dados_boleto_individual.get('codigo_barras', ''),
                'l10n_br_is_barcode_formatted': dados_boleto_individual.get('numero_linha_digitavel', ''),
                'data_limite_pagamento': dados_boleto_individual.get('data_limite_pagamento') or self.invoice_date_due,
                'l10n_br_is_own_number': self.l10n_br_is_own_number,
            }
            
            api_boleto_id = response_data.get('id_boleto')
            if api_boleto_id and api_boleto_id.strip():
                boleto_vals['itau_boleto_id'] = api_boleto_id.strip()
            else:
                boleto_vals['itau_boleto_id'] = str(uuid.uuid4())

            existing_boleto = self.env['move.boleto'].search([
                ('invoice_id', '=', self.id),
                ('bank_type', '=', 'itau')
            ], limit=1)
            
            if existing_boleto:
                existing_boleto.write(boleto_vals)
            else:
                self.env['move.boleto'].create(boleto_vals)
                
        else:
            mensagem_erro = response_data.get('mensagem_retorno', 'Erro desconhecido retornado pela API.')
            raise UserError(_("Falha ao registrar boleto no Itaú: %s") % mensagem_erro)
    
    def action_generate_itau_boleto(self):
        """
        Gera o boleto Itaú para a fatura, criando o "Nosso Número" e o registro move.boleto
        """
        for move in self:
            if not move.partner_bank_id:
                raise UserError(_("O campo 'Banco Destinatário' é obrigatório para emitir um boleto."))
            
            journal = move.partner_bank_id.journal_id
            if not journal:
                raise UserError(_("A conta bancária selecionada não está associada a um Diário. Verifique a configuração em 'Faturamento > Configuração > Contas Bancárias'."))
            
            if not journal.itau_wallet_code:
                raise UserError(_("Configure o 'Código da Carteira' no diário do banco (%s).") % journal.name)
            if not journal.l10n_br_is_payment_mode_id:
                raise UserError(_("Configure a 'Espécie do Título' no diário do banco (%s).") % journal.name)
            
            move.action_emitir_boleto_itau()
        return True 

 