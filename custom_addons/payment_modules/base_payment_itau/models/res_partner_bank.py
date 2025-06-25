# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ResPartnerBank(models.Model):
    _inherit = 'res.partner.bank'

    # =============================
    # CAMPOS ESPECÍFICOS DO ITAÚ
    # =============================
    
    # Campo específico do beneficiário Itaú
    itau_beneficiary_id = fields.Char(
        string='ID Beneficiário Itaú',
        help='ID do Beneficiário no sistema Itaú. Se não preenchido, utilizará dados do parceiro.',
        tracking=True
    )
    
    # Campo específico de nome de cobrança
    itau_nome_cobranca = fields.Char(
        string='Nome Cobrança Itaú',
        help='Nome específico para cobrança no Itaú. Se não preenchido, utilizará o nome do parceiro.',
        tracking=True
    )
    
    # =============================
    # CAMPOS DE ENDEREÇO ESPECÍFICOS
    # =============================
    
    # Many2one para endereço específico de cobrança
    itau_endereco_cobranca_id = fields.Many2one(
        'res.partner',
        string='Endereço Cobrança Itaú',
        help='Selecione um endereço específico para cobrança Itaú. Inclui endereço principal e endereços de cobrança do parceiro.',
        domain="['|', ('id', '=', partner_id), '&', ('parent_id', '=', partner_id), ('type', 'in', ['invoice', 'delivery'])]"
    )
    
    # =============================
    # CAMPOS INTERNOS (NÃO EXIBIDOS NA INTERFACE)
    # =============================
    # Estes campos são preenchidos automaticamente quando se seleciona
    # um endereço específico em itau_endereco_cobranca_id
    
    itau_street = fields.Char(
        string='Logradouro Itaú (Interno)',
        help='Campo interno. Preenchido automaticamente quando seleciona endereço específico.'
    )
    
    itau_street2 = fields.Char(
        string='Bairro Itaú (Interno)',
        help='Campo interno. Preenchido automaticamente quando seleciona endereço específico.'
    )
    
    itau_city = fields.Char(
        string='Cidade Itaú (Interno)',
        help='Campo interno. Preenchido automaticamente quando seleciona endereço específico.'
    )
    
    itau_state_id = fields.Many2one(
        'res.country.state',
        string='Estado Itaú (Interno)',
        help='Campo interno. Preenchido automaticamente quando seleciona endereço específico.'
    )
    
    itau_zip = fields.Char(
        string='CEP Itaú (Interno)',
        help='Campo interno. Preenchido automaticamente quando seleciona endereço específico.'
    )

    # =============================
    # CAMPOS COMPUTADOS COM FALLBACK
    # =============================
    
    @api.depends('partner_id', 'itau_beneficiary_id', 'itau_nome_cobranca', 
                 'itau_endereco_cobranca_id', 'itau_street', 'itau_street2', 
                 'itau_city', 'itau_state_id', 'itau_zip')
    def _compute_itau_data(self):
        """Computa dados com fallback para o parceiro"""
        for record in self:
            # Endereço de referência (específico ou do parceiro)
            endereco_ref = record.itau_endereco_cobranca_id or record.partner_id
            
            # Atualiza campos computados
            record.itau_beneficiary_id_computed = record.itau_beneficiary_id or (record.partner_id.vat or '')
            record.itau_nome_cobranca_computed = record.itau_nome_cobranca or (record.partner_id.name or '')
            record.itau_street_computed = record.itau_street or (endereco_ref.street or '')
            record.itau_street2_computed = record.itau_street2 or (endereco_ref.street2 or '')
            record.itau_city_computed = record.itau_city or (endereco_ref.city or '')
            record.itau_state_id_computed = record.itau_state_id or endereco_ref.state_id
            record.itau_zip_computed = record.itau_zip or (endereco_ref.zip or '')
    
    # Campos computados que implementam a lógica de fallback
    itau_beneficiary_id_computed = fields.Char(
        string='ID Beneficiário (Final)',
        compute='_compute_itau_data',
        store=True,
        help='Valor final do ID Beneficiário (específico ou do parceiro)'
    )
    
    itau_nome_cobranca_computed = fields.Char(
        string='Nome Cobrança (Final)',
        compute='_compute_itau_data',
        store=True,
        help='Valor final do Nome Cobrança (específico ou do parceiro)'
    )
    
    itau_street_computed = fields.Char(
        string='Logradouro (Final)',
        compute='_compute_itau_data',
        store=True,
        help='Valor final do Logradouro (específico ou do parceiro)'
    )
    
    itau_street2_computed = fields.Char(
        string='Bairro (Final)',
        compute='_compute_itau_data',
        store=True,
        help='Valor final do Bairro (específico ou do parceiro)'
    )
    
    itau_city_computed = fields.Char(
        string='Cidade (Final)',
        compute='_compute_itau_data',
        store=True,
        help='Valor final da Cidade (específico ou do parceiro)'
    )
    
    itau_state_id_computed = fields.Many2one(
        'res.country.state',
        string='Estado (Final)',
        compute='_compute_itau_data',
        store=True,
        help='Valor final do Estado (específico ou do parceiro)'
    )
    
    itau_zip_computed = fields.Char(
        string='CEP (Final)',
        compute='_compute_itau_data',
        store=True,
        help='Valor final do CEP (específico ou do parceiro)'
    )

    # =============================
    # MÉTODOS AUXILIARES
    # =============================
    
    def get_itau_beneficiario_data(self):
        """
        Retorna dados do beneficiário formatados para API do Itaú
        
        Returns:
            dict: Dados do beneficiário no formato esperado pela API
        """
        self.ensure_one()
        
        # Força recálculo dos campos computados
        self._compute_itau_data()
        
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
            'id_beneficiario': self.itau_beneficiary_id_computed or '',
            'nome_cobranca': self.itau_nome_cobranca_computed or '',
            'tipo_pessoa': {
                'codigo_tipo_pessoa': tipo_pessoa_codigo,
                'numero_cadastro_nacional_pessoa_juridica' if company_type == 'company' else 'numero_cadastro_pessoa_fisica': numero_cadastro
            },
            'endereco': {
                'nome_logradouro': self.itau_street_computed or '',
                'nome_bairro': self.itau_street2_computed or '',
                'nome_cidade': self.itau_city_computed or '',
                'sigla_UF': self.itau_state_id_computed.code if self.itau_state_id_computed else '',
                'numero_CEP': self.itau_zip_computed or ''
            }
        }
    
    @api.constrains('itau_zip')
    def _check_itau_zip(self):
        """Valida formato do CEP específico do Itaú"""
        for record in self:
            if record.itau_zip:
                # Remove caracteres não numéricos
                zip_numbers = ''.join(filter(str.isdigit, record.itau_zip))
                if len(zip_numbers) != 8:
                    raise ValidationError(_('CEP Itaú deve ter exatamente 8 dígitos.'))
    
    def get_available_addresses(self):
        """
        Retorna endereços disponíveis para seleção no campo itau_endereco_cobranca_id
        
        Returns:
            recordset: Endereços disponíveis (principal + endereços de cobrança/entrega)
        """
        self.ensure_one()
        if not self.partner_id:
            return self.env['res.partner']
            
        # Endereço principal + endereços filhos de cobrança/entrega
        available_addresses = self.partner_id
        if self.partner_id.child_ids:
            child_addresses = self.partner_id.child_ids.filtered(
                lambda p: p.type in ['invoice', 'delivery']
            )
            available_addresses |= child_addresses
            
        return available_addresses
    
    @api.onchange('itau_endereco_cobranca_id')
    def _onchange_itau_endereco_cobranca(self):
        """Preenche campos de endereço quando seleciona endereço específico"""
        if self.itau_endereco_cobranca_id:
            endereco = self.itau_endereco_cobranca_id
            # Preenche automaticamente os campos (sempre sobrescreve)
            self.itau_street = endereco.street
            self.itau_street2 = endereco.street2  
            self.itau_city = endereco.city
            self.itau_state_id = endereco.state_id
            self.itau_zip = endereco.zip
        else:
            # Se desmarcou, limpa os campos específicos para usar o endereço principal
            self.itau_street = False
            self.itau_street2 = False
            self.itau_city = False
            self.itau_state_id = False
            self.itau_zip = False

    def get_complete_itau_data(self):
        """
        Retorna dados completos incluindo beneficiário e endereço
        
        Returns:
            dict: Dados completos formatados para API
        """
        self.ensure_one()
        return {
            'beneficiario': self.get_itau_beneficiario_data(),
            'bank_info': {
                'acc_number': self.acc_number,
                'bank_name': self.bank_id.name if self.bank_id else '',
                'bank_bic': self.bank_id.bic if self.bank_id else '',
            }
        } 