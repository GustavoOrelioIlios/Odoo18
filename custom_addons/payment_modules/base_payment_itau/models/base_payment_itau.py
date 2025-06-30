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

    # =============================
    # CAMPOS ESPECÍFICOS DO ITAÚ
    # =============================
    
    # Campo para vincular a uma conta bancária específica
    partner_bank_id = fields.Many2one(
        'res.partner.bank',
        string='Conta Bancária Beneficiário',
        help='Conta bancária do beneficiário com dados específicos do Itaú configurados'
    )

    # Adiciona opção Itaú às integrações disponíveis usando selection_add
    integracao = fields.Selection(
        selection_add=[('itau_boleto', 'Itaú - Boleto')],
        ondelete={'itau_boleto': 'cascade'}
    )
    
    # Campos para armazenar JSONs de teste
    test_json_enviado = fields.Text(
        string='JSON Enviado (Último Teste)',
        readonly=True,
        help='JSON que foi enviado na última requisição de teste POST'
    )
    
    test_json_retorno = fields.Text(
        string='JSON Retorno (Último Teste)', 
        readonly=True,
        help='JSON retornado pela API Itaú na última requisição de teste POST'
    )

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
    
    # =============================
    # MÉTODOS QUE USAM RES.PARTNER.BANK
    # =============================
    
    def get_beneficiario_data_from_bank(self):
        """
        Obtém dados do beneficiário a partir da conta bancária configurada
        
        Returns:
            dict: Dados do beneficiário no formato da API Itaú
        """
        self.ensure_one()
        
        if not self.partner_bank_id:
            raise ValidationError(_('É necessário configurar uma Conta Bancária Beneficiário para usar os dados específicos do Itaú.'))
        
        # Usa o método do res.partner.bank que implementa a lógica de fallback
        return self.partner_bank_id.get_itau_beneficiario_data()
    
    def create_boleto_payload_with_bank_data(self, pagador_data, boleto_data):
        """
        Cria payload completo para criação de boleto usando dados da conta bancária
        
        Args:
            pagador_data (dict): Dados do pagador
            boleto_data (dict): Dados específicos do boleto
            
        Returns:
            dict: Payload completo para API do Itaú
        """
        self.ensure_one()
        
        # Obtém dados do beneficiário da conta bancária
        beneficiario_data = self.get_beneficiario_data_from_bank()
        
        # Monta payload completo
        payload = {
            'beneficiario': beneficiario_data,
            'dado_boleto': {
                'pagador': pagador_data,
                'dados_individuais_boleto': boleto_data.get('dados_individuais_boleto', []),
                'codigo_especie': boleto_data.get('codigo_especie'),
                'descricao_instrumento_cobranca': 'boleto',
                'tipo_boleto': boleto_data.get('tipo_boleto', 'proposta'),
                'codigo_carteira': boleto_data.get('codigo_carteira'),
                'codigo_aceite': boleto_data.get('codigo_aceite', 'S'),
                'data_emissao': boleto_data.get('data_emissao', datetime.now().strftime("%Y-%m-%d"))
            },
            'etapa_processo_boleto': 'validacao',
            'codigo_canal_operacao': 'BKL'
        }
        
        return payload
    
    def action_test_post_boleto_with_bank_data(self):
        """
        Testa criação de boleto usando dados da conta bancária configurada
        Com payload completo baseado no JSON fornecido pelo usuário
        """
        self.ensure_one()
        
        if self.integracao != 'itau_boleto':
            raise ValidationError(_('Esta funcionalidade é específica para integração Itaú'))
        
        if not self.partner_bank_id:
            raise ValidationError(_('Configure uma Conta Bancária Beneficiário primeiro.'))
            
        try:
            # Gera token
            token, _ = self._get_oauth_token()
            
            url = self.get_api_url('boletos')
            correlation_id = str(uuid.uuid4())
            
            # Obtém dados do beneficiário dos campos configurados
            beneficiario_data = self.get_beneficiario_data_from_bank()
            
            # Payload completo baseado no JSON fornecido pelo usuário
            # Apenas os dados do beneficiário são obtidos dos campos configurados
            payload = {
                "beneficiario": beneficiario_data,  # <- DADOS DOS CAMPOS CONFIGURADOS
                "dado_boleto": {
                    "pagador": {
                        "id_pagador": "298AFB64-F607-454E-8FC9-4765B70B7828",
                        "pessoa": {
                            "nome_pessoa": "Antônio Coutinho",
                            "nome_fantasia": "Empresa A",
                            "tipo_pessoa": {
                                "codigo_tipo_pessoa": "J",
                                "numero_cadastro_pessoa_fisica": "12345678901",
                                "numero_cadastro_nacional_pessoa_juridica": "12345678901234"
                            }
                        },
                        "endereco": {
                            "nome_logradouro": "rua dona ana neri, 368",
                            "nome_bairro": "Mooca",
                            "nome_cidade": "Sao Paulo",
                            "sigla_UF": "SP",
                            "numero_CEP": "12345678"
                        },
                        "texto_endereco_email": "itau@itau-unibanco.com.br"
                    },
                    "dados_individuais_boleto": [
                        {
                            "valor_titulo": "180.00",
                            "id_boleto_individual": "b1ff5cc0-8a9c-497e-b983-738904c23389",
                            "situacao_geral_boleto": "Em Aberto",
                            "status_vencimento": "a vencer",
                            "numero_nosso_numero": "12345678",
                            "data_vencimento": "2000-01-01",
                            "texto_seu_numero": "123",
                            "codigo_barras": "34101234567890123456789012345678901234567890",
                            "numero_linha_digitavel": "34101234567890123456789012345678901234567890123",
                            "data_limite_pagamento": "2000-01-01",
                            "texto_uso_beneficiario": "abc123abc123abc123"
                        },
                        {
                            "valor_titulo": "180.00",
                            "id_boleto_individual": "b1ff5cc0-8a9c-497e-b983-738904c23389",
                            "situacao_geral_boleto": "Em Aberto",
                            "status_vencimento": "a vencer",
                            "numero_nosso_numero": "12345678",
                            "data_vencimento": "2000-01-01",
                            "texto_seu_numero": "123",
                            "codigo_barras": "34101234567890123456789012345678901234567890",
                            "numero_linha_digitavel": "34101234567890123456789012345678901234567890123",
                            "data_limite_pagamento": "2000-01-01",
                            "texto_uso_beneficiario": "abc123abc123abc123"
                        }
                    ],
                    "codigo_especie": "00",  # ATENÇÃO: Altere para o código correto da espécie
                    "descricao_instrumento_cobranca": "boleto",
                    "tipo_boleto": "proposta",
                    "forma_envio": "impressão",
                    "quantidade_parcelas": 2,
                    "protesto": {
                        "codigo_tipo_protesto": 1,
                        "quantidade_dias_protesto": 1,
                        "protesto_falimentar": True
                    },
                    "negativacao": {
                        "codigo_tipo_negativacao": 1,
                        "quantidade_dias_negativacao": 1
                    },
                    "instrucao_cobranca": [
                        {
                            "codigo_instrucao_cobranca": 2,
                            "quantidade_dias_instrucao_cobranca": 10,
                            "dia_util": True
                        },
                        {
                            "codigo_instrucao_cobranca": 2,
                            "quantidade_dias_instrucao_cobranca": 10,
                            "dia_util": True
                        }
                    ],
                    "sacador_avalista": {
                        "pessoa": {
                            "nome_pessoa": "Antônio Coutinho",
                            "nome_fantasia": "Empresa A",
                            "tipo_pessoa": {
                                "codigo_tipo_pessoa": "J",
                                "numero_cadastro_pessoa_fisica": "12345678901",
                                "numero_cadastro_nacional_pessoa_juridica": "12345678901234"
                            }
                        },
                        "endereco": {
                            "nome_logradouro": "rua dona ana neri, 368",
                            "nome_bairro": "Mooca",
                            "nome_cidade": "Sao Paulo",
                            "sigla_UF": "SP",
                            "numero_CEP": "12345678"
                        },
                        "exclusao_sacador_avalista": True
                    },
                    "codigo_carteira": "000",  # ATENÇÃO: Altere para o código correto da sua carteira
                    "codigo_tipo_vencimento": 1,
                    "descricao_especie": "BDP Boleto proposta",
                    "codigo_aceite": "S",
                    "data_emissao": "2000-01-01",
                    "pagamento_parcial": True,
                    "quantidade_maximo_parcial": 2,
                    "valor_abatimento": "100.00",
                    "juros": {
                        "codigo_tipo_juros": "90",
                        "quantidade_dias_juros": 1,
                        "valor_juros": "999999999999999.00",
                        "percentual_juros": "000000100000",
                        "data_juros": "2024-09-21"
                    },
                    "multa": {
                        "codigo_tipo_multa": "01",
                        "quantidade_dias_multa": 1,
                        "valor_multa": "999999999999999.00",
                        "percentual_multa": "9999999.00000"
                    },
                    "desconto": {
                        "codigo_tipo_desconto": "01",
                        "descontos": [
                            {
                                "data_desconto": "2024-09-28",
                                "valor_desconto": "999999999999999.00",
                                "percentual_desconto": "9999999.00000"
                            },
                            {
                                "data_desconto": "2024-09-28",
                                "valor_desconto": "999999999999999.00",
                                "percentual_desconto": "9999999.00000"
                            }
                        ],
                        "codigo": "200",
                        "mensagem": "Aguardando aprovação"
                    },
                    "mensagens_cobranca": [
                        {
                            "mensagem": "abc"
                        },
                        {
                            "mensagem": "abc"
                        }
                    ],
                    "recebimento_divergente": {
                        "codigo_tipo_autorizacao": 1,
                        "valor_minimo": "999999999999999.00",
                        "percentual_minimo": "9999999.00000",
                        "valor_maximo": "999999999999999.00",
                        "percentual_maximo": "9999999.00000"
                    },
                    "desconto_expresso": True,
                    "texto_uso_beneficiario": "726351275ABC",
                    "pagamentos_cobranca": [
                        {
                            "codigo_instituicao_financeira_pagamento": "004",
                            "codigo_identificador_sistema_pagamento_brasileiro": "341",
                            "numero_agencia_recebedora": "1501",
                            "codigo_canal_pagamento_boleto_cobranca": "71",
                            "codigo_meio_pagamento_boleto_cobranca": "02",
                            "valor_pago_total_cobranca": "9999999999999.00",
                            "valor_pago_desconto_cobranca": "9999999999999.00",
                            "valor_pago_multa_cobranca": "9999999999999.00",
                            "valor_pago_juro_cobranca": "9999999999999.00",
                            "valor_pago_abatimento_cobranca": "9999999999999.00",
                            "valor_pagamento_imposto_sobre_operacao_financeira": "9999999999999.00",
                            "data_hora_inclusao_pagamento": "2016-02-28T16:41:41.090Z",
                            "data_inclusao_pagamento": "2020-02-28",
                            "descricao_meio_pagamento": "DÉBITO EM CONTA",
                            "descricao_canal_pagamento": "BANKFONE"
                        },
                        {
                            "codigo_instituicao_financeira_pagamento": "004",
                            "codigo_identificador_sistema_pagamento_brasileiro": "341",
                            "numero_agencia_recebedora": "1501",
                            "codigo_canal_pagamento_boleto_cobranca": "71",
                            "codigo_meio_pagamento_boleto_cobranca": "02",
                            "valor_pago_total_cobranca": "9999999999999.00",
                            "valor_pago_desconto_cobranca": "9999999999999.00",
                            "valor_pago_multa_cobranca": "9999999999999.00",
                            "valor_pago_juro_cobranca": "9999999999999.00",
                            "valor_pago_abatimento_cobranca": "9999999999999.00",
                            "valor_pagamento_imposto_sobre_operacao_financeira": "9999999999999.00",
                            "data_hora_inclusao_pagamento": "2016-02-28T16:41:41.090Z",
                            "data_inclusao_pagamento": "2020-02-28",
                            "descricao_meio_pagamento": "DÉBITO EM CONTA",
                            "descricao_canal_pagamento": "BANKFONE"
                        }
                    ],
                    "historico": [
                        {
                            "data": "2020-01-01",
                            "operacao": "Alteração dos dados da cobrança",
                            "comandado_por": "voluptate velit",
                            "conteudo_anterior": "2020-03-03",
                            "conteudo_atual": "2020-04-04",
                            "motivo": "Agência informada não existe",
                            "detalhe": [
                                {
                                    "descricao": "ALTERACAO DATA DESCONTO",
                                    "conteudo_anterior": "2020-03-03",
                                    "conteudo_atual": "2020-04-04"
                                },
                                {
                                    "descricao": "ALTERACAO DATA DESCONTO",
                                    "conteudo_anterior": "2020-03-03",
                                    "conteudo_atual": "2020-04-04"
                                }
                            ]
                        },
                        {
                            "data": "2020-01-01",
                            "operacao": "Alteração dos dados da cobrança",
                            "comandado_por": "ipsum",
                            "conteudo_anterior": "2020-03-03",
                            "conteudo_atual": "2020-04-04",
                            "motivo": "Agência informada não existe",
                            "detalhe": [
                                {
                                    "descricao": "ALTERACAO DATA DESCONTO",
                                    "conteudo_anterior": "2020-03-03",
                                    "conteudo_atual": "2020-04-04"
                                },
                                {
                                    "descricao": "ALTERACAO DATA DESCONTO",
                                    "conteudo_anterior": "2020-03-03",
                                    "conteudo_atual": "2020-04-04"
                                }
                            ]
                        }
                    ],
                    "baixa": {
                        "codigo": "200",
                        "mensagem": "Aguardando aprovação",
                        "campos": [
                            {
                                "campo": "COD-RET",
                                "mensagem": "Processamento efetuado. Aguardando aprovação do gerente",
                                "valor": "occaecat in non proident"
                            },
                            {
                                "campo": "COD-RET",
                                "mensagem": "Processamento efetuado. Aguardando aprovação do gerente",
                                "valor": "minim cupidatat in"
                            }
                        ],
                        "codigo_motivo_boleto_cobranca_baixado": "33",
                        "indicador_dia_util_baixa": "0",
                        "data_hora_inclusao_alteracao_baixa": "2016-02-28T16:41:41.090Z",
                        "codigo_usuario_inclusao_alteracao": "000000001",
                        "data_inclusao_alteracao_baixa": "2016-02-28"
                    }
                },
                "id_boleto": "b1ff5cc0-8a9c-497e-b983-738904c23386",
                "etapa_processo_boleto": "validacao",
                "codigo_canal_operacao": "BKL",
                "acoes_permitidas": {
                    "emitir_segunda_via": True,
                    "comandar_instrucao_alterar_dados_cobranca": False
                }
            }
            
            headers = {
                'x-itau-apikey': self.client_id,
                'x-itau-correlationID': correlation_id,
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'Authorization': f'Bearer {token}'
            }
            
            response = requests.post(url, headers=headers, json=payload, timeout=self.timeout)
            
            # ARMAZENA JSONs NOS CAMPOS
            self.test_json_enviado = json.dumps(payload, indent=2, ensure_ascii=False)
            try:
                # Tenta fazer parse do JSON de resposta
                response_json = response.json()
                self.test_json_retorno = json.dumps(response_json, indent=2, ensure_ascii=False)
            except (ValueError, json.JSONDecodeError):
                # Se não for JSON válido, armazena o texto da resposta
                self.test_json_retorno = f"Status: {response.status_code}\nContent-Type: {response.headers.get('Content-Type', 'N/A')}\n\nResposta:\n{response.text}"
            
            # Registro no chatter
            success = response.status_code in [200, 201]
            bank_info = f"Conta: {self.partner_bank_id.acc_number} - {self.partner_bank_id.partner_id.name}"
            
            if success:
                self.message_post(
                    body=f"📄 Teste POST Boleto (Payload Completo) executado com sucesso - Status: {response.status_code}<br/>"
                         f"Correlation ID: {correlation_id}<br/>"
                         f"{bank_info}<br/>"
                         f"Beneficiário: {beneficiario_data['nome_cobranca']} (ID: {beneficiario_data['id_beneficiario']})",
                    message_type='notification'
                )
            else:
                self.message_post(
                    body=f"⚠️ Teste POST Boleto (Payload Completo) retornou status: {response.status_code}<br/>"
                         f"Correlation ID: {correlation_id}<br/>"
                         f"{bank_info}<br/>"
                         f"Resposta: {response.text[:500]}...",
                    message_type='notification'
                )
            
            _logger.info('Teste POST boleto com payload completo - Status: %s', response.status_code)
            return self._refresh_view()
                
        except Exception as e:
            # ARMAZENA INFORMAÇÕES DE ERRO NOS CAMPOS JSON
            self.test_json_enviado = json.dumps(payload, indent=2, ensure_ascii=False) if 'payload' in locals() else "Erro antes da criação do payload"
            self.test_json_retorno = f"ERRO: {str(e)}\n\nDetalhes: Falha na execução da requisição antes de receber resposta da API."
            
            self.message_post(
                body=f"❌ Erro no teste POST Boleto (Payload Completo): {str(e)}",
                message_type='notification'
            )
            
            _logger.error('Erro ao testar POST boleto com payload completo: %s', str(e))
            return self._refresh_view()
    
    def _emitir_boleto_from_invoice_data(self, beneficiario_data, pagador_data, boleto_data):
        """
        Emite boleto usando dados extraídos da fatura
        
        Args:
            beneficiario_data (dict): Dados do beneficiário (empresa)
            pagador_data (dict): Dados do pagador (cliente da fatura)
            boleto_data (dict): Dados específicos do boleto
            
        Returns:
            dict: Resposta da API do Itaú
        """
        self.ensure_one()
        
        # Gera token OAuth2
        token, _ = self._get_oauth_token()
        
        # Monta payload completo com estrutura corrigida
        payload = {
            'beneficiario': beneficiario_data,
            'dado_boleto': {
                'codigo_carteira': boleto_data.get('codigo_carteira'),
                'codigo_especie': boleto_data.get('codigo_especie'),
                'descricao_especie': boleto_data.get('descricao_especie'),
                'descricao_instrumento_cobranca': boleto_data.get('descricao_instrumento_cobranca'),
                'codigo_aceite': boleto_data.get('codigo_aceite', 'S'),
                'tipo_boleto': boleto_data.get('tipo_boleto', 'proposta'),
                'data_emissao': boleto_data.get('data_emissao'),
                'pagador': pagador_data,
                'dados_individuais_boleto': boleto_data.get('dados_individuais_boleto', [])
            },
            'etapa_processo_boleto': 'validacao',
            'codigo_canal_operacao': 'BKL'
        }
        
        # === ADICIONA INFORMAÇÕES DE JUROS (SE CONFIGURADO) ===
        if boleto_data.get('juros'):
            payload['dado_boleto']['juros'] = boleto_data['juros']
        
        # === ADICIONA INFORMAÇÕES DE MULTA (SE CONFIGURADO) ===
        if boleto_data.get('multa'):
            payload['dado_boleto']['multa'] = boleto_data['multa']
        
        # === ADICIONA INFORMAÇÕES DE DESCONTO (SE CONFIGURADO) ===
        if boleto_data.get('desconto'):
            payload['dado_boleto']['desconto'] = boleto_data['desconto']
            
        # === ADICIONA INFORMAÇÕES DE PROTESTO (SE CONFIGURADO) ===
        if boleto_data.get('protesto'):
            payload['dado_boleto']['protesto'] = boleto_data['protesto']
            
        # === ADICIONA INFORMAÇÕES DE NEGATIVAÇÃO (SE CONFIGURADO) ===
        if boleto_data.get('negativacao'):
            payload['dado_boleto']['negativacao'] = boleto_data['negativacao']

        # Prepara requisição
        url = self.get_api_url('boletos')
        correlation_id = f"odoo-invoice-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        headers = {
            'x-itau-apikey': self.client_id,
            'x-itau-correlationID': correlation_id,
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Authorization': f'Bearer {token}'
        }
        
        # Faz requisição
        response = requests.post(url, headers=headers, json=payload, timeout=self.timeout)
        
        # Armazena JSONs para debug
        self.test_json_enviado = json.dumps(payload, indent=2, ensure_ascii=False)
        try:
            response_json = response.json()
            self.test_json_retorno = json.dumps(response_json, indent=2, ensure_ascii=False)
        except (ValueError, json.JSONDecodeError):
            self.test_json_retorno = f"Status: {response.status_code}\nResposta:\n{response.text}"
        
        # Log no chatter
        if response.status_code in [200, 201]:
            # CORREÇÃO: Acessa nome na estrutura aninhada
            cliente_nome = pagador_data.get('pessoa', {}).get('nome_pessoa', 'N/A')
            self.message_post(
                body=f"✅ Boleto emitido com sucesso via fatura<br/>"
                     f"Status: {response.status_code}<br/>"
                     f"Correlation ID: {correlation_id}<br/>"
                     f"Cliente: {cliente_nome}",
                message_type='notification'
            )
            return response.json()
        else:
            error_msg = f"Erro ao emitir boleto - Status: {response.status_code}"
            self.message_post(
                body=f"❌ {error_msg}<br/>Resposta: {response.text[:500]}...",
                message_type='notification'
            )
            raise Exception(f"{error_msg}: {response.text}") 