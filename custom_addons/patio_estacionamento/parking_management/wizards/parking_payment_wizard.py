from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

class ParkingPaymentWizard(models.TransientModel):
    _name = 'parking.payment.wizard'
    _description = 'Assistente de Pagamento de Estacionamento'

    parking_booking_id = fields.Many2one('parking.booking', string='Agendamento', required=True)
    registerbox_id = fields.Many2one('parking.registerbox', string='Caixa', required=True,
                                   domain="[('state', '=', 'open'), ('create_uid', '=', uid)]")
    payment_form_id = fields.Many2one('parking.payment.form', string='Forma de Pagamento', required=True)
    amount = fields.Float(string='Valor', required=True)
    comment = fields.Text(string='Observação')

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        
        # Get the first open register box for the current user
        registerbox = self.env['parking.registerbox'].search([
            ('state', '=', 'open'),
            ('create_uid', '=', self.env.uid)
        ], limit=1)
        
        if registerbox:
            res['registerbox_id'] = registerbox.id
            
        return res

    def action_confirm_payment(self):
        self.ensure_one()
        
        if not self.registerbox_id:
            raise UserError(_('É necessário ter um caixa aberto para registrar o pagamento.'))
            
        if self.amount <= 0:
            raise UserError(_('O valor do pagamento deve ser maior que zero.'))
            
        if self.amount > self.parking_booking_id.remaining_amount:
            raise UserError(_('O valor do pagamento não pode ser maior que o valor restante.'))
            
        # Create payment line in registerbox
        vals = {
            'registerbox_id': self.registerbox_id.id,
            'payment_form_id': self.payment_form_id.id,
            'amount': self.amount,
            'operation_type': 'payment',
            'company_id': self.env.user.company_id.id,
            'comment': self.comment,
        }
        if self.parking_booking_id:
            vals['parking_booking_id'] = self.parking_booking_id.id

        self.env['parking.registerbox.line'].create(vals)
        
        return {'type': 'ir.actions.act_window_close'} 