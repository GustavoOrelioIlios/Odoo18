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
        selection=[],  # Será populado pelos módulos específicos usando selection_add
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
        required=False,
        help='Chave secreta fornecida pelo banco'
    )
    
    # Connection Parameters
    timeout = fields.Integer(
        string='Timeout (segundos)',
        default=30,
        help='Tempo limite para requisições em segundos'
    )
    
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

    @api.constrains('timeout')
    def _check_timeout(self):
        for record in self:
            if record.timeout <= 0:
                raise ValidationError(_('O timeout deve ser maior que zero'))

    @api.onchange('integracao')
    def _onchange_integracao(self):
        """Atualiza campos baseado no tipo de integração"""
        if self.integracao:
            # Reseta campos sensíveis ao mudar integração
            self.client_id = False
            self.client_secret = False
            self.base_url = False

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
            'environment': self.environment,
            'integracao': self.integracao,
        }

    def _update_connection_status(self, success, error_message=None, token=None):
        """Atualiza o status da conexão e registra no chatter"""
        self.ensure_one()
        
        self.last_connection_test = fields.Datetime.now()
        self.connection_status = 'success' if success else 'failed'
        
        self.env.cr.commit()
        
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
            
        self.env.cr.commit()