from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.osv import expression
from datetime import datetime

class ParkingRegisterBoxCloseWizard(models.TransientModel):
    _name = 'parking.registerbox.close.wizard'
    _description = 'Fechamento de Caixa'

    registerbox_id = fields.Many2one('parking.registerbox', string='Caixa', required=True)
    end_value = fields.Monetary(string='Valor de Fechamento', related='registerbox_id.calculated_end_value', readonly=True)
    comment = fields.Text(string='Observação')
    currency_id = fields.Many2one('res.currency', related='registerbox_id.currency_id')

    def action_close_box(self):
        self.ensure_one()
        self.registerbox_id.action_close_box_from_wizard(self.comment)
        return {'type': 'ir.actions.act_window_close'}

class ParkingRegisterBox(models.Model):
    _name = 'parking.registerbox'
    _description = 'Caixa de Estacionamento'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Nome', required=True, readonly=True, default='/')
    intial_value = fields.Monetary(string='Valor de Abertura', required=True)
    calculated_end_value = fields.Monetary(string='Valor de Fechamento', compute='_compute_end_value', store=True)
    currency_id = fields.Many2one('res.currency', string='Moeda', required=True, default=lambda self: self.env.company.currency_id.id)
    create_uid = fields.Many2one('res.users', string='Usuário de Abertura', readonly=True)
    end_user = fields.Many2one('res.users', string='Usuário de Fechamento', readonly=True)
    state = fields.Selection([
        ('open', 'Aberto'),
        ('close', 'Fechado')
    ], string='Status', default='open', tracking=True)
    comment = fields.Text(string='Observação')
    create_date = fields.Datetime(string='Data de Abertura', readonly=True)
    end_date = fields.Datetime(string='Data de Fechamento', readonly=True)
    company_id = fields.Many2one('res.company', string='Pátio', required=True, default=lambda self: self.env.company.id)
    register_line_ids = fields.One2many('parking.registerbox.line', 'registerbox_id', string='Lançamentos')

    @api.depends('intial_value', 'register_line_ids', 'register_line_ids.amount')
    def _compute_end_value(self):
        for box in self:
            total = box.intial_value
            for line in box.register_line_ids:
                total += line.amount
            box.calculated_end_value = total

    @api.constrains('state')
    def _check_state_changes(self):
        for record in self:
            if record.state == 'open' and record._origin.state == 'close':
                raise UserError(_('Não é permitido reabrir um caixa que já foi fechado.'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # Verifica se o usuário já tem caixa aberto
            open_box = self.search([('create_uid', '=', self.env.uid), ('state', '=', 'open')])
            if open_box:
                raise UserError(_('Você já possui um caixa aberto!'))
            
        if vals.get('name', '/') == '/':
            user = self.env.user
            now = fields.Datetime.now()
            vals['name'] = f"{user.name} {now.strftime('%d/%m/%Y %H:%M:%S')}"
            
            # Define o estado como aberto e a empresa do usuário
            vals['state'] = 'open'
            vals['company_id'] = self.env.user.company_id.id
            
        return super().create(vals_list)

    def action_close_box_from_wizard(self, comment):
        self.write({
            'state': 'close',
            'end_user': self.env.user.id,
            'end_date': fields.Datetime.now(),
            'comment': comment,
        }) 

    def action_close_box(self):
        self.ensure_one()
        return {
            'name': _('Fechar Caixa'),
            'type': 'ir.actions.act_window',
            'res_model': 'parking.registerbox.close.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_registerbox_id': self.id,
            }
        } 

    @api.model
    def search(self, args, offset=0, limit=None, order=None):
        if not args:
            args = []
        user = self.env.user
        if not self.env.is_superuser():
            if user.has_group('parking_management.group_parking_manager') and not user.has_group('parking_management.group_parking_admin'):
                args = expression.AND([args, [('create_uid', '=', user.id)]])
        return super(ParkingRegisterBox, self).search(args, offset=offset, limit=limit, order=order) 