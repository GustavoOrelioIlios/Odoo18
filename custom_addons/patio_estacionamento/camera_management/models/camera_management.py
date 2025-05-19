from odoo import models, fields, api
import requests
import base64
from odoo.exceptions import UserError, ValidationError
from requests.auth import HTTPDigestAuth

class CameraManagement(models.Model):
    _name = 'camera.management'
    _description = 'Câmera de Segurança'
    _inherit = 'mail.thread'
    _rec_name = 'name'

    

    name = fields.Char(string='Nome', required=True, tracking=True)
    model = fields.Char(string='Modelo',tracking=True)
    ip_address = fields.Char(string='Endereço IP',tracking=True)
    username = fields.Char(string='Usuário',tracking=True)
    password = fields.Char(string='Senha',tracking=True)
    location = fields.Char(string='Localização',tracking=True)
    image_attachment_id = fields.Many2one('ir.attachment', string='Última Imagem Capturada', readonly=True,tracking=True)
    
    port = fields.Char(string='Porta', default='62800',tracking=True)



    camera_type = fields.Selection([
        ('checkin', 'Check-in'),
        ('checkout', 'Check-out')
    ], string='Tipo da Câmera', required=True,tracking=True)

    company_id = fields.Many2one('res.company', string='Pátio', required=True,tracking=True)
    
    @api.constrains('company_id', 'camera_type')
    def _check_camera_por_patio(self):
        for camera in self:
            cameras = self.search([('company_id', '=', camera.company_id.id)])
            if len(cameras) > 2:
                raise ValidationError("Cada pátio pode ter no máximo 2 câmeras.")
            
            tipos = [c.camera_type for c in cameras]
            if tipos.count('checkin') > 1 or tipos.count('checkout') > 1:
                raise ValidationError("As câmeras de um pátio devem ser uma de check-in e uma de check-out.")

    def capturar_imagem_ISAPI(self,res_model=False, res_id=False, image_name=False, operation='test'): 

        for camera in self:
            if not camera.ip_address:
                raise UserError("A câmera deve ter um endereço IP definido.")
            try:
                url = f"http://{camera.ip_address}:{camera.port}/ISAPI/Streaming/channels/1/picture"

                auth = None
                if camera.username and camera.password:
                    auth = HTTPDigestAuth(camera.username, camera.password)

                response = requests.get(url, auth=auth, timeout=5)

                if response.status_code == 200:
                    image_data = base64.b64encode(response.content)

                    attachment = self.env['ir.attachment'].create({
                        'name': f"{image_name}_snapshot.jpg" if image_name else f"{camera.name}_snapshot.jpg",
                        'type': 'binary',
                        'datas': image_data,
                        'res_model': res_model if res_model else self._name,
                        'res_id': res_id if res_id else camera.id,
                        'mimetype': 'image/jpeg',
                    })
                    if operation == 'test':                        
                        camera.image_attachment_id = attachment.id
                    else :
                        return attachment.id
                else:
                    raise UserError(f"Erro ao acessar a câmera. Código: {response.status_code}")

            except Exception as e:
                raise UserError(f"Erro ao capturar imagem: {str(e)}")

