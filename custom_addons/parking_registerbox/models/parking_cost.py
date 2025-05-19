from odoo import models, fields, api, _
from odoo.exceptions import UserError

class ParkingCost(models.Model):
    _name = 'parking.cost'
    _description = 'Regra de Cálculo de Valor por Hora'

    name = fields.Char(string='Nome da Regra', required=True)
    company_id = fields.Many2one('res.company', string='Pátio', required=True, default=lambda self: self.env.company.id)
    active = fields.Boolean(string='Ativo', default=True)
    value = fields.Float(string='Valor por Hora', required=True)

    def _check_active_rule(self, company_id, exclude_id=None):
        domain = [
            ('company_id', '=', company_id),
                ('active', '=', True)
        ]
        if exclude_id:
            domain.append(('id', '!=', exclude_id))
        
        exists = self.search(domain)
        if exists:
            raise UserError(_('Já existe uma regra ativa para este pátio. Desative a existente para criar/ativar uma nova.'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('active', True):
                self._check_active_rule(vals.get('company_id'))
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('active', True):
            for record in self:
                self._check_active_rule(record.company_id.id, record.id)
        return super().write(vals) 