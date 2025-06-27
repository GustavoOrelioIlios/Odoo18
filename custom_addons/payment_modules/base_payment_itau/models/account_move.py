# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime
import json
import uuid
import logging

# Importação dos modelos Pydantic para validação
from .pydantic_models import ValidadorBoleto, ValidadorBeneficiario

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = 'account.move'
    
    # Campos para armazenar informações de boleto Itaú
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
    
    # Campos computados para exibição
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
    
    # NOVO CAMPO - Nosso Número
    l10n_br_is_own_number = fields.Char(
        string='Nosso Número',
        copy=False,
        readonly=True,
        help="Nosso Número gerado para o boleto Itaú."
    )
    
    # NOVO CAMPO - Relacionamento com boletos
    boleto_ids = fields.One2many(
        'move.boleto',
        'invoice_id',
        string='Boletos Bancários',
        help="Boletos bancários gerados para esta fatura"
    )
    

    
    @api.depends('itau_boleto_json_request', 'itau_boleto_json_response')
    def _compute_itau_boleto_formatted(self):
        """Formata JSONs para exibição HTML"""
        for record in self:
            # Formata JSON de requisição
            if record.itau_boleto_json_request:
                try:
                    parsed = json.loads(record.itau_boleto_json_request)
                    formatted = json.dumps(parsed, indent=2, ensure_ascii=False)
                    record.itau_boleto_request_formatted = f'<pre style="background: #f8f9fa; padding: 10px; border-radius: 5px; overflow-x: auto;">{formatted}</pre>'
                except:
                    record.itau_boleto_request_formatted = f'<pre style="background: #f8f9fa; padding: 10px; border-radius: 5px; overflow-x: auto;">{record.itau_boleto_json_request or ""}</pre>'
            else:
                record.itau_boleto_request_formatted = '<p style="color: #6c757d; font-style: italic;">Nenhuma requisição realizada ainda</p>'
            
            # Formata JSON de resposta
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
        
        # Validações básicas
        if self.state != 'posted':
            raise UserError(_('Só é possível emitir boleto para faturas confirmadas.'))
            
        if self.move_type not in ['out_invoice', 'out_refund']:
            raise UserError(_('Só é possível emitir boleto para faturas de cliente.'))
        
        # Verifica se a empresa tem conta bancária Itaú configurada
        if not self.company_id.itau_partner_bank_id:
            raise UserError(_(
                'A empresa "%s" não possui conta bancária Itaú configurada.\n'
                'Configure em: Configurações → Empresas → %s → Configurações Itaú → Conta Bancária Itaú'
            ) % (self.company_id.name, self.company_id.name))
        
        # Verifica se a empresa tem configuração de API Itaú
        if not self.company_id.itau_payment_api_id:
            raise UserError(_(
                'A empresa "%s" não possui configuração de API Itaú.\n'
                'Configure em: Configurações → Empresas → %s → Configurações Itaú → Configuração API Itaú'
            ) % (self.company_id.name, self.company_id.name))
        
        # Obtém configuração da API
        api_config = self.company_id.itau_payment_api_id
        
        # Obtém dados do beneficiário da empresa
        beneficiario_data = self.company_id.get_itau_beneficiario_data()
        
        # Monta dados do pagador (cliente da fatura)
        pagador_data = self._get_pagador_data_from_invoice()
        
        # Monta dados específicos do boleto
        boleto_data = self._get_boleto_data_from_invoice()
        
        # ✅ VALIDAÇÃO PYDANTIC - Valida todos os dados antes de chamar a API
        validador = ValidadorBoleto()
        sucesso, dados_validados, erros_validacao = validador.validar_dados_completos(
            beneficiario_data=beneficiario_data,
            pagador_data=pagador_data,
            boleto_data=boleto_data
        )
        
        if not sucesso:
            # Formata erros para exibição
            mensagem_erros = validador.formatar_erros_para_exibicao(erros_validacao)
            
            # Salva erro de validação
            self.write({
                'itau_boleto_status': 'error',
                'itau_boleto_date': fields.Datetime.now(),
                'itau_boleto_error_message': f" Erro de Validação:\n{mensagem_erros}",
            })
            
            # Notificação de erro de validação
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
        
        # Chama API do Itaú com dados validados
        try:
            result = api_config._emitir_boleto_from_invoice_data(
                beneficiario_data=dados_validados['beneficiario'],
                pagador_data=dados_validados['pagador'],
                boleto_data=dados_validados['boleto']
            )
            
            # Atualiza campos de status e JSONs
            self.write({
                'itau_boleto_status': 'success',
                'itau_boleto_date': fields.Datetime.now(),
                'itau_boleto_json_request': api_config.test_json_enviado,
                'itau_boleto_json_response': api_config.test_json_retorno,
                'itau_boleto_error_message': False,
            })
            
            # --- ETAPA 2: PROCESSAR A RESPOSTA E CRIAR O REGISTRO MOVE.BOLETO ---
            self._create_boleto_record_from_api_response()
            
            # Notificação de sucesso na tela
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
            # Atualiza campos com erro
            self.write({
                'itau_boleto_status': 'error',
                'itau_boleto_date': fields.Datetime.now(),
                'itau_boleto_json_request': getattr(api_config, 'test_json_enviado', '') or '',
                'itau_boleto_json_response': getattr(api_config, 'test_json_retorno', '') or '',
                'itau_boleto_error_message': str(e),
            })
            
            # Notificação de erro na tela
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('❌ Erro na Emissão'),
                    'message': _('Falha ao emitir boleto. Verifique os detalhes na aba "Boleto Itaú".'),
                    'type': 'danger',
                    'sticky': True,
                }
            }
    
    def _get_payment_interest_penalty_info(self):
        """
        Obtém informações de juros e multa aplicando lógica de fallback.
        
        Ordem de prioridade:
        1. Configurações do cliente (partner_id)
        2. Configurações padrão do diário (partner_bank_id.journal_id)
        
        Returns:
            dict: Dicionário com informações de juros e multa
        """
        self.ensure_one()
        
        # Inicializa resultado
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
        
        # Obtém o diário correto (do banco destinatário)
        journal = None
        if self.partner_bank_id and self.partner_bank_id.journal_id:
            journal = self.partner_bank_id.journal_id
        
        # 🚨 DEBUG LOG TEMPORÁRIO
        _logger.info("🔍 DEBUG - Partner: %s | Partner Bank: %s | Journal: %s", 
                     self.partner_id.name, 
                     self.partner_bank_id.display_name if self.partner_bank_id else 'None',
                     journal.name if journal else 'None')
        
        # === JUROS ===
        # Prioridade 1: Cliente
        if self.partner_id.payment_interest_code:
            _logger.info("🔍 DEBUG - Usando JUROS do CLIENTE: %s", self.partner_id.payment_interest_code)
            result['interest']['code'] = self.partner_id.payment_interest_code
            result['interest']['percent'] = self.partner_id.payment_interest_percent
            result['interest']['value'] = self.partner_id.payment_interest_value
            result['interest']['date_start'] = self.partner_id.payment_interest_date_start
        # Prioridade 2: Diário (fallback)
        elif journal and journal.payment_interest_code:
            _logger.info("🔍 DEBUG - Usando JUROS do DIÁRIO: %s", journal.payment_interest_code)
            result['interest']['code'] = journal.payment_interest_code
            result['interest']['percent'] = journal.payment_interest_percent
            result['interest']['value'] = journal.payment_interest_value
            result['interest']['date_start'] = journal.payment_interest_date_start
        else:
            _logger.info("🔍 DEBUG - JUROS não encontrado nem no cliente nem no diário")
        
        # === MULTA ===
        # Prioridade 1: Cliente
        if self.partner_id.payment_penalty_code:
            _logger.info("🔍 DEBUG - Usando MULTA do CLIENTE: %s", self.partner_id.payment_penalty_code)
            result['penalty']['code'] = self.partner_id.payment_penalty_code
            result['penalty']['percent'] = self.partner_id.payment_penalty_percent
            result['penalty']['value'] = self.partner_id.payment_penalty_value
            result['penalty']['date_start'] = self.partner_id.payment_penalty_date_start
        # Prioridade 2: Diário (fallback)
        elif journal and journal.payment_penalty_code:
            _logger.info("🔍 DEBUG - Usando MULTA do DIÁRIO: %s", journal.payment_penalty_code)
            result['penalty']['code'] = journal.payment_penalty_code
            result['penalty']['percent'] = journal.payment_penalty_percent
            result['penalty']['value'] = journal.payment_penalty_value
            result['penalty']['date_start'] = journal.payment_penalty_date_start
        else:
            _logger.info("🔍 DEBUG - MULTA não encontrada nem no cliente nem no diário")
        
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
        
        # === NOVA LÓGICA: Usa sistema de múltiplos descontos ===
        if hasattr(payment_term, 'discount_line_ids') and payment_term.discount_line_ids:
            _logger.info("🔍 DEBUG - Usando NOVO sistema de descontos: %d linhas encontradas", 
                         len(payment_term.discount_line_ids))
            
            # Usa o método do termo de pagamento para gerar estrutura
            discount_data = payment_term.get_itau_discount_data(self.invoice_date)
            
            if discount_data:
                _logger.info("🔍 DEBUG - Estrutura de desconto gerada: %s", discount_data)
            
            return discount_data
        
        # === LÓGICA ANTIGA: Compatibilidade com sistema original ===
        else:
            _logger.info("🔍 DEBUG - Usando sistema ANTIGO de descontos (compatibilidade)")
            
            # Obtém linhas do termo de pagamento que são descontos (sistema original)
            payment_term_lines = payment_term.line_ids.filtered(
                lambda line: line.value == 'discount'
            ).sorted('sequence')
            
            discounts_list = []
            
            for line in payment_term_lines:
                if line.value_amount != 0:  # Se há desconto configurado (pode ser negativo)
                    # Calcula data do desconto baseada na data da fatura
                    discount_date = self.invoice_date
                    if line.days > 0:
                        from datetime import timedelta
                        discount_date = self.invoice_date + timedelta(days=line.days)
                    
                    # Remove o sinal negativo do percentual (Odoo armazena como negativo)
                    percentual_absoluto = abs(line.value_amount)
                    
                    # Formata percentual como string de 12 dígitos sem decimais
                    # Exemplo: 2.5% = 250000000000 (2.5 * 100 * 1000000000)
                    percentual_formatado = "{:012.0f}".format(percentual_absoluto * 10000000000)
                    
                    discount_info = {
                        'data_desconto': discount_date.strftime('%Y-%m-%d'),
                        'percentual_desconto': percentual_formatado
                    }
                    
                    discounts_list.append(discount_info)
            
            # Retorna a estrutura completa de desconto conforme API Itaú
            if discounts_list:
                return {
                    'codigo_tipo_desconto': '02',  # Código para desconto percentual (padrão antigo)
                    'descontos': discounts_list
                }
            
            return {}
    
    def _get_pagador_data_from_invoice(self):
        """
        Extrai dados do pagador (cliente) da fatura com estrutura aninhada conforme API Itaú
        """
        partner = self.partner_id
        
        # Determina endereço (faturamento tem prioridade)
        endereco_cobranca = partner
        if hasattr(partner, 'child_ids'):
            endereco_faturamento = partner.child_ids.filtered(lambda c: c.type == 'invoice')
            if endereco_faturamento:
                endereco_cobranca = endereco_faturamento[0]
        
        # ESTRUTURA CORRIGIDA: Objeto aninhado conforme API Itaú
        pagador_data = {
            'pessoa': {
                'nome_pessoa': partner.name or '',
                'nome_fantasia': partner.name or '',  # Pode usar o mesmo nome ou um campo diferente se existir
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
        
        # Adiciona documento (CPF/CNPJ) na estrutura correta
        if partner.vat:
            if partner.is_company:
                pagador_data['pessoa']['tipo_pessoa']['numero_cadastro_nacional_pessoa_juridica'] = partner.vat
            else:
                pagador_data['pessoa']['tipo_pessoa']['numero_cadastro_pessoa_fisica'] = partner.vat
        
        return pagador_data
    
    def _get_boleto_data_from_invoice(self):
        """
        Extrai dados específicos do boleto da fatura com campos adicionais
        """
        # --- CORREÇÃO: Pega configurações do diário do banco destinatário ---
        if not self.partner_bank_id:
            raise UserError(_("O campo 'Banco Destinatário' é obrigatório para emitir um boleto."))
        
        journal = self.partner_bank_id.journal_id
        if not journal:
            raise UserError(_("A conta bancária selecionada não está associada a um Diário. Verifique a configuração em 'Faturamento > Configuração > Contas Bancárias'."))
        
        # Pega o código da carteira do diário correto - obrigatório
        codigo_carteira = journal.itau_wallet_code
        if not codigo_carteira:
            raise UserError(_('O campo "Código da Carteira de Cobrança (Itaú)" deve ser preenchido no diário %s') % journal.name)
        
        # Pega o código da espécie do diário correto - obrigatório
        codigo_especie = journal.l10n_br_is_payment_mode_id
        if not codigo_especie:
            raise UserError(_('O campo "Código da Espécie do Título (Itaú)" deve ser preenchido no diário %s') % journal.name)
        
        # Gera ou busca o "Nosso Número" se não existir
        if not self.l10n_br_is_own_number:
            own_number = self.env['ir.sequence'].next_by_code('itau.nosso.numero')
            self.write({'l10n_br_is_own_number': own_number})
        
        # Busca ou cria o registro move.boleto
        boleto_record = self.env['move.boleto'].search([('invoice_id', '=', self.id)], limit=1)
        if not boleto_record:
            boleto_record = self.env['move.boleto'].create({'invoice_id': self.id})
        
        # === OBTÉM INFORMAÇÕES DE JUROS E MULTA ===
        interest_penalty_info = self._get_payment_interest_penalty_info()
        
        # 🚨 DEBUG LOG TEMPORÁRIO
        _logger.info("🔍 DEBUG - Interest/Penalty Info: %s", interest_penalty_info)
        
        # === OBTÉM INFORMAÇÕES DE DESCONTO ===
        discount_info = self._get_discount_info_from_payment_terms()
        
        # 🚨 DEBUG LOG TEMPORÁRIO
        _logger.info("🔍 DEBUG - Discount Info: %s", discount_info)
        
        boleto_data = {
            'codigo_carteira': codigo_carteira,
            'codigo_especie': codigo_especie,
            'descricao_especie': journal.l10n_br_is_payment_mode_description or '',  # CAMPO ADICIONADO
            'descricao_instrumento_cobranca': 'boleto',  # CAMPO ADICIONADO
            'codigo_aceite': 'S',
            'tipo_boleto': 'proposta',
            'data_emissao': fields.Date.context_today(self).strftime('%Y-%m-%d'),
            
            'dados_individuais_boleto': [{
                'valor_titulo': f"{self.amount_total:.2f}",
                'data_vencimento': self.invoice_date_due.strftime('%Y-%m-%d') if self.invoice_date_due else fields.Date.context_today(self).strftime('%Y-%m-%d'),
                'data_limite_pagamento': self.invoice_date_due.strftime('%Y-%m-%d') if self.invoice_date_due else fields.Date.context_today(self).strftime('%Y-%m-%d'),  # CAMPO ADICIONADO
                'id_boleto_individual': boleto_record.itau_boleto_id or str(uuid.uuid4()),
                'numero_nosso_numero': self.l10n_br_is_own_number,
                'texto_seu_numero': self.name or '',
                'texto_uso_beneficiario': f"Fatura {self.name}" if self.name else 'Fatura',
            }],
        }
        
        # === ADICIONA INFORMAÇÕES DE JUROS (SE CONFIGURADO) ===
        if interest_penalty_info['interest']['code'] and interest_penalty_info['interest']['code'] != '05':  # Não é isento
            # 🚨 DEBUG LOG TEMPORÁRIO
            _logger.info("🔍 DEBUG - Adicionando JUROS ao boleto_data")
            
            from datetime import timedelta
            data_inicio_juros = self.invoice_date_due + timedelta(days=interest_penalty_info['interest']['date_start'])
            
            juros_config = {
                'codigo_tipo_juros': interest_penalty_info['interest']['code'],
                'data_juros': data_inicio_juros.strftime('%Y-%m-%d')
            }
            
            # Adiciona valor ou percentual dependendo do tipo
            if interest_penalty_info['interest']['code'] in ['90', '91', '92']:  # Percentual
                # Formata percentual como string de 12 dígitos sem decimais
                # Exemplo: 1.5% = 150000000000 (1.5 * 100 * 1000000000)
                percentual_formatado = "{:012.0f}".format(interest_penalty_info['interest']['percent'] * 10000000000)
                juros_config['percentual_juros'] = percentual_formatado
            elif interest_penalty_info['interest']['code'] == '93':  # Valor Diário
                juros_config['valor_juros'] = "{:.2f}".format(interest_penalty_info['interest']['value'])
            
            boleto_data['juros'] = juros_config
            
            # 🚨 DEBUG LOG TEMPORÁRIO
            _logger.info("🔍 DEBUG - Juros config adicionado: %s", juros_config)
        else:
            # 🚨 DEBUG LOG TEMPORÁRIO
            _logger.info("🔍 DEBUG - JUROS NÃO adicionado - Código: %s", interest_penalty_info['interest']['code'])
        
        # === ADICIONA INFORMAÇÕES DE MULTA (SE CONFIGURADO) ===
        if interest_penalty_info['penalty']['code'] and interest_penalty_info['penalty']['code'] != '03':  # Não é isento
            # 🚨 DEBUG LOG TEMPORÁRIO
            _logger.info("🔍 DEBUG - Adicionando MULTA ao boleto_data")
            
            from datetime import timedelta
            data_inicio_multa = self.invoice_date_due + timedelta(days=interest_penalty_info['penalty']['date_start'])
            
            multa_config = {
                'codigo_tipo_multa': interest_penalty_info['penalty']['code'],
                'data_multa': data_inicio_multa.strftime('%Y-%m-%d')
            }
            
            # Adiciona valor ou percentual dependendo do tipo
            if interest_penalty_info['penalty']['code'] == '01':  # Valor Fixo
                multa_config['valor_multa'] = "{:.2f}".format(interest_penalty_info['penalty']['value'])
            elif interest_penalty_info['penalty']['code'] == '02':  # Percentual
                # Formata percentual como string de 12 dígitos sem decimais
                # Exemplo: 2.0% = 200000000000 (2.0 * 100 * 1000000000)
                percentual_formatado = "{:012.0f}".format(interest_penalty_info['penalty']['percent'] * 10000000000)
                multa_config['percentual_multa'] = percentual_formatado
            
            boleto_data['multa'] = multa_config
            
            # 🚨 DEBUG LOG TEMPORÁRIO
            _logger.info("🔍 DEBUG - Multa config adicionada: %s", multa_config)
        else:
            # 🚨 DEBUG LOG TEMPORÁRIO
            _logger.info("🔍 DEBUG - MULTA NÃO adicionada - Código: %s", interest_penalty_info['penalty']['code'])
        
        # === ADICIONA INFORMAÇÕES DE DESCONTO (SE CONFIGURADO) ===
        if discount_info:
            # 🚨 DEBUG LOG TEMPORÁRIO
            _logger.info("🔍 DEBUG - Adicionando DESCONTO ao boleto_data: %s", discount_info)
            
            boleto_data['desconto'] = discount_info
        else:
            # 🚨 DEBUG LOG TEMPORÁRIO
            _logger.info("🔍 DEBUG - DESCONTO NÃO adicionado - Info vazia")
        
        # 🚨 DEBUG LOG TEMPORÁRIO - BOLETO_DATA FINAL
        _logger.info("🔍 DEBUG - boleto_data FINAL: %s", boleto_data)
        
        return boleto_data
    
    def _create_boleto_record_from_api_response(self):
        """
        Processa a resposta da API do Itaú e cria o registro move.boleto
        """
        self.ensure_one()
        
        # Verifica se há uma resposta JSON válida
        if not self.itau_boleto_json_response:
            raise UserError(_("A resposta da API (JSON Recebido) está vazia. Não é possível registrar o boleto."))

        try:
            response_data = json.loads(self.itau_boleto_json_response)
        except json.JSONDecodeError:
            raise UserError(_("Erro: Não foi possível decodificar a resposta JSON da API."))
        
        # Verifica se a resposta indica sucesso
        if response_data.get('etapa_processo_boleto') == 'efetivacao':
            
            # Gera o "Nosso Número" se ainda não existir
            if not self.l10n_br_is_own_number:
                own_number = self.env['ir.sequence'].next_by_code('itau.nosso.numero')
                self.write({'l10n_br_is_own_number': own_number})

            # Extrai dados do boleto da resposta
            dados_boleto_individual = response_data.get('dados_individuais_boleto', [{}])[0]

            # Prepara os valores para criação do registro move.boleto
            boleto_vals = {
                'invoice_id': self.id,
                'l10n_br_is_barcode': dados_boleto_individual.get('codigo_barras', ''),
                'l10n_br_is_barcode_formatted': dados_boleto_individual.get('numero_linha_digitavel', ''),
                'data_limite_pagamento': dados_boleto_individual.get('data_limite_pagamento') or self.invoice_date_due,
                # A data de emissão já tem default no modelo, então não é obrigatória aqui
            }
            
            # Lógica para o ID do Boleto no Itaú: Prioriza API, fallback para UUID
            api_boleto_id = response_data.get('id_boleto')
            if api_boleto_id and api_boleto_id.strip():
                # Se a API retornou um ID válido, usar esse valor
                boleto_vals['itau_boleto_id'] = api_boleto_id.strip()
            else:
                # Se a API não retornou ID, gerar UUID como fallback
                boleto_vals['itau_boleto_id'] = str(uuid.uuid4())

            # Verifica se já existe um boleto para esta fatura
            existing_boleto = self.env['move.boleto'].search([('invoice_id', '=', self.id)], limit=1)
            
            if existing_boleto:
                # Atualiza o boleto existente
                existing_boleto.write(boleto_vals)
            else:
                # Cria um novo registro
                self.env['move.boleto'].create(boleto_vals)
                
        else:
            # Caso a API retorne um erro ou status inesperado
            mensagem_erro = response_data.get('mensagem_retorno', 'Erro desconhecido retornado pela API.')
            raise UserError(_("Falha ao registrar boleto no Itaú: %s") % mensagem_erro)
    
    def action_generate_itau_boleto(self):
        """
        Gera o boleto Itaú para a fatura, criando o "Nosso Número" e o registro move.boleto
        """
        for move in self:
            # --- VALIDAÇÕES INICIAIS ---
            if not move.partner_bank_id:
                raise UserError(_("O campo 'Banco Destinatário' é obrigatório para emitir um boleto."))
            
            journal = move.partner_bank_id.journal_id
            if not journal:
                raise UserError(_("A conta bancária selecionada não está associada a um Diário. Verifique a configuração do Banco Destinatário."))
            
            # Validações das configurações do diário correto
            if not journal.itau_wallet_code:
                raise UserError(_("Configure o 'Código da Carteira' no diário do banco (%s).") % journal.name)
            if not journal.l10n_br_is_payment_mode_id:
                raise UserError(_("Configure a 'Espécie do Título' no diário do banco (%s).") % journal.name)
            
            if not move.l10n_br_is_own_number:
                own_number = self.env['ir.sequence'].next_by_code('itau.nosso.numero')
                move.write({'l10n_br_is_own_number': own_number})
            
            # Chama a função principal de emissão de boleto
            move.action_emitir_boleto_itau()
        return True 

    def test_multiple_discounts(self):
        """
        Método de teste para demonstrar o novo sistema de múltiplos descontos
        """
        self.ensure_one()
        
        if not self.invoice_payment_term_id:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('❌ Erro'),
                    'message': _('Esta fatura não possui termo de pagamento configurado.'),
                    'type': 'danger',
                    'sticky': True,
                }
            }
        
        payment_term = self.invoice_payment_term_id
        
        # Verifica se usa novo sistema
        has_new_system = hasattr(payment_term, 'discount_line_ids') and payment_term.discount_line_ids
        
        if has_new_system:
            # Testa geração de estrutura de desconto
            discount_data = payment_term.get_itau_discount_data(self.invoice_date)
            
            mensagem = f"""💰 NOVO SISTEMA DE DESCONTOS DETECTADO
            
🏷️ TERMO DE PAGAMENTO: {payment_term.name}
📋 Tipo de Desconto: {dict(payment_term._fields['itau_discount_code'].selection)[payment_term.itau_discount_code]}
📊 Quantidade de Linhas: {len(payment_term.discount_line_ids)}

📅 CONDIÇÕES CONFIGURADAS:"""
            
            for line in payment_term.discount_line_ids.sorted('days'):
                if payment_term.itau_discount_code in ['02', '90']:
                    mensagem += f"\n• {line.days} dias: {line.value}% de desconto"
                else:
                    mensagem += f"\n• {line.days} dias: R$ {line.value:.2f} de desconto"
            
            mensagem += f"""

🔧 ESTRUTURA JSON GERADA:
{discount_data}

📝 INSTRUÇÕES:
• Para editar: Vá em Faturamento > Configuração > Termos de Pagamento
• Abra o termo '{payment_term.name}'
• Acesse a aba '💰 Condições de Desconto'"""
            
            title = "✅ Sistema de Múltiplos Descontos Ativo"
            msg_type = 'success'
            
        else:
            mensagem = f"""⚠️ SISTEMA ANTIGO DE DESCONTOS
            
🏷️ TERMO DE PAGAMENTO: {payment_term.name}
📋 Status: Usando sistema original do Odoo

📝 PARA ATIVAR O NOVO SISTEMA:
1. Vá em Faturamento > Configuração > Termos de Pagamento
2. Abra o termo '{payment_term.name}'
3. Selecione um 'Tipo de Desconto (Itaú)' diferente de 'Sem Desconto'
4. Configure as condições na aba '💰 Condições de Desconto'

✨ BENEFÍCIOS DO NOVO SISTEMA:
• Múltiplos descontos escalonados
• Compatibilidade total com API Itaú
• Validações automáticas
• Formatação correta dos valores"""
            
            title = "⚠️ Sistema Antigo em Uso"
            msg_type = 'warning'
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _(title),
                'message': _(mensagem),
                'type': msg_type,
                'sticky': True,
            }
        }

    def debug_journal_config(self):
        """
        Método de debug para verificar configurações do diário
        """
        self.ensure_one()
        
        if not self.partner_bank_id:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('❌ Erro'),
                    'message': _('Nenhuma conta bancária (Banco Destinatário) configurada.'),
                    'type': 'danger',
                    'sticky': True,
                }
            }
        
        journal = self.partner_bank_id.journal_id
        if not journal:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('❌ Erro'),
                    'message': _('A conta bancária não está associada a um diário.'),
                    'type': 'danger',
                    'sticky': True,
                }
            }
        
        mensagem = f"""🏦 BANCO DESTINATÁRIO:
• Banco: {self.partner_bank_id.display_name}
• Diário: {journal.name}
• ID Diário: {journal.id}
• Código Carteira: {journal.itau_wallet_code or 'NÃO CONFIGURADO'}

🤝 CLIENTE (partner_id):
• Nome: {self.partner_id.name}
• ID: {self.partner_id.id}
• Juros: {self.partner_id.payment_interest_code or 'NÃO CONFIGURADO'} ({self.partner_id.payment_interest_percent}%)
• Multa: {self.partner_id.payment_penalty_code or 'NÃO CONFIGURADO'} ({self.partner_id.payment_penalty_percent}%)

⚙️ DIÁRIO (via partner_bank_id):
• Juros: {journal.payment_interest_code or 'NÃO CONFIGURADO'} ({journal.payment_interest_percent}%)
• Multa: {journal.payment_penalty_code or 'NÃO CONFIGURADO'} ({journal.payment_penalty_percent}%)

🔄 RESULTADO DA FUNÇÃO _get_payment_interest_penalty_info():"""
        
        try:
            info = self._get_payment_interest_penalty_info()
            mensagem += f"""
• Juros Final: {info['interest']['code'] or 'VAZIO'} ({info['interest']['percent']}%)
• Multa Final: {info['penalty']['code'] or 'VAZIO'} ({info['penalty']['percent']}%)"""
        except Exception as e:
            mensagem += f"\n❌ ERRO: {str(e)}"
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('🔍 Debug Journal'),
                'message': _(mensagem),
                'type': 'info',
                'sticky': True,
            }
        }

    def demo_payment_config_usage(self):
        """
        Método de demonstração para mostrar como usar as configurações de juros, multa e desconto.
        
        Este método pode ser chamado para testar a lógica de fallback e ver como os dados
        são estruturados para a API do Itaú.
        """
        self.ensure_one()
        
        # Obtém informações de juros e multa
        info = self._get_payment_interest_penalty_info()
        
        # Obtém informações de desconto
        discount_info = self._get_discount_info_from_payment_terms()
        
        # Obtém dados completos do boleto (igual ao que seria enviado para API)
        try:
            boleto_data = self._get_boleto_data_from_invoice()
            
            # Formata resposta para demonstração
            resultado = {
                'configuracoes_encontradas': {
                    'juros': {
                        'codigo': info['interest']['code'],
                        'percentual': info['interest']['percent'],
                        'valor': info['interest']['value'],
                        'dias_inicio': info['interest']['date_start']
                    },
                    'multa': {
                        'codigo': info['penalty']['code'],
                        'percentual': info['penalty']['percent'],
                        'valor': info['penalty']['value'],
                        'dias_inicio': info['penalty']['date_start']
                    },
                    'desconto': discount_info
                },
                'estrutura_final_api': boleto_data
            }
            
            # Prepara mensagem
            mensagem_partes = []
            
            # Informações de juros
            if info['interest']['code']:
                if info['interest']['code'] == '05':
                    mensagem_partes.append("• Juros: ISENTO (05)")
                else:
                    if info['interest']['code'] in ['90', '91', '92']:
                        mensagem_partes.append(f"• Juros: {info['interest']['code']} ({info['interest']['percent']}%)")
                    else:
                        mensagem_partes.append(f"• Juros: {info['interest']['code']} (R$ {info['interest']['value']})")
            else:
                mensagem_partes.append("• Juros: Não configurado")
            
            # Informações de multa
            if info['penalty']['code']:
                if info['penalty']['code'] == '03':
                    mensagem_partes.append("• Multa: ISENTA (03)")
                else:
                    if info['penalty']['code'] == '02':
                        mensagem_partes.append(f"• Multa: {info['penalty']['code']} ({info['penalty']['percent']}%)")
                    else:
                        mensagem_partes.append(f"• Multa: {info['penalty']['code']} (R$ {info['penalty']['value']})")
            else:
                mensagem_partes.append("• Multa: Não configurada")
            
            # Informações de desconto
            if discount_info:
                desconto_count = len(discount_info.get('descontos', []))
                mensagem_partes.append(f"• Desconto: {desconto_count} configuração(ões)")
            else:
                mensagem_partes.append("• Desconto: Não configurado")
            
            # Verifica se vai aparecer no JSON final
            json_include_info = []
            if boleto_data.get('juros'):
                json_include_info.append("✅ JUROS será incluído no JSON")
            else:
                json_include_info.append("❌ JUROS NÃO será incluído no JSON")
                
            if boleto_data.get('multa'):
                json_include_info.append("✅ MULTA será incluída no JSON")
            else:
                json_include_info.append("❌ MULTA NÃO será incluída no JSON")
                
            if boleto_data.get('desconto'):
                json_include_info.append("✅ DESCONTO será incluído no JSON")
            else:
                json_include_info.append("❌ DESCONTO NÃO será incluído no JSON")
            
            mensagem_completa = (
                "Configurações encontradas:\n" + 
                "\n".join(mensagem_partes) + 
                "\n\n⚙️ STATUS PARA API:\n" +
                "\n".join(json_include_info)
            )
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('🔍 Configurações de Pagamento'),
                    'message': _(mensagem_completa),
                    'type': 'info',
                    'sticky': True,
                }
            }
        
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('❌ Erro'),
                    'message': _(f'Erro ao obter configurações: {str(e)}'),
                    'type': 'danger',
                    'sticky': True,
                }
            } 