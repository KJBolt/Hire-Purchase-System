from odoo import models, fields, api, _
from odoo.exceptions import UserError
import requests
import json
import logging
_logger = logging.getLogger(__name__)

class NuovoPayLock(models.Model):
    _name = 'nuovopay.lock'
    _description = 'NuovoPay Device Lock'

    name = fields.Char('Device Name/IMEI', required=True)
    repayment_id = fields.Many2one('repayment', string='Splitpay Customer', required=True)
    device_id = fields.Char('NuovoPay Device ID')
    type=fields.Selection([
        ('AndroidDevice', 'AndroidDevice'),
        ('WindowsDevice', 'WindowsDevice'),
    ], default='AndroidDevice', string='Device Type', help="The device OS (e.g., Android, iOS)")
    device_group_id = fields.Char('Device Group ID', help="Specify whether it belongs to a group")
    is_tv = fields.Boolean('Is TV')
    manufacturer = fields.Char('Manufacturer')
    customer_id = fields.Char(
        string='Customer ID',
        related='repayment_id.unique_id',
        store=True
    )
    imei_no = fields.Char('IMEI Number', required=True, help="Device IMEI (very important for Android phones)")
    serial_no = fields.Char('Serial Number', required=True, help="Device serial number")
    first_lock_date = fields.Datetime('First Lock Date', help="When locking policy should start")

    # User details
    user_first_name = fields.Char('User First Name')
    user_last_name = fields.Char('User Last Name')
    user_phone = fields.Char(
        string='User Phone',
        related='repayment_id.customer_name.phone',
        store=True, 
        readonly=False
    )
    user_email = fields.Char(
        string='User Email',
        related='repayment_id.customer_name.email',
        store=True,
        readonly=False
    )
    user_address = fields.Char('User Address', compute='_compute_customer_address', store=True, readonly=False)
    user_country = fields.Char('User Country', compute='_compute_customer_address', store=True, readonly=False)

    status = fields.Selection([
        ('locked', 'Locked'),
        ('unlocked', 'Unlocked'),
    ], default='unlocked', string='Lock Status')
    lock_date = fields.Datetime('Lock Date')
    unlock_date = fields.Datetime('Unlock Date')

    # api_response = fields.Text('API Response', readonly=True)
    enrollment_code = fields.Char('Enrollment Code', readonly=True)
    qr_code_data = fields.Text('QR Code Data', readonly=True)
    huawei_qrcode_data = fields.Text('Huawei QR Code Data', readonly=True)


    @api.model
    def create(self, vals):
        record = super(NuovoPayLock, self).create(vals)
        return record.action_register_device() or record

    def action_register_device(self):
        for record in self:
            nuovopay_credentials = self.env['res.config.settings'].get_nuovopay_credentials()
            api_key = nuovopay_credentials.get('api_key')
            api_url = nuovopay_credentials.get('api_url')

            if not api_key or not api_url:
                raise UserError(_('NuovoPay API key or URL is not configured. Please configure it in the settings.'))

            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Token {api_key}'
            }

            payload = {
                "device": {
                    "type": record.type or "android",
                    "device_group_id": record.device_group_id,
                    "is_tv": record.is_tv,
                    "manufacturer": record.manufacturer,
                    "customer_id": record.customer_id,
                    "imei_no": record.imei_no,
                    "serial_no": record.serial_no,
                    "first_lock_date": record.first_lock_date.strftime('%Y-%m-%d') if record.first_lock_date else None
                }
            }

            try:
                response = requests.post(f"{api_url}/dm/api/v1/devices/register.json", headers=headers, data=json.dumps(payload))
                response.raise_for_status() 

                response_data = response.json()
                _logger.info(f"Response from NuovoPay: {response_data}")

                # Extract and store the response data
                if response_data.get('success'):
                    record.write({
                        'device_id': str(response_data.get('device_id')),
                        'enrollment_code': response_data.get('enrollment_code'),
                        'qr_code_data': json.dumps(response_data.get('qr_code_data'), indent=4) if response_data.get('qr_code_data') else False,
                        'huawei_qrcode_data': json.dumps(response_data.get('huawei_qrcode_data'), indent=4) if response_data.get('huawei_qrcode_data') else False
                    })
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'reload',
                    }
                    
                

            except requests.exceptions.RequestException as e:
                _logger.error(f"Error registering device with NuovoPay: {e}")
                raise UserError(_(f"Failed to register device with NuovoPay: {e}"))


    @api.depends('repayment_id')
    def _compute_customer_address(self):
        _logger.info("Computing customer address...")
        for record in self:
            if record.repayment_id and record.repayment_id.customer_name:
                partner = record.repayment_id.customer_name
                _logger.info(f"Partner UTX => {partner}")

                # Split partner name
                if partner.name:
                    name_parts = partner.name.strip().split(' ', 1)
                    record.user_first_name = name_parts[0]
                    record.user_last_name = name_parts[1] if len(name_parts) > 1 else ''
                else:
                    record.user_first_name = False
                    record.user_last_name = False

                # Address and country  
                if partner.street:
                    record.user_address = partner.street
                if partner.country_id:
                    record.user_country = partner.country_id.name
            else:
                record.user_first_name = False
                record.user_last_name = False
                record.user_address = False
                record.user_country = False