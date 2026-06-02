from odoo import models, fields, api, _
from odoo.exceptions import UserError
import requests
import json
import logging
import time

_logger = logging.getLogger(__name__)

OPPO_API_URL = "https://ilockcardf-isp.apps.coloros.com"

class OppoLock(models.Model):
    _name = 'oppo.lock'
    _description = 'Oppo Device Lock'

    lock_title = fields.Char('Lock Title', required=False)
    lock_message = fields.Text('Lock Message', required=False)
    device_name = fields.Char('Device Name/IMEI', required=False)
    customer_name= fields.Char(string="Customer")
    repayment_id = fields.Many2one('repayment', string='Customer', required=True, ondelete='cascade')
    imei_list = fields.Text('IMEI List', help='JSON array of IMEIs',required=True)
    device_uid = fields.Char('Device UID', required=False, help='Primary IMEI')
    expired_time = fields.Char('Expired Time (ms)', help='Expiration time in milliseconds')
    display_type = fields.Selection([
        ('0', 'Dialog'),
        ('1', 'Full Screen'),
    ], default='1', string='Display Type')

    # Message content fields
    one_day_title = fields.Char('One Day Title', default='Payment Required')
    one_day_content = fields.Text('One Day Content', default='Your plan expires soon. Please pay to continue.')
    three_day_title = fields.Char('Three Day Title', default='Payment Overdue')
    three_day_content = fields.Text('Three Day Content', default='Your device will lock if payment is not made.')
    seven_day_title = fields.Char('Seven Day Title', default='Device Locked')
    seven_day_content = fields.Text('Seven Day Content', default='Your device is locked. Please pay to unlock.')

    status = fields.Selection([
        ('-1', 'Error'),
        ('0', 'Normal'),
        ('1', 'Locked'),
        ('2', 'Locking'),
        ('3', 'Completed'),
        ('4', 'Completing'),
        ('5', 'Unlocking'),
        ('7', 'Activating'),
        ('8', 'Releasing PhoneLOCK'),
        ('9', 'Released PhoneLOCK'),
        ('10', 'Releasing SIMLOCK'),
        ('11', 'Released SIMLOCK'),
        ('12', 'Deleting'),
        ('13', 'Deleted'),
        ('14', 'CK Unlock'),
    ], default='0', string='Lock Status')
    lock_date = fields.Datetime('Lock Date')
    api_response = fields.Text('API Response', readonly=True)
    x_sign = fields.Char('Generated X-Sign', readonly=True)
    
    # @api.onchange('device_uid')
    # def _onchange_device_uid(self):
    #     """Auto-populate imei_list with device_uid"""
    #     if self.device_uid:
    #         self.imei_list = json.dumps([self.device_uid])
    #         self.name = self.device_uid

    @api.onchange('repayment_id')
    def _onchange_repayment_id(self):
        """Auto-populate imei_list from repayment product lines"""
        if self.repayment_id and self.repayment_id.product_lines:
            imeis = []
            for line in self.repayment_id.product_lines:
                if line.lot_id:
                    for lot in line.lot_id:
                        if lot.name:
                            imeis.append(lot.name)

            if imeis:
                self.imei_list = json.dumps(imeis)
                # Set device_uid to the first IMEI if not set
                # if not self.device_uid and imeis:
                #     self.device_uid = imeis[0]
                #     self.name = imeis[0]

    def _generate_x_sign(self, request_body):
        """Generate x-sign signature using the signing server"""
        self.ensure_one()

        oppo_credentials = self.env['res.config.settings'].get_oppo_credentials()
        carrier_code = oppo_credentials.get('carrier_code')
        token = oppo_credentials.get('token')
        signature_server_url = oppo_credentials.get('signature_server_url')

        if not carrier_code or not token:
            raise UserError(_('Oppo carrier code or token is not configured. Please configure it in the settings.'))

        if not signature_server_url:
            raise UserError(_('Signature server URL is not configured. Please configure it in the settings.'))

        # Stringify the request body as JSON
        data_string = json.dumps(request_body, separators=(',', ':'))

        payload = {
            "carrierCode": carrier_code,
            "token": token,
            "data": data_string
        }

        try:
            response = requests.post(
                signature_server_url,
                headers={'Content-Type': 'application/json'},
                json=payload,
                timeout=30
            )
            response.raise_for_status()

            response_data = response.json()
            _logger.info(f"Signature server response: {response_data}")

            if response_data.get('status') == 'success':
                return response_data.get('x-sign')
            else:
                raise UserError(_('Failed to generate x-sign: %s') % response_data.get('error', 'Unknown error'))

        except requests.exceptions.RequestException as e:
            _logger.error(f"Error calling signature server: {e}")
            raise UserError(_('Failed to connect to signature server: %s') % str(e))


    def action_lock_device(self):
        """Lock device using Oppo prepaid/edit API"""
        for record in self:
            # Check if deviceUid, title, message and imeiList is not empty
            if not record.device_uid:
                raise UserError(_('Device UID is required. Please enter the device UID.'))
            if not record.lock_title:
                raise UserError(_('Lock Title is required. Please enter the lock title.'))
            if not record.lock_message:
                raise UserError(_('Lock Message is required. Please enter the lock message.'))
            

            oppo_credentials = self.env['res.config.settings'].get_oppo_credentials()
            carrier_code = oppo_credentials.get('carrier_code')

            if not carrier_code:
                raise UserError(_('Oppo carrier code is not configured. Please configure it in the settings.'))

            # Use device_uid if available, otherwise use imei_list
            if record.device_uid:
                request_body = {
                    "title": record.lock_title,
                    "message": record.lock_message,
                    "deviceUid": record.device_uid
                }
            else:
                try:
                    imei_list = json.loads(record.imei_list) if isinstance(record.imei_list, str) else []
                except json.JSONDecodeError:
                    imei_list = []

                if not imei_list:
                    raise UserError(_('Device UID or IMEI list is required to check status.'))

                request_body = {
                    "title": record.lock_title,
                    "message": record.lock_message,
                    "imeiList": imei_list
                }

            if not imei_list:
                raise UserError(_('IMEI List is required. Please enter at least one IMEI.'))

            # Build request body
            # request_body = {
                
            #     "imeiList": imei_list,
            # }

            # Generate x-sign
            x_sign = record._generate_x_sign(request_body)
            record.x_sign = x_sign

            _logger.info(f"X-Sign: {x_sign}")
            _logger.info(f"Carrier Code: {carrier_code}")

            # Call Oppo API
            headers = {
                'Content-Type': 'application/json',
                'x-carrier-code': carrier_code,
                'x-sign': x_sign
            }

            try:
                response = requests.post(
                    f"{OPPO_API_URL}/lock",
                    headers=headers,
                    json=request_body
                )
                response.raise_for_status()

                response_data = response.json()
                _logger.info(f"Oppo API response: {response_data}")

                record.api_response = json.dumps(response_data, indent=2)

                if response_data.get('code') == 0:
                    record.write({
                        'status': '1',
                        'lock_date': fields.Datetime.now()
                    })
                    record.message_post(
                        body=f'Device locked successfully via Oppo API',
                        message_type='comment',
                        subtype_xmlid='mail.mt_note'
                    )
                else:
                    record.write({'status': '-1'})
                    raise UserError(_('Oppo API error: %s') % response_data.get('errorInfo', 'Unknown error'))

            except requests.exceptions.RequestException as e:
                _logger.error(f"Error calling Oppo API: {e}")
                record.write({'status': '-1'})
                raise UserError(_('Failed to lock device via Oppo API: %s') % str(e))

    def action_unlock_device(self):
        """Unlock device using Oppo prepaid/unlock API"""
        for record in self:
            oppo_credentials = self.env['res.config.settings'].get_oppo_credentials()
            carrier_code = oppo_credentials.get('carrier_code')

            if not carrier_code:
                raise UserError(_('Oppo carrier code is not configured. Please configure it in the settings.'))

            # if record.status != '1':
            #     raise UserError(_('Device is not currently locked.'))

            # Parse IMEI list
            # Use device_uid if available, otherwise use imei_list
            if record.device_uid:
                request_body = {
                    "deviceUid": record.device_uid
                }
            else:
                try:
                    imei_list = json.loads(record.imei_list) if isinstance(record.imei_list, str) else []
                except json.JSONDecodeError:
                    imei_list = []

                if not imei_list:
                    raise UserError(_('Device UID or IMEI list is required to check status.'))

                request_body = {
                    "imeiList": imei_list
                }

            # Build request body
            request_body = {
                "imeiList": imei_list,
            }

            # Generate x-sign
            x_sign = record._generate_x_sign(request_body)
            record.x_sign = x_sign

            # Call Oppo API
            headers = {
                'Content-Type': 'application/json',
                'x-carrier-code': carrier_code,
                'x-sign': x_sign
            }

            try:
                response = requests.post(
                    f"{OPPO_API_URL}/unlock",
                    headers=headers,
                    json=request_body,
                    timeout=30
                )
                response.raise_for_status()

                response_data = response.json()
                _logger.info(f"Oppo unlock API response: {response_data}")

                record.api_response = json.dumps(response_data, indent=2)

                if response_data.get('code') == 0:
                    record.write({
                        'status': '0',
                        'lock_date': fields.Datetime.now()
                    })
                    record.message_post(
                        body=f'Device unlocked successfully via Oppo API',
                        message_type='comment',
                        subtype_xmlid='mail.mt_note'
                    )
                else:
                    record.write({'status': '-1'})
                    raise UserError(_('Oppo API error: %s') % response_data.get('errorInfo', 'Unknown error'))

            except requests.exceptions.RequestException as e:
                _logger.error(f"Error calling Oppo unlock API: {e}")
                record.write({'status': '-1'})
                raise UserError(_('Failed to unlock device via Oppo API: %s') % str(e))

    def action_get_device_status(self):
        """Get device status from Oppo API"""
        for record in self:
            oppo_credentials = self.env['res.config.settings'].get_oppo_credentials()
            carrier_code = oppo_credentials.get('carrier_code')

            if not carrier_code:
                raise UserError(_('Oppo carrier code is not configured. Please configure it in the settings.'))

            # Use device_uid if available, otherwise use imei_list
            if record.device_uid:
                request_body = {
                    "deviceUid": record.device_uid
                }
            else:
                try:
                    imei_list = json.loads(record.imei_list) if isinstance(record.imei_list, str) else []
                except json.JSONDecodeError:
                    imei_list = []

                if not imei_list:
                    raise UserError(_('Device UID or IMEI list is required to check status.'))

                request_body = {
                    "imeiList": imei_list
                }

            # Generate x-sign
            x_sign = record._generate_x_sign(request_body)
            record.x_sign = x_sign

            # Generate transaction ID
            # import uuid
            # transaction_id = str(uuid.uuid4())

            # Call Oppo API
            headers = {
                'Content-Type': 'application/json',
                'x-carrier-code': carrier_code,
                'x-sign': x_sign,
                # 'x-transactionId': transaction_id
            }

            try:
                response = requests.post(
                    f"{OPPO_API_URL}/getStatus",
                    headers=headers,
                    json=request_body
                )
                response.raise_for_status()

                response_data = response.json()
                _logger.info(f"Oppo getStatus API response: {response_data}")

                record.api_response = json.dumps(response_data, indent=2)

                # Map API status codes to our status field
                api_status = response_data.get('status')

                new_status = str(api_status) if api_status is not None else '-1'
                record.write({'status': new_status})

                return {
                    'status': new_status,
                    'api_status': api_status,
                    'info': response_data.get('info', ''),
                    'result': response_data.get('result', '')
                }

            except requests.exceptions.RequestException as e:
                _logger.error(f"Error calling Oppo getStatus API: {e}")
                record.write({'status': '-1'})
                raise UserError(_('Failed to get device status from Oppo API: %s') % str(e))