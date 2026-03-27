from odoo import http
from odoo.http import request
import logging
import json
import requests

_logger = logging.getLogger(__name__)

class NuovoLockController(http.Controller):

    def _get_credentials(self):
        nuovopay_credentials = request.env['res.config.settings'].sudo().get_nuovopay_credentials()
        _logger.info(f"NuovoPay credentials: {nuovopay_credentials}")
        api_key = nuovopay_credentials.get('api_key')
        api_url = nuovopay_credentials.get('api_url')
        return api_key, api_url

    # List all devices
    @http.route('/dm/api/v1/devices.json', type='http', auth='public', methods=['GET'], website=True, csrf=False)
    def get_devices(self, **kwargs):
        return request.render('gobtechnologies.nuovo_lock_template')

    # Lock device
    @http.route('/nuovopay/devices/lock', type='json', auth='user', methods=['POST'], csrf=False)
    def lock_device(self, device_id, **kwargs):
        api_key, api_url = self._get_credentials()
        if not api_key or not api_url:
            return {'success': False, 'error': 'NuovoPay API key or URL is not configured.'}

        headers = {
            'Authorization': f'Token {api_key}',
        }

        payload = {
            'device_ids[]': [device_id],
        }
        
        try:
            response = requests.patch(
                f"{api_url}/dm/api/v1/devices/lock.json",
                headers=headers,
                data=payload
            )
            result = response.json() if response.content else {}
            _logger.info(f"NuovoPay lock response: {result.get('errors', 'No errors')}")
            if result.get('success'):
                record = request.env['nuovopay.lock'].sudo().search([('device_id', '=', str(device_id))], limit=1)
                if record:
                    record.write({'status': 'locked', 'lock_date': datetime.now()})
            else:
                return {'success': False, 'error': result.get('errors', 'Unknown error')}
        except Exception as e:
            _logger.error(f"NuovoPay lock API error: {e}")
            return {'success': False, 'error': str(e)}

    # Unlock device
    @http.route('/nuovopay/devices/unlock', type='json', auth='user', methods=['POST'], csrf=False)
    def unlock_device(self, device_id, **kwargs):
        api_key, api_url = self._get_credentials()
        if not api_key or not api_url:
            return {'success': False, 'error': 'NuovoPay API key or URL is not configured.'}

        headers = {
            'Authorization': f'Token {api_key}',
            'Content-Type': 'application/json'
        }

        payload = {
            'device_ids[]': [device_id],
        }

        try:
            response = requests.patch(
                f"{api_url}/dm/api/v1/devices/unlock.json",
                headers=headers,
                data= payload
            )
            result = response.json() if response.content else {}
            if result.get('success'):
                record = request.env['nuovopay.lock'].sudo().search([('device_id', '=', str(device_id))], limit=1)
                if record:
                    record.write({'status': 'unlocked', 'unlock_date': datetime.now()})
            else:
                return {'success': False, 'error': result.get('errors', 'Unknown error')}
            return result
        except Exception as e:
            _logger.error(f"NuovoPay unlock API error: {e}")
            return {'success': False, 'error': str(e)}

    # Unregister device
    @http.route('/nuovopay/devices/unregister', type='json', auth='user', methods=['POST'], csrf=False)
    def unregister_device(self, device_id, odoo_record_id, **kwargs):
        _logger.info(f"Unregistering device {device_id} with Odoo record ID {odoo_record_id}")
        api_key, api_url = self._get_credentials()
        if not api_key or not api_url:
            return {'success': False, 'error': 'NuovoPay API key or URL is not configured.'}

        headers = {
            'Authorization': f'Token {api_key}'
            # Remove Content-Type header to let requests set it automatically for form data
        }
        
        # Use form data instead of JSON
        payload = {
            'device_ids[]': [device_id],  # Array parameter as required
            'delete_device': True         # Optional parameter with default value
        }

        try:
            response = requests.post(
                f"{api_url}/dm/api/v2/devices/unregister.json",  # Use v2 API
                headers=headers,
                data=payload  # Send as form data, not JSON
            )

            if response.status_code in (200, 204):
                result = response.json() if response.content else {'success': True}
                if result.get('success', True):
                    record = request.env['nuovopay.lock'].sudo().browse(odoo_record_id)
                    if record.exists():
                        record.unlink()
                else:
                    return {'success': False, 'error': result.get('errors', 'Unknown error')}
            else:
                result = response.json() if response.content else {}
                error_msg = result.get('error') or result.get('message') or f"API returned status {response.status_code}"
                _logger.info(f"NuovoPay unregister failed: {error_msg}")
                return {'success': False, 'error': error_msg}

        except Exception as e:
            _logger.info(f"NuovoPay unregister API error: {e}")
            return {'success': False, 'error': str(e)}