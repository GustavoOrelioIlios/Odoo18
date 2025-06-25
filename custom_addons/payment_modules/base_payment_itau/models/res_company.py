# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ResCompany(models.Model):
    _inherit = 'res.company'
    
    # Configuração Itaú para a empresa
    itau_payment_api_id = fields.Many2one(
        'base.payment.api',
        string='Configuração API Itaú',
        domain="[('integracao', '=', 'itau_boleto')]",
        help='Configuração da API Itaú que será usada para emissão de boletos desta empresa'
    )
    
    # Campo para selecionar qual conta bancária Itaú usar
    itau_partner_bank_id = fields.Many2one(
        'res.partner.bank',
        string='Conta Bancária Itaú',
        domain="[('partner_id', '=', partner_id), ('bank_id.name', 'ilike', 'Itaú')]",
        help='Conta bancária desta empresa que contém os dados específicos do Itaú para emissão de boletos'
    )
    
    def get_itau_beneficiario_data(self):
        """
        Retorna dados do beneficiário baseado na conta bancária Itaú configurada
        """
        self.ensure_one()
        
        if not self.itau_partner_bank_id:
            raise UserError(_(
                'A empresa "%s" não possui uma conta bancária Itaú configurada.\n'
                'Configure em: Configurações → Empresas → %s → Configurações Itaú → Conta Bancária Itaú'
            ) % (self.name, self.name))
        
        # Usa o método da conta bancária que já tem toda a lógica
        return self.itau_partner_bank_id.get_itau_beneficiario_data() 