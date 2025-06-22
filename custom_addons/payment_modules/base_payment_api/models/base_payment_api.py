# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import requests
import json
import logging

_logger = logging.getLogger(__name__)


class BasePaymentAPI(models.Model):
    _name = 'base.payment.api'
    _description = 'Configuração Base para Integrações de Pagamento'
    _inherit = ['mail.thread']
    _order = 'name'

    name = fields.Char(
        string='Nome da Configuração',
        required=True,
        help='Nome identificador para esta configuração',
        tracking=True
    )
    
    bank_id = fields.Many2one(
        'res.bank',
        string='Banco',
        required=True,
        help='Banco associado a esta integração',
        tracking=True
    )
    
    integracao = fields.Selection(
        selection='_get_integracao_selection',
        string='Tipo de Integração', 
        required=True, 
        help='Tipo de integração de pagamento',
        tracking=True
    )
    
    environment = fields.Selection([
        ('sandbox', 'Sandbox (Testes)'),
        ('production', 'Produção')
    ], string='Ambiente', required=True, default='sandbox', tracking=True)
    
    # API Configuration
    base_url = fields.Char(
        string='URL Base da API',
        required=True,
        help='URL base da API do banco',
        tracking=True
    )
    
    client_id = fields.Char(
        string='Client ID',
        required=True,
        help='ID do cliente fornecido pelo banco'
    )
    
    client_secret = fields.Char(
        string='Client Secret',
        required=True,
        help='Chave secreta fornecida pelo banco'
    )
    
    # Connection Parameters
    timeout = fields.Integer(
        string='Timeout (segundos)',
        default=30,
        help='Tempo limite para requisições em segundos'
    )
    
    # Additional Configuration - COMENTADOS TEMPORARIAMENTE
    # debug_mode = fields.Boolean(
    #     string='Modo Debug',
    #     default=False,
    #     help='Ativar logs detalhados'
    # )
    
    active = fields.Boolean(
        string='Ativo',
        default=True,
        tracking=True
    )
    
    company_id = fields.Many2one(
        'res.company',
        string='Empresa',
        default=lambda self: self.env.company,
        required=True
    )
    
    description = fields.Text(
        string='Descrição',
        help='Descrição detalhada da configuração'
    )
    
    # Status fields
    last_connection_test = fields.Datetime(
        string='Último Teste de Conexão',
        readonly=True
    )
    
    connection_status = fields.Selection([
        ('not_tested', 'Não Testado'),
        ('success', 'Sucesso'),
        ('failed', 'Falhou')
    ], string='Status da Conexão', default='not_tested', readonly=True, tracking=True)
    
    # CAMPOS DE DEBUG - COMENTADOS
    # last_error_message = fields.Text(
    #     string='Última Mensagem de Erro',
    #     readonly=True,
    #     help='Detalhes do último erro de conexão'
    # )
    # 
    # last_token = fields.Text(
    #     string='Último Token Gerado',
    #     readonly=True,
    #     help='Último token gerado (para debug)'
    # )

    @api.constrains('timeout')
    def _check_timeout(self):
        for record in self:
            if record.timeout <= 0:
                raise ValidationError(_('O timeout deve ser maior que zero'))

    # CONSTRAINTS COMENTADOS TEMPORARIAMENTE
    # @api.constrains('retry_attempts')
    # def _check_retry_attempts(self):
    #     for record in self:
    #         if record.retry_attempts < 0:
    #             raise ValidationError(_('O número de tentativas não pode ser negativo'))

    @api.model
    def _get_integracao_selection(self):
        """Retorna as opções de integração disponíveis - será estendido pelos módulos específicos"""
        return []

    def testar_token(self):
        """Método genérico para testar token - será sobrescrito pelos módulos específicos"""
        raise NotImplementedError(_('Método testar_token deve ser implementado pelo módulo específico'))
    
    def _refresh_view(self):
        """Força a atualização da view atual sem reload completo da página"""
        return {
            'type': 'ir.actions.client',
            'tag': 'soft_reload',
        }

    def get_connection_params(self):
        """Retorna os parâmetros de conexão formatados para uso na integração"""
        self.ensure_one()
        return {
            'base_url': self.base_url,
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'timeout': self.timeout,
            # 'retry_attempts': self.retry_attempts,      # COMENTADO
            # 'debug_mode': self.debug_mode,              # COMENTADO
            'environment': self.environment,
            'integracao': self.integracao,
        }

    def _update_connection_status(self, success, error_message=None, token=None):
        """Atualiza o status da conexão e registra no chatter"""
        self.ensure_one()
        
        # CORREÇÃO TEMPORÁRIA: Ajustar data para 2024
        from datetime import datetime, timedelta
        current_time = fields.Datetime.now()
        if current_time.year == 2025:
            # Se estiver em 2025, subtrair 1 ano para corrigir
            corrected_time = current_time.replace(year=2024)
        else:
            corrected_time = current_time
            
        self.last_connection_test = corrected_time
        self.connection_status = 'success' if success else 'failed'
        # CAMPOS DE DEBUG COMENTADOS
        # self.last_error_message = error_message if not success else False
        # self.last_token = 'Token gerado com sucesso' if success else False
        
        # FORÇA COMMIT DAS MUDANÇAS ANTES DO CHATTER
        self.env.cr.commit()
        
        # REGISTRA NO CHATTER
        if success:
            self.message_post(
                body="✅ Teste de conexão realizado com sucesso",
                message_type='notification'
            )
        else:
            self.message_post(
                body=f"❌ Falha no teste de conexão: {error_message}",
                message_type='notification'
            )
            
        # FORÇA COMMIT DO CHATTER
        self.env.cr.commit()

    # MODAL COMENTADO - NÃO EXIBIR MAIS MODAL NOS TESTES
    # def _show_test_result(self, title, content, success, extra_info=None):
    #     """Exibe modal com resultado do teste"""
    #     return {
    #         'type': 'ir.actions.act_window',
    #         'name': title,
    #         'res_model': 'payment.test.result.wizard',
    #         'view_mode': 'form',
    #         'target': 'new',
    #         'context': {
    #             'default_title': title,
    #             'default_content': content,
    #             'default_success': success,
    #             'default_extra_info': extra_info or '',
    #         }
    #     } 