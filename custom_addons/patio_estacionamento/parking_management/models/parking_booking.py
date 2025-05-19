from odoo import models, fields,api
from odoo.exceptions import UserError, ValidationError
import re

class ParkingBooking(models.Model):
    _name = 'parking.booking'
    _description = 'Parking Booking'
    _inherit = 'mail.thread' 
    _rec_name = 'tractor_plate'

    name = fields.Char(string='Código de agendamento', tracking=True)
    start_date = fields.Datetime(string='Previsão de chegada', tracking=True)
    end_date = fields.Datetime(string='Previsão de saída', tracking=True)
    checkin_date = fields.Datetime(string='Data de entrada', tracking=True)
    checkout_date = fields.Datetime(string='Data de saída', tracking=True)
    contract_id = fields.Char(string='ID. Contrato', tracking=True)
    contract_external_id = fields.Char(string='Referência Externa do Contrato', tracking=True)
    client_id = fields.Many2one('res.partner', string='Cliente', tracking=True, domain="[('category_id', 'ilike', 'cliente')]",ondelete='restrict')
    parking_queue_id = fields.Many2one('parking.queue', string='Fila', tracking=True,ondelete='restrict')
    parking_slot_id = fields.Many2one('parking.slots', string='Vaga', tracking=True, domain="[('state', '=', 'livre')]",ondelete='restrict')
    company_id = fields.Many2one('res.company', string='Pátio', tracking=True,ondelete='restrict',default=lambda self: self.env.company.id, index=1)
    operation = fields.Char(string='Operação', tracking=True)
    product = fields.Char(string='Produto', tracking=True)
    cargo_packaging = fields.Char(string='Embalagem', tracking=True)
    booking_cargo_weight = fields.Float(string='Peso Agendado', tracking=True)
    planta_code = fields.Char(string='Código da Planta', tracking=True)
    parking_lot_code = fields.Char(string='Código do pátio', tracking=True)
    cargo_cliente_name= fields.Char(string='Nome do Cliente da Carga', tracking=True)
    cargo_cliente_cnpj = fields.Char(string='CNPJ do Cliente da Carga', tracking=True)
    carrier_name = fields.Char(string='Transportadora', tracking=True)
    carrier_cnpj = fields.Char(string='CNPJ da Transportadora', tracking=True)
    driver_name = fields.Char(string='Nome do Motorista', tracking=True)
    driver_cpf = fields.Char(string='CPF do Motorista', tracking=True)
    driver_mobile = fields.Char(string='Celular do Motorista', tracking=True)
    observation = fields.Text(string='Observações', tracking=True)
    user_id_checkin = fields.Many2one('res.users', string='Responsável pela entrada')
    user_id_checkout = fields.Many2one('res.users', string='Responsável pela saída')
    state = fields.Selection([
        ('provisorio', 'Provisório'),
        ('agendado', 'Agendado'),
        ('checkin', 'Entrada'),
        ('checkout', 'Saída'),
        ('cancelado', 'Cancelado'),
    ], string='Status', default='provisorio', tracking=True)
    active = fields.Boolean(string='Ativo', default=True, tracking=True)
    tractor_plate = fields.Char(string='Placa do Cavalo', tracking=True,size=8)
    trailer_plate_1 = fields.Char(string='Placa da Carreta 1', tracking=True)
    trailer_plate_2 = fields.Char(string='Placa da Carreta 2', tracking=True)
    trailer_plate_3 = fields.Char(string='Placa da Carreta 3', tracking=True)

    def write(self, vals):
        if 'state' in vals and vals['state'] == 'checkin' and not vals.get('parking_slot_id', self.parking_slot_id):
            raise ValidationError("Necessario informar a vaga quando o estado é Check-In/Entrada.")
        if 'active' in vals and not vals['active'] and self.state == 'checkin':
            raise ValidationError("Não é possível arquivar um agendamento com estado Check-In/Entrada.")
        return super(ParkingBooking, self).write(vals)

    def unlink(self):
        for record in self:
            if record.state == 'checkin':
                raise ValidationError("Não é possível excluir um agendamento com estado Check-In/Entrada.")
        return super(ParkingBooking, self).unlink()

    @api.constrains('tractor_plate', 'trailer_plate_1', 'trailer_plate_2', 'trailer_plate_3')
    def _check_plate_format(self):
        for record in self:
            # List of fields to validate
            plates = {
                'tractor_plate': record.tractor_plate,
                'trailer_plate_1': record.trailer_plate_1,
                'trailer_plate_2': record.trailer_plate_2,
                'trailer_plate_3': record.trailer_plate_3,
            }

            # Validate each plate
            for field_name, plate in plates.items():
                if plate:  # Only validate if the field is not empty
                    plate_upper = plate.upper()  # Convert to uppercase
                    
                    # Pattern 1: 3 letters followed by 4 numbers (with or without hyphen)
                    pattern1 = r'^[A-Z]{3}[-]?\d{4}$'
                    
                    # Pattern 2: 3 letters, 1 number, 1 letter, 2 numbers (Mercosul format)
                    pattern2 = r'^[A-Z]{3}\d[A-Z]\d{2}$'
                    
                    if not (re.match(pattern1, plate_upper) or re.match(pattern2, plate_upper)):
                        raise ValidationError(
                            f"A placa no campo '{self._fields[field_name].string}' deve seguir um dos seguintes formatos:\n"
                            "1. 3 letras seguidas de 4 números (Exemplo: ABC1234 ou ABC-1234).\n"
                            "2. 3 letras, 1 número, 1 letra, 2 números (Formato Mercosul, exemplo: ABC1D23)."
                        )

    def truck_checkin(self):
        if not self.parking_slot_id:
            raise UserError('Necessario informar a vaga para fazer checkin')
        
        
        if not self.parking_slot_id.state == 'livre':
            raise UserError(f'Vaga já ocupada por outro veículo com placa : {self.parking_slot_id.booking_id.tractor_plate}')
        else:
            self.state = 'checkin'
            self.parking_slot_id.state = 'ocupado'
            self.parking_slot_id.booking_id = self.id
            self.checkin_date = fields.Datetime.now()
            self.user_id_checkin = self.env.user.id

        
        #set patio id 
        if not self.company_id:
            self.company_id = self.env.user.company_id.id
        
        # set fila id
        if not self.parking_queue_id:
            if self.parking_slot_id:
                self.parking_queue_id = self.parking_slot_id.queue_id.id
            
        # captura imagem da camera de checkin
        self.capture_camera_image(operation='checkin')

    
    def truck_checkout(self):
        # liberar vaga soment se a vaga estiver ocupada pelo veiculo que esta fazendo checkout
        if self.parking_slot_id.booking_id.id == self.id:
            self.parking_slot_id.state = 'livre'
            self.parking_slot_id.booking_id = False
        self.state = 'checkout'
        self.checkout_date = fields.Datetime.now()
        self.user_id_checkout = self.env.user.id
        # captura imagem da camera de checkout
        self.capture_camera_image(operation='checkout')
        
    def capture_camera_image(self,operation):
        camera = self.env['camera.management'].search([('camera_type', '=', operation), ('company_id', '=', self.company_id.id)], limit=1)
        if camera:
            attchment_id = camera.capturar_imagem_ISAPI(self._name,self.id, self.tractor_plate, operation=operation)            
            if attchment_id: # add the attchement_id to the parking booking attachments in chatter
                self.message_post(body=f"Imagem capturada durante o {operation}", attachment_ids=[attchment_id])
        else:
            self.message_post(body=f"Não foi possível capturar a imagem do {operation}, câmera não encontrada.")

    @api.onchange('client_id')
    def _onchange_client_id(self):
        if self.client_id:
            available_queues = self.env['parking.queue'].search([('client_id', '=', self.client_id.id)])
            parking_slots = self.env['parking.slots'].search([('queue_id', 'in', available_queues.ids), ('state', '=', 'livre')])
            self.parking_slot_id = parking_slots[0] if parking_slots else False

            
    @api.onchange('tractor_plate')
    def _onchange_tractor_plate(self):
        if self.tractor_plate:
            self.tractor_plate = self.tractor_plate.upper()
















        