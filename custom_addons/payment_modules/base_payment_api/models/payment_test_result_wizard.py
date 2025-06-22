# -*- coding: utf-8 -*-

from odoo import models, fields, api


class PaymentTestResultWizard(models.TransientModel):
    _name = 'payment.test.result.wizard'
    _description = 'Resultado dos Testes da API de Pagamento'

    title = fields.Char(
        string='Título',
        readonly=True
    )
    
    success = fields.Boolean(
        string='Sucesso',
        readonly=True
    )
    
    content = fields.Text(
        string='Resposta da API',
        readonly=True,
        help='Conteúdo da resposta JSON da API'
    )
    
    extra_info = fields.Text(
        string='Informações Adicionais',
        readonly=True,
        help='URLs, parâmetros e outros detalhes do teste'
    )

    def action_close(self):
        """Fecha o modal"""
        return {'type': 'ir.actions.act_window_close'} 