# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from .sicoob_pydantic_models import SicoobBoletoValidator
import requests
import json
import logging
from datetime import datetime

_logger = logging.getLogger(__name__)


class BasePaymentSicoob(models.Model):
    _inherit = 'base.payment.api'

    # Adiciona opção Sicoob às integrações disponíveis usando selection_add
    integracao = fields.Selection(
        selection_add=[('sicoob_boleto', 'Sicoob - Boleto')],
        ondelete={'sicoob_boleto': 'cascade'}
    )

    def _get_sicoob_token(self):
        """Retorna o token do Sicoob"""
        self.ensure_one()
        
        if self.environment == 'sandbox':
            # Token fixo para ambiente sandbox
            return '1301865f-c6bc-38f3-9f49-666dbcfc59c3'
        else:
            # TODO: Implementar lógica para ambiente de produção
            raise NotImplementedError(_('Ambiente de produção ainda não implementado'))

    def _get_sicoob_headers(self):
        """Retorna os headers para requisições Sicoob"""
        self.ensure_one()
        
        token = self._get_sicoob_token()
        _logger.info("[Sicoob] Token(AQUI): %s", token)
        _logger.info("[Sicoob] Client ID(AQUI): %s", self.client_id)
        correlation_id = f"odoo-sicoob-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        return {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Authorization': f'Bearer {token}',
            'client_id': self.client_id,
            'User-Agent': 'PostmanRuntime/7.4.1',
            # 'Cookie': '3335c623dfb80f915ea5457e9d5d4421=9b5b7462af495d4f602fe8d773abf45d; TS016f8952=017a3a183bdaaf76925393b75c52c6bf3132dfdb99c4045312a35e5384c4c0e1fff3052c6d1d0111a1632b2a3831f55a16212d8ef7'
            # 'x-sicoob-correlationID': correlation_id
        }

    def testar_token(self):
        """Implementa o teste de token específico para Sicoob"""
        self.ensure_one()
        
        if self.integracao != 'sicoob_boleto':
            return super().testar_token()

        try:
            # No caso do Sicoob sandbox, vamos apenas verificar se temos o client_id
            if not self.client_id:
                raise UserError(_('Client ID é obrigatório para integração com Sicoob'))
            
            # Obtém os headers com o token
            headers = self._get_sicoob_headers()
            
            # Registra sucesso
            self._update_connection_status(True)
            
            # Registra os headers para debug
            debug_info = json.dumps(headers, indent=2)
            self.message_post(
                body=f"✅ Headers de autenticação configurados com sucesso:\n<pre>{debug_info}</pre>",
                message_type='notification'
            )
            
            return self._refresh_view()
            
        except Exception as e:
            self._update_connection_status(False, str(e))
            raise UserError(_('Erro ao configurar autenticação: %s') % str(e))

    def _emitir_boleto_sicoob(self, invoice):
        """
        Emite um boleto Sicoob para uma fatura
        
        Args:
            invoice: account.move - A fatura para emitir o boleto
            
        Returns:
            dict: Dados do boleto emitido
        """
        self.ensure_one()
        
        try:
            # Obtém os headers com o token
            headers = self._get_sicoob_headers()

            # Coleta todos os dados necessários para o boleto
            payload_data = invoice._get_sicoob_boleto_details_data()

            # Log para debug da espécie do documento
            _logger.info("[Sicoob] Espécie do documento configurada no diário: %s", invoice.journal_id.sicoob_especie_documento)
            _logger.info("[Sicoob] Espécie do documento no payload: %s", payload_data.get('codigoEspecieDocumento'))

            # Valida os dados usando o modelo Pydantic
            sucesso, dados_validados, mensagem = SicoobBoletoValidator.validar_payload(payload_data)
            if not sucesso:
                raise UserError(_(
                    "Erros de validação encontrados:\n%s"
                ) % mensagem)

            _logger.info("[Sicoob] Espécie do documento após validação: %s", dados_validados.get('codigoEspecieDocumento'))

            # Salva o JSON enviado para debug
            invoice.write({
                'test_json_enviado': json.dumps(dados_validados, indent=2, ensure_ascii=False)
            })

            # Determina a URL da API baseado no ambiente
            # if self.environment == 'sandbox':
            #     api_url = 'https://sandbox.sicoob.com.br/cobranca-bancaria/v3/boletos'
            # else:
            #     api_url = 'https://api.sicoob.com.br/cobranca-bancaria/v3/boletos'

            api_url = 'https://sandbox.sicoob.com.br/sicoob/sandbox/cobranca-bancaria/v3/boletos'

            # LOG DETALHADO ANTES DO REQUEST
            _logger.info("[Sicoob] URL da API AQUI: %s", api_url)
            _logger.info("[Sicoob] Headers da requisição: %s", json.dumps(headers, indent=2, ensure_ascii=False))
            _logger.info("[Sicoob] JSON enviado: %s", json.dumps(dados_validados, indent=2, ensure_ascii=False))

            # dados_validados1 = {
            #     "numeroCliente": 25546454,
            #     "codigoModalidade": 1,
            #     "numeroContaCorrente": 75187241,
            #     "codigoEspecieDocumento": "DM",
            #     "dataEmissao": "2018-09-20",
            #     "nossoNumero": 2588658,
            #     "seuNumero": "1235512",
            #     "identificacaoBoletoEmpresa": "4562",
            #     "identificacaoEmissaoBoleto": 1,
            #     "identificacaoDistribuicaoBoleto": 1,
            #     "valor": 156.50,
            #     "dataVencimento": "2018-09-20",
            #     "dataLimitePagamento": "2018-09-20",
            #     "valorAbatimento": 1,
            #     "tipoDesconto": 1,
            #     "dataPrimeiroDesconto": "2018-09-20",
            #     "valorPrimeiroDesconto": 1,
            #     "dataSegundoDesconto": "2018-09-20",
            #     "valorSegundoDesconto": 0,
            #     "dataTerceiroDesconto": "2018-09-20",
            #     "valorTerceiroDesconto": 0,
            #     "tipoMulta": 1,
            #     "dataMulta": "2018-09-20",
            #     "valorMulta": 5,
            #     "tipoJurosMora": 1,
            #     "dataJurosMora": "2018-09-20",
            #     "valorJurosMora": 4,
            #     "numeroParcela": 1,
            #     "aceite": True,
            #     "codigoNegativacao": 2,
            #     "numeroDiasNegativacao": 60,
            #     "codigoProtesto": 1,
            #     "numeroDiasProtesto": 30,
            #     "pagador": {
            #         "numeroCpfCnpj": "98765432185",
            #         "nome": "Marcelo dos Santos",
            #         "endereco": "Rua 87 Quadra 1 Lote 1 casa 1",
            #         "bairro": "Santa Rosa",
            #         "cidade": "Luziânia",
            #         "cep": "72320000",
            #         "uf": "DF",
            #         "email": "pagador@dominio.com.br"
            #     },
            #     "beneficiarioFinal": {
            #         "numeroCpfCnpj": "98784978699",
            #         "nome": "Lucas de Lima"
            #     },
            #     "mensagensInstrucao": [
            #         "Descrição da Instrução 1",
            #         "Descrição da Instrução 2",
            #         "Descrição da Instrução 3",
            #         "Descrição da Instrução 4",
            #         "Descrição da Instrução 5"
            #     ],
            #     "gerarPdf": False,
            #     "rateioCreditos": [
            #         {
            #             "numeroBanco": 756,
            #             "numeroAgencia": 4027,
            #             "numeroContaCorrente": 0,
            #             "contaPrincipal": True,
            #             "codigoTipoValorRateio": 1,
            #             "valorRateio": 100,
            #             "codigoTipoCalculoRateio": 1,
            #             "numeroCpfCnpjTitular": "98765432185",
            #             "nomeTitular": "Marcelo dos Santos",
            #             "codigoFinalidadeTed": 10,
            #             "codigoTipoContaDestinoTed": "CC",
            #             "quantidadeDiasFloat": 1,
            #             "dataFloatCredito": "2020-12-30"
            #         }
            #     ],
            #     "codigoCadastrarPIX": 1,
            #     "numeroContratoCobranca": 1

            # }

            # Faz a chamada à API
            response = requests.post(
                api_url,
                headers=headers,
                json=dados_validados,
                timeout=self.timeout
            )

            _logger.info("[Sicoob] Resposta da API AQUI: %s", response.json())



            # LOG DETALHADO DA RESPOSTA
            _logger.info("[Sicoob] Status code da resposta: %s", response.status_code)
            _logger.info("[Sicoob] Headers da resposta: %s", dict(response.headers))
            _logger.info("[Sicoob] Corpo da resposta: %s", response.text[:2000])  # Limita para não poluir o log

            # Processa a resposta
            response_json = None
            try:
                response_json = response.json()
                invoice.test_json_retorno = json.dumps(response_json, indent=2, ensure_ascii=False)
            except (ValueError, json.JSONDecodeError):
                invoice.test_json_retorno = f"Status: {response.status_code}\nContent-Type: {response.headers.get('Content-Type', 'N/A')}\n\nResposta:\n{response.text}"

            # Atualiza a fatura com o resultado
            if response.status_code in [200, 201]:
                invoice.write({
                    'sicoob_status': 'success',
                    'sicoob_date': fields.Datetime.now(),
                    'sicoob_error_message': False,
                })
                _logger.info("Boleto Sicoob emitido com sucesso para fatura %s", invoice.name)

                # Processa a resposta e cria o registro move.boleto
                if response_json and response_json.get('resultado'):
                    invoice._create_boleto_record_from_sicoob_api_response(response_json.get('resultado'))
                else:
                    # Fallback para o caso de a chave 'resultado' não estar presente
                    invoice._create_boleto_record_from_sicoob_api_response(response_json)
                
                return response_json
            else:
                error_msg = f"Erro API Sicoob (Status: {response.status_code}): {response.text[:500]}..."
                invoice.write({
                    'sicoob_status': 'error',
                    'sicoob_date': fields.Datetime.now(),
                    'sicoob_error_message': error_msg,
                })
                _logger.error("Falha na emissão do boleto Sicoob para fatura %s: %s", invoice.name, error_msg)
                raise UserError(_("Erro na comunicação com a API Sicoob. Verifique os detalhes na fatura."))

        except Exception as e:
            import traceback
            error_msg = f"Exceção ao emitir boleto Sicoob: {str(e)}\nTraceback:\n{traceback.format_exc()}"
            invoice.write({
                'sicoob_status': 'error',
                'sicoob_date': fields.Datetime.now(),
                'sicoob_error_message': error_msg,
            })
            _logger.error("Erro geral na emissão do boleto Sicoob para fatura %s: %s", invoice.name, error_msg)
            raise UserError(_("Ocorreu um erro inesperado ao tentar emitir o boleto Sicoob. Contate o suporte.")) 