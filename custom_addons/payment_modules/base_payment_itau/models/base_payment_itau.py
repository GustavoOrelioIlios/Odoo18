# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import requests
import json
import logging
import uuid
from datetime import datetime

_logger = logging.getLogger(__name__)


class BasePaymentItau(models.Model):
    _inherit = 'base.payment.api'

    @api.model
    def _get_integracao_selection(self):
        """Adiciona opção Itaú às integrações disponíveis"""
        options = super()._get_integracao_selection()
        options.append(('itau_boleto', 'Itaú Boleto'))
        return options

    def _get_oauth_token(self):
        """Gera token OAuth2 do Itaú"""
        self.ensure_one()
        
        try:
            oauth_url = self.get_api_url('oauth')
            
            payload = {
                'grant_type': 'client_credentials',
                'client_id': self.client_id,
                'client_secret': self.client_secret
            }
            
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded',
                'User-Agent': 'Odoo-Itau-Integration'
            }
            
            response = requests.post(oauth_url, headers=headers, data=payload, timeout=self.timeout)
            
            if response.status_code == 200:
                token_data = response.json()
                return token_data.get('access_token'), response.text
            else:
                raise Exception(f"Erro na autenticação: {response.status_code} - {response.text}")
                
        except Exception as e:
            _logger.error('Erro ao gerar token OAuth: %s', str(e))
            raise

    def testar_token(self):
        """Implementação específica do teste de token para o Itaú"""
        for record in self:
            if record.integracao == 'itau_boleto':
                try:
                    # Testa gerar token OAuth
                    token, full_response = record._get_oauth_token()
                    
                    record._update_connection_status(True, token=token)
                    
                    # SEM MODAL - APENAS LOG E RETORNO COM REFRESH
                    _logger.info('Token OAuth2 gerado com sucesso para %s', record.name)
                    
                    # FORÇA ATUALIZAÇÃO DA VIEW E CHATTER
                    return record._refresh_view()
                    
                except Exception as e:
                    record._update_connection_status(False, str(e))
                    
                    # SEM MODAL - APENAS LOG E NOTIFICAÇÃO COM REFRESH
                    _logger.error('Erro na geração do token para %s: %s', record.name, str(e))
                    
                    # FORÇA ATUALIZAÇÃO DA VIEW E CHATTER
                    return record._refresh_view()
            else:
                # Chama método pai para outras integrações
                return super().testar_token()

    # MÉTODOS DE TESTE POST BOLETO - COMENTADOS
    # def action_test_post_boleto(self):
    #     """Testar criação de boleto no Itaú"""
    #     for record in self:
    #         if record.integracao != 'itau_boleto':
    #             raise ValidationError(_('Esta funcionalidade é específica para integração Itaú'))
    #             
    #         try:
    #             # Gera token
    #             token, _ = record._get_oauth_token()
    #             
    #             url = record.get_api_url('boletos')
    #             correlation_id = str(uuid.uuid4())
    #             
    #             # Payload simplificado para teste
    #             payload = {
    #                 "beneficiario": {
    #                     "id_beneficiario": "150000052061",
    #                     "nome_cobranca": "Teste Odoo Integração",
    #                     "tipo_pessoa": {
    #                         "codigo_tipo_pessoa": "J",
    #                         "numero_cadastro_nacional_pessoa_juridica": "12345678901234"
    #                     },
    #                     "endereco": {
    #                         "nome_logradouro": "Rua Teste, 123",
    #                         "nome_bairro": "Centro",
    #                         "nome_cidade": "São Paulo",
    #                         "sigla_UF": "SP",
    #                         "numero_CEP": "01234567"
    #                     }
    #                 },
    #                 "dado_boleto": {
    #                     "pagador": {
    #                         "id_pagador": str(uuid.uuid4()),
    #                         "pessoa": {
    #                             "nome_pessoa": "Cliente Teste",
    #                             "tipo_pessoa": {
    #                                 "codigo_tipo_pessoa": "F",
    #                                 "numero_cadastro_pessoa_fisica": "12345678901"
    #                             }
    #                         },
    #                         "endereco": {
    #                             "nome_logradouro": "Rua Cliente, 456",
    #                             "nome_bairro": "Vila Teste",
    #                             "nome_cidade": "São Paulo",
    #                             "sigla_UF": "SP",
    #                             "numero_CEP": "01234567"
    #                         },
    #                         "texto_endereco_email": "teste@teste.com"
    #                     },
    #                     "dados_individuais_boleto": [{
    #                         "valor_titulo": "100.00",
    #                         "id_boleto_individual": str(uuid.uuid4()),
    #                         "numero_nosso_numero": "12345678",
    #                         "data_vencimento": "2025-12-31",
    #                         "texto_seu_numero": "123"
    #                     }],
    #                     "codigo_especie": "01",
    #                     "descricao_instrumento_cobranca": "boleto",
    #                     "tipo_boleto": "proposta",
    #                     "codigo_carteira": "112",
    #                     "codigo_aceite": "S",
    #                     "data_emissao": datetime.now().strftime("%Y-%m-%d")
    #                 },
    #                 "etapa_processo_boleto": "validacao",
    #                 "codigo_canal_operacao": "BKL"
    #             }
    #             
    #             headers = {
    #                 'x-itau-apikey': record.client_id,
    #                 'x-itau-correlationID': correlation_id,
    #                 'Content-Type': 'application/json',
    #                 'Accept': 'application/json',
    #                 'Authorization': f'Bearer {token}'
    #             }
    #             
    #             response = requests.post(url, headers=headers, json=payload, timeout=record.timeout)
    #             
    #             # REGISTRO NO CHATTER
    #             success = response.status_code in [200, 201]
    #             if success:
    #                 record.message_post(
    #                     body=f"📄 Teste POST Boleto executado com sucesso - Status: {response.status_code}<br/>"
    #                          f"Correlation ID: {correlation_id}",
    #                     message_type='notification'
    #                 )
    #             else:
    #                 record.message_post(
    #                     body=f"⚠️ Teste POST Boleto retornou status: {response.status_code}<br/>"
    #                          f"Correlation ID: {correlation_id}<br/>"
    #                          f"Resposta: {response.text[:200]}...",
    #                     message_type='notification'
    #                 )
    #             
    #             # SEM MODAL - APENAS LOG E NOTIFICAÇÃO
    #             if success:
    #                 _logger.info('Teste POST boleto executado com sucesso - Status: %s', response.status_code)
    #                 return {
    #                     'type': 'ir.actions.client',
    #                     'tag': 'display_notification',
    #                     'params': {
    #                         'type': 'success',
    #                         'message': f'Teste POST boleto concluído - Status: {response.status_code}',
    #                         'sticky': False,
    #                     }
    #                 }
    #             else:
    #                 _logger.warning('Teste POST boleto retornou status: %s - %s', response.status_code, response.text)
    #                 return {
    #                     'type': 'ir.actions.client',
    #                     'tag': 'display_notification',
    #                     'params': {
    #                         'type': 'warning',
    #                         'message': f'Teste POST boleto - Status: {response.status_code}',
    #                         'sticky': False,
    #                     }
    #                 }
    #                 
    #         except Exception as e:
    #             # REGISTRO DE ERRO NO CHATTER
    #             record.message_post(
    #                 body=f"❌ Erro no teste POST Boleto: {str(e)}",
    #                 message_type='notification'
    #             )
    #             
    #             _logger.error('Erro ao testar POST boleto: %s', str(e))
    #             return {
    #                 'type': 'ir.actions.client',
    #                 'tag': 'display_notification',
    #                 'params': {
    #                     'type': 'danger',
    #                     'message': f'Erro no teste POST boleto: {str(e)}',
    #                     'sticky': False,
    #                 }
    #             }

    # MÉTODOS DE TESTE GET BOLETO - COMENTADOS  
    # def action_test_get_boleto(self):
    #     """Testar consulta de boleto no Itaú"""
    #     for record in self:
    #         if record.integracao != 'itau_boleto':
    #             raise ValidationError(_('Esta funcionalidade é específica para integração Itaú'))
    #             
    #         try:
    #             # Gera token
    #             token, _ = record._get_oauth_token()
    #             
    #             # Parâmetros de teste
    #             params = {
    #                 'id_beneficiario': '150000052061',
    #                 'nosso_numero': '00001056',
    #                 'codigo_carteira': '157',
    #                 'data_inclusao': datetime.now().strftime("%Y-%m-%d")
    #             }
    #             
    #             url = record.get_api_url('boletos_consulta')
    #             correlation_id = str(uuid.uuid4())
    #             
    #             headers = {
    #                 'x-itau-apikey': record.client_id,
    #                 'x-itau-correlationID': correlation_id,
    #                 'Accept': 'application/json',
    #                 'Authorization': f'Bearer {token}'
    #             }
    #             
    #             response = requests.get(url, headers=headers, params=params, timeout=record.timeout)
    #             
    #             # REGISTRO NO CHATTER
    #             success = response.status_code == 200
    #             if success:
    #                 record.message_post(
    #                     body=f"🔍 Teste GET Boleto executado com sucesso - Status: {response.status_code}<br/>"
    #                          f"Correlation ID: {correlation_id}<br/>"
    #                          f"Parâmetros: {params}",
    #                     message_type='notification'
    #                 )
    #             else:
    #                 record.message_post(
    #                     body=f"⚠️ Teste GET Boleto retornou status: {response.status_code}<br/>"
    #                          f"Correlation ID: {correlation_id}<br/>"
    #                          f"Parâmetros: {params}<br/>"
    #                          f"Resposta: {response.text[:200]}...",
    #                     message_type='notification'
    #                 )
    #             
    #             # SEM MODAL - APENAS LOG E NOTIFICAÇÃO
    #             if success:
    #                 _logger.info('Teste GET boleto executado com sucesso - Status: %s', response.status_code)
    #                 return {
    #                     'type': 'ir.actions.client',
    #                     'tag': 'display_notification',
    #                     'params': {
    #                         'type': 'success',
    #                         'message': f'Teste GET boleto concluído - Status: {response.status_code}',
    #                         'sticky': False,
    #                     }
    #                 }
    #             else:
    #                 _logger.warning('Teste GET boleto retornou status: %s - %s', response.status_code, response.text)
    #                 return {
    #                     'type': 'ir.actions.client',
    #                     'tag': 'display_notification',
    #                     'params': {
    #                         'type': 'warning',
    #                         'message': f'Teste GET boleto - Status: {response.status_code}',
    #                         'sticky': False,
    #                     }
    #                 }
    #                 
    #         except Exception as e:
    #             # REGISTRO DE ERRO NO CHATTER
    #             record.message_post(
    #                 body=f"❌ Erro no teste GET Boleto: {str(e)}",
    #                 message_type='notification'
    #             )
    #             
    #             _logger.error('Erro ao testar GET boleto: %s', str(e))
    #             return {
    #                 'type': 'ir.actions.client',
    #                 'tag': 'display_notification',
    #                 'params': {
    #                     'type': 'danger',
    #                     'message': f'Erro no teste GET boleto: {str(e)}',
    #                     'sticky': False,
    #                 }
    #             }

    def get_api_url(self, endpoint):
        """Constrói URL completa para endpoints específicos do Itaú"""
        self.ensure_one()
        
        if self.integracao == 'itau_boleto':
            # Mapeamento das rotas do Itaú
            routes = {
                'oauth': '/api/oauth/jwt',
                'boletos': '/itau-ep9-gtw-cash-management-ext-v2/v2/boletos',
                'boletos_consulta': '/itau-ep9-gtw-cash-management-ext-v2/v2/boletos',
                'cash_management': '/itau-ep9-gtw-cash-management-ext-v2/v2',
            }
            
            if endpoint not in routes:
                raise ValueError(f"Endpoint '{endpoint}' não suportado para Itaú. Disponíveis: {list(routes.keys())}")
                
            return f"{self.base_url}{routes[endpoint]}"
        else:
            # Chama método pai para outras integrações
            return super().get_api_url(endpoint) 