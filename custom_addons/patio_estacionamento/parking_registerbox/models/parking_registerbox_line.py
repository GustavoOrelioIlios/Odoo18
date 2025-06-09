from odoo import models, fields, api
from odoo.exceptions import UserError
from odoo.osv import expression

class ParkingRegisterBoxLine(models.Model):
    _name = 'parking.registerbox.line'
    _description = 'Lançamentos do Caixa'
    _order = 'create_date desc'
    _rec_name = 'display_name'

    @api.depends('operation_type', 'payment_form_id', 'amount')
    def _compute_display_name(self):
        for record in self:
            operation_types = dict(self._fields['operation_type'].selection)
            operation_name = operation_types.get(record.operation_type, '')
            payment_form = record.payment_form_id.name or ''
            amount = record.amount
            if amount < 0:
                amount = f"({abs(amount):.2f})"
            else:
                amount = f"{amount:.2f}"
            record.display_name = f"{operation_name} - {payment_form} - {amount}"

    display_name = fields.Char(string='Display Name', compute='_compute_display_name', store=True)

    registerbox_id = fields.Many2one('parking.registerbox', string='Caixa', required=True, ondelete='cascade')
    payment_form_id = fields.Many2one('parking.payment.form', string='Forma de Pagamento', required=True)
    amount = fields.Monetary(string='Valor', required=True)
    currency_id = fields.Many2one('res.currency', related='registerbox_id.currency_id')
    operation_type = fields.Selection([
        ('payment', 'Pagamento'),
        ('add', 'Suprimento'),
        ('remove', 'Sangria'),
        ('reversal', 'Estorno')
    ], string='Tipo de Operação', required=True, default='payment')
    reversed_line_id = fields.Many2one('parking.registerbox.line', string='Lançamento Estornado')
    reversal_line_ids = fields.One2many('parking.registerbox.line', 'reversed_line_id', string='Estornos')
    comment = fields.Text(string='Observação')
    company_id = fields.Many2one('res.company', string='Pátio', required=True, default=lambda self: self.env.company.id)
    create_date = fields.Datetime(string='Data do Lançamento', readonly=True)
    create_uid = fields.Many2one('res.users', string='Usuário', readonly=True)
    parking_booking_id = fields.Many2one(
        'parking.booking',
        string='Agendamento',
        ondelete='restrict',
        index=True,
        copy=False
    )

    @api.constrains('registerbox_id', 'operation_type')
    def _check_box_state(self):
        for line in self:
            if line.registerbox_id.state != 'open':
                raise UserError(('Não é possível criar lançamentos em um caixa fechado.'))

    @api.constrains('amount', 'operation_type')
    def _check_amount(self):
        for line in self:
            if line.operation_type == 'reversal':
                if abs(line.amount) > abs(line.reversed_line_id.amount):
                    raise UserError(('O valor do estorno não pode ser maior que o valor do lançamento original.'))
                if line.amount == line.reversed_line_id.amount:
                    raise UserError(('O valor do estorno deve ter sinal oposto ao lançamento original.'))

    @api.model
    def search(self, args, offset=0, limit=None, order=None):
        if not args:
            args = []
        user = self.env.user
        if not self.env.is_superuser():
            if user.has_group('parking_management.group_parking_manager') and not user.has_group('parking_management.group_parking_admin'):
                args = expression.AND([args, [('create_uid', '=', user.id)]])
        return super(ParkingRegisterBoxLine, self).search(args, offset=offset, limit=limit, order=order)