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
        correlation_id = f"odoo-sicoob-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        return {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Authorization': f'Bearer {token}',
            'client_id': self.client_id,
            'x-sicoob-correlationID': correlation_id
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
            if self.environment == 'sandbox':
                api_url = 'https://sandbox.sicoob.com.br/cobranca-bancaria/v3/boletos'
            else:
                api_url = 'https://api.sicoob.com.br/cobranca-bancaria/v3/boletos'

            # Faz a chamada à API
            response = requests.post(
                api_url,
                headers=headers,
                json=dados_validados,
                timeout=self.timeout
            )

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
            error_msg = f"Exceção ao emitir boleto Sicoob: {str(e)}"
            invoice.write({
                'sicoob_status': 'error',
                'sicoob_date': fields.Datetime.now(),
                'sicoob_error_message': error_msg,
            })
            _logger.error("Erro geral na emissão do boleto Sicoob para fatura %s: %s", invoice.name, error_msg)
            raise UserError(_("Ocorreu um erro inesperado ao tentar emitir o boleto Sicoob. Contate o suporte.")) 