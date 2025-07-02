# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ResCompany(models.Model):
    _inherit = 'res.company'
    
    # Configuração Sicoob para a empresa
    sicoob_payment_api_id = fields.Many2one(
        'base.payment.api',
        string='Configuração API Sicoob',
        domain="[('integracao', '=', 'sicoob_boleto')]",
        help='Configuração da API Sicoob que será usada para emissão de boletos desta empresa'
    )
    
    # Campo para selecionar qual conta bancária Sicoob usar
    sicoob_partner_bank_id = fields.Many2one(
        'res.partner.bank',
        string='Conta Bancária Sicoob',
        domain="[('partner_id', '=', partner_id), ('bank_id.name', 'ilike', 'Sicoob')]",
        help='Conta bancária desta empresa que contém os dados específicos do Sicoob para emissão de boletos'
    )
    
    def get_sicoob_beneficiario_data(self):
        """
        Retorna dados do beneficiário baseado na conta bancária Sicoob configurada
        """
        self.ensure_one()
        
        if not self.sicoob_partner_bank_id:
            raise UserError(_(
                'A empresa "%s" não possui uma conta bancária Sicoob configurada.\n'
                'Configure em: Configurações → Empresas → %s → Configurações Sicoob → Conta Bancária Sicoob'
            ) % (self.name, self.name))
        
        # Usa o método da conta bancária que já tem toda a lógica
        return self.sicoob_partner_bank_id.get_sicoob_beneficiario_data() 