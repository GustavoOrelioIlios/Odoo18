from odoo import models, fields

class ParkingRegisterBoxLine(models.Model):
    _inherit = 'parking.registerbox.line'
    parking_booking_id = fields.Many2one('parking.booking', string='Agendamento', ondelete='restrict', index=True, copy=False) 