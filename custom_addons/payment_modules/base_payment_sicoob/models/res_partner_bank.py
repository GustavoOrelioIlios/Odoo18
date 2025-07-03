# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ResPartnerBank(models.Model):
    _inherit = 'res.partner.bank'

    is_sicoob_bank = fields.Boolean(
        string='É banco Sicoob',
        compute='_compute_is_sicoob_bank',
        store=True
    )

    sicoob_client_number = fields.Char(
        string='Número do Cliente Sicoob',
        help='Número de identificação do cliente Sicoob',
        copy=False
    )

    sicoob_modalidade = fields.Selection([
        ('1', 'SIMPLES COM REGISTRO')
    ], string='Modalidade de Cobrança (Sicoob)',
        default='1',
        help='Código que identifica a modalidade de cobrança no Sicoob'
    )

    @api.depends('bank_id', 'bank_id.name')
    def _compute_is_sicoob_bank(self):
        for record in self:
            record.is_sicoob_bank = record.bank_id and 'sicoob' in record.bank_id.name.lower() if record.bank_id.name else False

    @api.onchange('bank_id')
    def _onchange_bank_id(self):
        if not self.is_sicoob_bank:
            self.sicoob_client_number = False
            self.sicoob_modalidade = False

    @api.constrains('sicoob_client_number')
    def _check_sicoob_client_number(self):
        """Validação do número do cliente Sicoob"""
        for record in self:
            if record.sicoob_client_number:
                # Remove caracteres não numéricos para validação
                clean_number = ''.join(filter(str.isdigit, record.sicoob_client_number))
                if not clean_number:
                    raise ValidationError(_('O número do cliente Sicoob deve conter pelo menos um dígito numérico.'))
                if len(clean_number) > 20:  # Limite máximo de 20 dígitos
                    raise ValidationError(_('O número do cliente Sicoob não pode ter mais de 20 dígitos.'))

    def get_sicoob_beneficiario_data(self):
        """
        Retorna dados do beneficiário formatados para API do Sicoob
        
        Returns:
            dict: Dados do beneficiário no formato esperado pela API
        """
        self.ensure_one()
        
        # Determina tipo de pessoa
        company_type = self.partner_id.company_type
        if company_type == 'company':
            tipo_pessoa_codigo = 'J'
            numero_cadastro = self.partner_id.vat or ''
        else:
            tipo_pessoa_codigo = 'F'
            # Para pessoa física, assume que o VAT contém CPF
            numero_cadastro = self.partner_id.vat or ''
        
        return {
            'numeroCpfCnpj': numero_cadastro,
            'nome': self.partner_id.name or '',
            'endereco': {
                'logradouro': self.partner_id.street or '',
                'bairro': self.partner_id.street2 or '',
                'cidade': self.partner_id.city or '',
                'uf': self.partner_id.state_id.code if self.partner_id.state_id else '',
                'cep': self.partner_id.zip or ''
            }
        } 