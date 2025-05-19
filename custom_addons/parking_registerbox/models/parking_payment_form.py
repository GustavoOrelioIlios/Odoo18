from odoo import models, fields

class ParkingPaymentForm(models.Model):
    _name = 'parking.payment.form'
    _description = 'Forma de Pagamento do Estacionamento'

    name = fields.Char(string='Nome', required=True) 
    active = fields.Boolean(string='Ativo', default=True)
    company_id = fields.Many2one('res.company', string='Pátio', required=True, default=lambda self: self.env.company.id) 