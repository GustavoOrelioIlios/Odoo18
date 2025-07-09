# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import timedelta


class AccountPaymentTerm(models.Model):
    _inherit = 'account.payment.term'

    sicoob_discount_code = fields.Selection([
        ('0', 'Sem Desconto'),
        ('1', 'Valor Fixo Até a Data Informada'),
        ('2', 'Percentual até a data informada'),
        ('3', 'Valor por antecipação dia corrido'),
        ('4', 'Valor por antecipação dia útil'),
        ('5', 'Percentual por antecipação dia corrido'),
        ('6', 'Percentual por antecipação dia útil'),
    ], string='Tipo de Desconto (Sicoob)',
       default='0',
       help="Define o tipo de desconto para TODAS as condições deste termo.\n\n"
            "📋 Códigos da API Sicoob:\n"
            "• 0: Sem Desconto\n"
            "• 1: Valor Fixo Até a Data Informada\n"
            "• 2: Percentual até a data informada\n"
            "• 3: Valor por antecipação dia corrido\n"
            "• 4: Valor por antecipação dia útil\n"
            "• 5: Percentual por antecipação dia corrido\n"
            "• 6: Percentual por antecipação dia útil")

    sicoob_discount_line_ids = fields.One2many(
        'account.payment.term.sicoob.discount',
        'payment_term_id',
        string='Condições de Desconto',
        help="Configure múltiplas datas limite para o mesmo tipo de desconto.\n"
             "Exemplo: 10 dias (R$ 50), 5 dias (R$ 30), 2 dias (R$ 10)\n"
             "⚠️ API exige ordem decrescente de datas."
    )
    
    sicoob_discount_summary = fields.Text(
        string='Resumo dos Descontos',
        compute='_compute_sicoob_discount_summary',
        help="Resumo das condições de desconto configuradas"
    )
    
    @api.depends('sicoob_discount_line_ids', 'sicoob_discount_code')
    def _compute_sicoob_discount_summary(self):
        """Computa resumo das condições de desconto"""
        for record in self:
            if record.sicoob_discount_line_ids and record.sicoob_discount_code != '0':
                tipo_desc = dict(record._fields['sicoob_discount_code'].selection)[record.sicoob_discount_code]
                linhas = []
                for line in record.sicoob_discount_line_ids.sorted('days', reverse=True):
                    if record.sicoob_discount_code in ['2', '5', '6']:
                        linhas.append(f"• {line.days} dias: {line.value}%")
                    else:
                        linhas.append(f"• {line.days} dias: R$ {line.value:.2f}")
                
                record.sicoob_discount_summary = f"Tipo: {tipo_desc} (código {record.sicoob_discount_code})\n" + "\n".join(linhas)
            else:
                record.sicoob_discount_summary = "Nenhuma condição de desconto configurada"
    
    @api.constrains('sicoob_discount_line_ids', 'sicoob_discount_code')
    def _check_sicoob_discount_consistency(self):
        """Valida consistência entre tipo de desconto e linhas configuradas"""
        for record in self:
            if record.sicoob_discount_code != '0' and not record.sicoob_discount_line_ids:
                raise ValidationError(
                    _("Quando um tipo de desconto é selecionado, deve haver pelo menos uma linha de desconto configurada.")
                )
            
            if record.sicoob_discount_code == '0' and record.sicoob_discount_line_ids:
                raise ValidationError(
                    _("Quando 'Sem Desconto' está selecionado, não deve haver linhas de desconto configuradas.")
                )
    
    def get_sicoob_discount_data(self, invoice_date):
        """
        Gera estrutura de desconto conforme API do Sicoob
        
        Args:
            invoice_date (date): Data da fatura para calcular datas de desconto
            
        Returns:
            dict: Estrutura de desconto para API do Sicoob ou {} se sem desconto
        """
        self.ensure_one()
        
        if not self.sicoob_discount_code or self.sicoob_discount_code == '0':
            return {}
        
        if not self.sicoob_discount_line_ids:
            return {}
        
        descontos_list = []
        
        for line in self.sicoob_discount_line_ids.sorted('days', reverse=True):
            data_desconto = invoice_date + timedelta(days=line.days)
            
            desconto_info = {
                'dataPrimeiroDesconto': data_desconto.strftime('%Y-%m-%d')
            }
            
            if self.sicoob_discount_code in ['2', '5', '6']:
                desconto_info['valorPrimeiroDesconto'] = line.value
            else:
                desconto_info['valorPrimeiroDesconto'] = line.value
            
            descontos_list.append(desconto_info)
        
        if descontos_list:
            return {
                'tipoDesconto': self.sicoob_discount_code,
                'dataPrimeiroDesconto': descontos_list[0]['dataPrimeiroDesconto'],
                'valorPrimeiroDesconto': descontos_list[0]['valorPrimeiroDesconto']
            }
        
        return {} 