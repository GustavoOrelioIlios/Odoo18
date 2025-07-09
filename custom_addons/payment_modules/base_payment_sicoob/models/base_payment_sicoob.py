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
        }

    def testar_token(self):
        """Implementa o teste de token específico para Sicoob"""
        self.ensure_one()
        
        if self.integracao != 'sicoob_boleto':
            return super().testar_token()

        try:
            if not self.client_id:
                raise UserError(_('Client ID é obrigatório para integração com Sicoob'))
            
            headers = self._get_sicoob_headers()
            
            self._update_connection_status(True)
            
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
            headers = self._get_sicoob_headers()

            payload_data = invoice._get_sicoob_boleto_details_data()

            _logger.info("[Sicoob] Espécie do documento configurada no diário: %s", invoice.journal_id.sicoob_especie_documento)
            _logger.info("[Sicoob] Espécie do documento no payload: %s", payload_data.get('codigoEspecieDocumento'))

            sucesso, dados_validados, mensagem = SicoobBoletoValidator.validar_payload(payload_data)
            if not sucesso:
                raise UserError(_(
                    "Erros de validação encontrados:\n%s"
                ) % mensagem)

            _logger.info("[Sicoob] Espécie do documento após validação: %s", dados_validados.get('codigoEspecieDocumento'))

            invoice.write({
                'test_json_enviado': json.dumps(dados_validados, indent=2, ensure_ascii=False)
            })

            api_url = 'https://sandbox.sicoob.com.br/sicoob/sandbox/cobranca-bancaria/v3/boletos'

            _logger.info("[Sicoob] URL da API AQUI: %s", api_url)
            _logger.info("[Sicoob] Headers da requisição: %s", json.dumps(headers, indent=2, ensure_ascii=False))
            _logger.info("[Sicoob] JSON enviado: %s", json.dumps(dados_validados, indent=2, ensure_ascii=False))

            response = requests.post(
                api_url,
                headers=headers,
                json=dados_validados,
                timeout=self.timeout
            )

            _logger.info("[Sicoob] Resposta da API AQUI: %s", response.json())

            _logger.info("[Sicoob] Status code da resposta: %s", response.status_code)
            _logger.info("[Sicoob] Headers da resposta: %s", dict(response.headers))
            _logger.info("[Sicoob] Corpo da resposta: %s", response.text[:2000])

            response_json = None
            try:
                response_json = response.json()
                invoice.test_json_retorno = json.dumps(response_json, indent=2, ensure_ascii=False)
            except (ValueError, json.JSONDecodeError):
                invoice.test_json_retorno = f"Status: {response.status_code}\nContent-Type: {response.headers.get('Content-Type', 'N/A')}\n\nResposta:\n{response.text}"

            if response.status_code in [200, 201]:
                invoice.write({
                    'sicoob_status': 'success',
                    'sicoob_date': fields.Datetime.now(),
                    'sicoob_error_message': False,
                })
                _logger.info("Boleto Sicoob emitido com sucesso para fatura %s", invoice.name)

                if response_json and response_json.get('resultado'):
                    invoice._create_boleto_record_from_sicoob_api_response(response_json.get('resultado'))
                else:
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