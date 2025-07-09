# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class AccountPaymentTermDiscount(models.Model):
    _name = 'account.payment.term.discount'
    _description = 'Linha de Desconto do Termo de Pagamento'
    _order = 'days desc, id'

    payment_term_id = fields.Many2one(
        'account.payment.term',
        string='Termo de Pagamento',
        required=True,
        ondelete='cascade'
    )
    
    days = fields.Integer(
        string='Dias para Desconto',
        required=True,
        default=0,
        help="Prazo limite para o desconto, em dias após a data da fatura.\n"
             "Exemplo: 5 = desconto válido até 5 dias após a emissão.\n"
             "⚠️ API Itaú exige ordem decrescente (maior → menor)."
    )
    
    value = fields.Float(
        string='Valor do Desconto',
        required=True,
        digits='Account',
        help="Valor do desconto conforme tipo selecionado no termo:\n\n"
             "📊 Para tipos Percentual (02, 90): Digite o percentual\n"
             "   • Exemplo: 5.0 = 5% de desconto\n\n"
             "💰 Para tipos Valor Fixo (01, 91): Digite o valor em reais\n"
             "   • Exemplo: 10.50 = R$ 10,50 de desconto"
    )
    
    is_percentage_type = fields.Boolean(
        string='É Tipo Percentual',
        compute='_compute_discount_type',
        help="Indica se o tipo de desconto do parent é percentual"
    )
    
    value_label = fields.Char(
        string='Label do Valor',
        compute='_compute_discount_type',
        help="Label que muda conforme tipo"
    )
    
    display_info = fields.Char(
        string='Resumo',
        compute='_compute_display_info',
        help="Resumo da condição de desconto"
    )
    
    @api.depends('payment_term_id.itau_discount_code')
    def _compute_discount_type(self):
        """Computa se é tipo percentual e o label correto"""
        for record in self:
            if record.payment_term_id and record.payment_term_id.itau_discount_code:
                record.is_percentage_type = record.payment_term_id.itau_discount_code in ['02', '90']
                
                if record.is_percentage_type:
                    record.value_label = 'Percentual (%)'
                else:
                    record.value_label = 'Valor (R$)'
            else:
                record.is_percentage_type = False
                record.value_label = 'Valor'
    
    @api.depends('days', 'value', 'payment_term_id.itau_discount_code')
    def _compute_display_info(self):
        """Computa informação resumida para exibição"""
        for record in self:
            if record.payment_term_id and record.payment_term_id.itau_discount_code:
                tipo = dict(record.payment_term_id._fields['itau_discount_code'].selection).get(
                    record.payment_term_id.itau_discount_code, 'N/A'
                )
                if record.payment_term_id.itau_discount_code in ['02', '90']:
                    record.display_info = f"{record.days} dias: {record.value}% ({tipo})"
                else:
                    record.display_info = f"{record.days} dias: R$ {record.value:.2f} ({tipo})"
            else:
                record.display_info = f"{record.days} dias: {record.value}"
    
    @api.constrains('days')
    def _check_days(self):
        """Valida que os dias não podem ser negativos"""
        for record in self:
            if record.days < 0:
                raise ValidationError(_("Os dias para desconto não podem ser negativos."))
    
    @api.constrains('value')
    def _check_value(self):
        """Valida que o valor do desconto deve ser positivo"""
        for record in self:
            if record.value <= 0:
                raise ValidationError(_("O valor do desconto deve ser maior que zero."))
            
            if (record.payment_term_id and 
                record.payment_term_id.itau_discount_code in ['02', '90'] and 
                record.value > 100):
                raise ValidationError(_("Para desconto percentual, o valor não pode ser maior que 100%."))
    
    @api.constrains('payment_term_id', 'days')
    def _check_unique_days(self):
        """Valida que não existem dias duplicados no mesmo termo de pagamento"""
        for record in self:
            if record.payment_term_id:
                existing = self.search([
                    ('payment_term_id', '=', record.payment_term_id.id),
                    ('days', '=', record.days),
                    ('id', '!=', record.id)
                ])
                if existing:
                    raise ValidationError(
                        _("Já existe uma condição de desconto para %d dias neste termo de pagamento.") % record.days
                    ) 