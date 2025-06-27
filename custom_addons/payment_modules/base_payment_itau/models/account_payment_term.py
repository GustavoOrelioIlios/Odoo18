# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class AccountPaymentTerm(models.Model):
    _inherit = 'account.payment.term'

    # Campo para definir o tipo de desconto conforme API Itaú
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

    # Campo One2many para as linhas de desconto
    discount_line_ids = fields.One2many(
        'account.payment.term.discount',
        'payment_term_id',
        string='Condições de Desconto',
        help="Configure múltiplas datas limite para o mesmo tipo de desconto.\n"
             "Exemplo: 10 dias (R$ 50), 5 dias (R$ 30), 2 dias (R$ 10)\n"
             "⚠️ API exige ordem decrescente de datas."
    )
    
    # Campo computado para mostrar resumo das condições
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
                for line in record.discount_line_ids.sorted('days', reverse=True):  # Ordem decrescente como API exige
                    if record.itau_discount_code in ['02', '90']:  # Percentual
                        linhas.append(f"• {line.days} dias: {line.value}%")
                    else:  # Valor fixo
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
        
        # Se não há tipo de desconto ou é '00', retorna vazio
        if not self.itau_discount_code or self.itau_discount_code == '00':
            return {}
        
        # Se não há linhas de desconto, retorna vazio
        if not self.discount_line_ids:
            return {}
        
        # Monta lista de descontos ordenada por dias (API exige ordem decrescente)
        descontos_list = []
        
        for line in self.discount_line_ids.sorted('days', reverse=True):  # Ordem decrescente
            from datetime import timedelta
            
            # Calcula data do desconto
            data_desconto = invoice_date + timedelta(days=line.days)
            
            desconto_info = {
                'data_desconto': data_desconto.strftime('%Y-%m-%d')
            }
            
            # Adiciona valor ou percentual conforme tipo
            if self.itau_discount_code in ['02', '90']:  # Percentual
                # Formato: 7 dígitos inteiros e 5 casas decimais (total 12 dígitos)
                # Exemplo: 5.0% = "005000000000" 
                percentual_formatado = "{:012.0f}".format(line.value * 10000000)
                desconto_info['percentual_desconto'] = percentual_formatado
                
            elif self.itau_discount_code in ['01', '91']:  # Valor fixo
                # Formato: 15 dígitos inteiros e 2 casas decimais (total 17 dígitos)
                # Exemplo: R$ 10.50 = "00000000001050" (15 dígitos) + "50" (2 decimais) = "0000000000105050"
                valor_em_centavos = int(line.value * 100)  # Converte para centavos
                valor_formatado = "{:017d}".format(valor_em_centavos)
                
                # Log para debug
                import logging
                _logger = logging.getLogger(__name__)
                _logger.info("🔍 DEBUG VALOR DESCONTO - Valor original: %s, Em centavos: %d, Formatado: %s (len: %d)", 
                            line.value, valor_em_centavos, valor_formatado, len(valor_formatado))
                
                desconto_info['valor_desconto'] = valor_formatado
            
            descontos_list.append(desconto_info)
        
        # Retorna estrutura completa
        if descontos_list:
            return {
                'codigo_tipo_desconto': self.itau_discount_code,
                'descontos': descontos_list
            }
        
        return {} 