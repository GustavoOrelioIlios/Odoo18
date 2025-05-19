from odoo import models, fields

class ParkingSlots(models.Model):
    _name = 'parking.slots'
    _description = 'Parking Slots'
    _inherit = 'mail.thread'
    _rec_name = 'name'

    name = fields.Char(string='Código', tracking=True)
    queue_id = fields.Many2one('parking.queue', string='Fila', tracking=True,ondelete='restrict')
    company_id = fields.Many2one('res.company', string='Pátio', tracking=True,default=lambda self: self.env.company.id, index=1)
    state = fields.Selection([
        ('livre', 'Livre'),
        ('ocupado', 'Ocupado')
    ], string='Status', default='livre', tracking=True)
    booking_id = fields.Many2one('parking.booking', string='Ocupado por', tracking=True,ondelete='restrict')
    active = fields.Boolean(string='Ativo', default=True, tracking=True)


    def release_slot(self):
        self.state = 'livre'
        self.booking_id = False
        self.message_post(body='Vaga liberada via rotina de forçar liberar a vaga')