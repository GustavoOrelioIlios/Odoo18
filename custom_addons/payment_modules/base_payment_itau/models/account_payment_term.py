# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class AccountPaymentTerm(models.Model):
    _inherit = 'account.payment.term'

    itau_discount_code = fields.Selection([
        ('00', 'Sem Desconto'),
        ('01', 'Valor Fixo'),
        ('02', 'Percentual'),
        ('90', 'Percentual por Antecipação'),
        ('91', 'Valor por Antecipação'),
    ], string='Tipo de Desconto (Itaú)',
       default='00',
       help="Define o tipo único de desconto para TODAS as condições deste termo.\n\n"
            "📋 Códigos da API Itaú:\n"
            "• 00: Sem desconto\n"
            "• 01: Valor fixo em reais (ex: R$ 10,50)\n"
            "• 02: Percentual do valor do título (ex: 5% = 5.0)\n"
            "• 90: Percentual por antecipação (usa parâmetros do beneficiário)\n"
            "• 91: Valor por antecipação (usa parâmetros do beneficiário)\n\n"
            "⚠️ Importante: Todas as linhas de desconto terão este mesmo código_tipo_desconto.")

    discount_line_ids = fields.One2many(
        'account.payment.term.discount',
        'payment_term_id',
        string='Condições de Desconto',
        help="Configure múltiplas datas limite para o mesmo tipo de desconto.\n"
             "Exemplo: 10 dias (R$ 50), 5 dias (R$ 30), 2 dias (R$ 10)\n"
             "⚠️ API exige ordem decrescente de datas."
    )
    
    discount_summary = fields.Text(
        string='Resumo dos Descontos',
        compute='_compute_discount_summary',
        help="Resumo das condições de desconto configuradas"
    )
    
    @api.depends('discount_line_ids', 'itau_discount_code')
    def _compute_discount_summary(self):
        """Computa resumo das condições de desconto"""
        for record in self:
            if record.discount_line_ids and record.itau_discount_code != '00':
                tipo_desc = dict(record._fields['itau_discount_code'].selection)[record.itau_discount_code]
                linhas = []
                for line in record.discount_line_ids.sorted('days', reverse=True):
                    if record.itau_discount_code in ['02', '90']:
                        linhas.append(f"• {line.days} dias: {line.value}%")
                    else:
                        linhas.append(f"• {line.days} dias: R$ {line.value:.2f}")
                
                record.discount_summary = f"Tipo: {tipo_desc} (código {record.itau_discount_code})\n" + "\n".join(linhas)
            else:
                record.discount_summary = "Nenhuma condição de desconto configurada"
    
    @api.constrains('discount_line_ids', 'itau_discount_code')
    def _check_discount_consistency(self):
        """Valida consistência entre tipo de desconto e linhas configuradas"""
        for record in self:
            if record.itau_discount_code != '00' and not record.discount_line_ids:
                raise ValidationError(
                    _("Quando um tipo de desconto é selecionado, deve haver pelo menos uma linha de desconto configurada.")
                )
            
            if record.itau_discount_code == '00' and record.discount_line_ids:
                raise ValidationError(
                    _("Quando 'Sem Desconto' está selecionado, não deve haver linhas de desconto configuradas.")
                )
    
    def get_itau_discount_data(self, invoice_date):
        """
        Gera estrutura de desconto conforme API do Itaú
        
        Args:
            invoice_date (date): Data da fatura para calcular datas de desconto
            
        Returns:
            dict: Estrutura de desconto para API do Itaú ou {} se sem desconto
        """
        self.ensure_one()
        
        if not self.itau_discount_code or self.itau_discount_code == '00':
            return {}
        
        if not self.discount_line_ids:
            return {}
        
        descontos_list = []
        
        for line in self.discount_line_ids.sorted('days', reverse=True):
            from datetime import timedelta
            
            data_desconto = invoice_date + timedelta(days=line.days)
            
            desconto_info = {
                'data_desconto': data_desconto.strftime('%Y-%m-%d')
            }
            
            if self.itau_discount_code in ['02', '90']:
                percentual_formatado = "{:012.0f}".format(line.value * 10000000)
                desconto_info['percentual_desconto'] = percentual_formatado
                
            elif self.itau_discount_code in ['01', '91']:
                valor_em_centavos = int(line.value * 100)
                valor_formatado = "{:017d}".format(valor_em_centavos)                
                
                desconto_info['valor_desconto'] = valor_formatado
            
            descontos_list.append(desconto_info)
        
        if descontos_list:
            return {
                'codigo_tipo_desconto': self.itau_discount_code,
                'descontos': descontos_list
            }
        
        return {} 