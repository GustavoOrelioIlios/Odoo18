# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime
import json

# Importação dos modelos Pydantic para validação
from .pydantic_models import ValidadorBoleto, ValidadorBeneficiario


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
            
            # Notificação de sucesso na tela
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('✅ Boleto Emitido!'),
                    'message': _('Boleto Itaú emitido com sucesso. Verifique os detalhes na aba "Boleto Itaú".'),
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
    
    def _get_pagador_data_from_invoice(self):
        """
        Extrai dados do pagador (cliente) da fatura
        """
        partner = self.partner_id
        
        # Determina endereço (faturamento tem prioridade)
        endereco_cobranca = partner
        if hasattr(partner, 'child_ids'):
            endereco_faturamento = partner.child_ids.filtered(lambda c: c.type == 'invoice')
            if endereco_faturamento:
                endereco_cobranca = endereco_faturamento[0]
        
        pagador_data = {
            'nome_pagador': partner.name or '',
            'logradouro': endereco_cobranca.street or '',
            'bairro': endereco_cobranca.street2 or '',
            'cidade': endereco_cobranca.city or '',
            'uf': endereco_cobranca.state_id.code if endereco_cobranca.state_id else '',
            'cep': endereco_cobranca.zip or '',
            'telefone': partner.phone or partner.mobile or '',
            'email': partner.email or '',
        }
        
        # Adiciona documento (CPF/CNPJ)
        if partner.vat:
            if partner.is_company:
                pagador_data['cnpj'] = partner.vat
            else:
                pagador_data['cpf'] = partner.vat
        
        return pagador_data
    
    def _get_boleto_data_from_invoice(self):
        """
        Extrai dados específicos do boleto da fatura
        """
        boleto_data = {
            'dados_individuais_boleto': [{
                'valor_titulo': str(self.amount_total),
                'id_boleto_individual': f"inv-{self.id}-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                'situacao_geral_boleto': 'Em Aberto',
                'status_vencimento': 'a vencer',
                'numero_nosso_numero': f"{self.id:08d}",
                'data_vencimento': self.invoice_date_due.strftime('%Y-%m-%d') if self.invoice_date_due else datetime.now().strftime('%Y-%m-%d'),
                'texto_seu_numero': self.name or '',
                'data_limite_pagamento': self.invoice_date_due.strftime('%Y-%m-%d') if self.invoice_date_due else datetime.now().strftime('%Y-%m-%d'),
                'texto_uso_beneficiario': f"Fatura {self.name}" if self.name else 'Fatura',
            }],
            'codigo_especie': '01',
            'tipo_boleto': 'proposta',
            'codigo_carteira': '112',
            'codigo_aceite': 'S',
            'data_emissao': self.invoice_date.strftime('%Y-%m-%d') if self.invoice_date else datetime.now().strftime('%Y-%m-%d')
        }
        
        return boleto_data 