from odoo import models, fields
from odoo.exceptions import UserError

class ParkingQueue(models.Model):
    _name = 'parking.queue'
    _description = 'Parking Queue'
    _inherit = 'mail.thread'
    _rec_name = 'name'


    name = fields.Char(string='Titulo da fila', tracking=True)
    description = fields.Text(string='Descrição', tracking=True)
    client_id = fields.Many2one('res.partner', string='Cliente', tracking=True)
    contract_capacity = fields.Integer(string='Quantidade de vagas contratadas', default=1, tracking=True)
    company_id = fields.Many2one('res.company', string='Pátio', tracking=True,default=lambda self: self.env.company.id, index=1)
    active = fields.Boolean(string='Ativo', default=True, tracking=True)
    state = fields.Selection([
        ('provisorio' , 'Provisório'),
        ('ativo' , 'Ativo')
    ],string='Status', default='provisorio', tracking=True)
    slot_ids = fields.One2many('parking.slots', 'queue_id', string='Vagas', tracking=True)
    intial_slot = fields.Integer(string='Vaga inicial', default=1, tracking=True)
    # todo: 
    # adicionar campo booking_ids to render bookings in queue
    # adiconar campo slots_ids to render slots in queue


    def add_slots(self):
        if self.state == 'provisorio' and self.contract_capacity > 1 and self.intial_slot > 0:
            for i in range(self.contract_capacity):
                new_slot = self.env['parking.slots'].create({
                    'name': str(self.intial_slot + i).zfill(2),
                    'company_id': self.company_id.id,
                    'queue_id': self.id
                })
            self.state = 'ativo'
        else:
            raise UserError('Não foi possível adicionar as vagas, verifique os campos |Quantidade de vagas contratadas| e |Vaga inicial| ')

