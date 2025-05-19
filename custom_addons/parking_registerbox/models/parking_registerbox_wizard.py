from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import datetime

class ParkingRegisterBoxCashAddWizard(models.TransientModel):
    _name = 'parking.registerbox.cash.add.wizard'
    _description = 'Suprimento de Caixa'

    registerbox_id = fields.Many2one('parking.registerbox', string='Caixa', required=True)
    amount = fields.Monetary(string='Valor', required=True)
    currency_id = fields.Many2one('res.currency', related='registerbox_id.currency_id')
    comment = fields.Text(string='Motivo', required=True)

    def action_add_cash(self):
        self.ensure_one()
        if self.registerbox_id.state != 'open':
            raise UserError(_('Não é possível adicionar suprimento em um caixa fechado.'))
        
        self.env['parking.registerbox.line'].create({
            'registerbox_id': self.registerbox_id.id,
            'payment_form_id': self.env.ref('parking_registerbox.payment_form_cash').id,
            'amount': self.amount,
            'operation_type': 'add',
            'comment': self.comment,
        })
        return {'type': 'ir.actions.act_window_close'}

class ParkingRegisterBoxCashRemoveWizard(models.TransientModel):
    _name = 'parking.registerbox.cash.remove.wizard'
    _description = 'Sangria de Caixa'

    registerbox_id = fields.Many2one('parking.registerbox', string='Caixa', required=True)
    amount = fields.Monetary(string='Valor', required=True)
    currency_id = fields.Many2one('res.currency', related='registerbox_id.currency_id')
    comment = fields.Text(string='Motivo', required=True)

    def action_remove_cash(self):
        self.ensure_one()
        if self.registerbox_id.state != 'open':
            raise UserError(_('Não é possível fazer sangria em um caixa fechado.'))
        
        self.env['parking.registerbox.line'].create({
            'registerbox_id': self.registerbox_id.id,
            'payment_form_id': self.env.ref('parking_registerbox.payment_form_cash').id,
            'amount': -self.amount,
            'operation_type': 'remove',
            'comment': self.comment,
        })
        return {'type': 'ir.actions.act_window_close'}

class ParkingRegisterBoxReversalWizard(models.TransientModel):
    _name = 'parking.registerbox.reversal.wizard'
    _description = 'Estorno'

    registerbox_id = fields.Many2one('parking.registerbox', string='Caixa', required=True)
    line_id = fields.Many2one('parking.registerbox.line', string='Lançamento a Estornar', required=True,
                             domain="[('registerbox_id', '=', registerbox_id), "
                                   "('operation_type', '!=', 'reversal'), "
                                   "('reversal_line_ids', '=', [])]")
    amount = fields.Monetary(string='Valor', required=True)
    currency_id = fields.Many2one('res.currency', related='registerbox_id.currency_id')
    comment = fields.Text(string='Motivo do Estorno', required=True)
    
    # Campos informativos do lançamento selecionado
    selected_operation_type = fields.Selection(related='line_id.operation_type', string='Tipo de Operação', readonly=True)
    selected_payment_form = fields.Many2one(related='line_id.payment_form_id', string='Forma de Pagamento', readonly=True)
    selected_amount = fields.Monetary(related='line_id.amount', string='Valor Original', readonly=True)
    selected_comment = fields.Text(related='line_id.comment', string='Observação Original', readonly=True)

    @api.onchange('line_id')
    def _onchange_line_id(self):
        if self.line_id:
            # O estorno deve ter o sinal oposto ao lançamento original
            self.amount = -self.line_id.amount

    def action_reverse(self):
        self.ensure_one()
        if self.registerbox_id.state != 'open':
            raise UserError(_('Não é possível fazer estorno em um caixa fechado.'))
        
        if not self.line_id:
            raise UserError(_('Selecione um lançamento para estornar.'))

        if abs(self.amount) > abs(self.line_id.amount):
            raise UserError(_('O valor do estorno não pode ser maior que o valor do lançamento original.'))
        
        if self.amount == 0:
            raise UserError(_('O valor do estorno não pode ser zero.'))

        # Cria o lançamento de estorno
        self.env['parking.registerbox.line'].create({
            'registerbox_id': self.registerbox_id.id,
            'payment_form_id': self.line_id.payment_form_id.id,
            'amount': self.amount,
            'operation_type': 'reversal',
            'comment': self.comment,
            'reversed_line_id': self.line_id.id,
        })
        return {'type': 'ir.actions.act_window_close'} 