from odoo import fields, models, api
from ..utils.hash_utils import encrypt_text, decrypt_text
import logging

_logger = logging.getLogger(__name__)

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    hubtel_client_id = fields.Char(
        string='Client ID',
        config_parameter='gobtechnologies.hubtel_client_id'
    )
    hubtel_client_secret = fields.Char(
        string='Client Secret',
        config_parameter='gobtechnologies.hubtel_client_secret'
    )
    hubtel_merchant_account = fields.Char(
        string='Merchant Account',
        config_parameter='gobtechnologies.hubtel_merchant_account'
    )

    webhook_url = fields.Char(
        string='Webhook URL',
        config_parameter='gobtechnologies.webhook_url'
    )

    nuovopay_api_key = fields.Char(
        string='NuovoPay API Key',
        config_parameter='gobtechnologies.nuovopay_api_key'
    )
    nuovopay_api_url = fields.Char(
        string='NuovoPay API URL',
        config_parameter='gobtechnologies.nuovopay_api_url'
    )

    # Add Oppo Pay Configuration
    oppo_carrier_code = fields.Char(
        string='Oppo Carrier Code',
        config_parameter='gobtechnologies.oppo_carrier_code'
    )
    oppo_token = fields.Char(
        string='Oppo Token',
        config_parameter='gobtechnologies.oppo_token'
    )
    oppo_signature_server_url = fields.Char(
        string='Oppo Signature Server URL',
        config_parameter='gobtechnologies.oppo_signature_server_url',
        default='http://sarfosco-phones.com/sign'
    )


    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        params = self.env['ir.config_parameter'].sudo()
        
        # Decrypt values when getting them
        res.update({
            'hubtel_client_id': decrypt_text(params.get_param('gobtechnologies.hubtel_client_id', '')),
            'hubtel_client_secret': decrypt_text(params.get_param('gobtechnologies.hubtel_client_secret', '')),
            'hubtel_merchant_account': decrypt_text(params.get_param('gobtechnologies.hubtel_merchant_account', '')),
            'webhook_url': decrypt_text(params.get_param('gobtechnologies.webhook_url', '')),
            'nuovopay_api_key': decrypt_text(params.get_param('gobtechnologies.nuovopay_api_key', '')),
            'nuovopay_api_url': decrypt_text(params.get_param('gobtechnologies.nuovopay_api_url', '')),

            # oppo pay
            'oppo_carrier_code': decrypt_text(params.get_param('gobtechnologies.oppo_carrier_code', '')),
            'oppo_token': decrypt_text(params.get_param('gobtechnologies.oppo_token', '')),
            'oppo_signature_server_url': decrypt_text(params.get_param('gobtechnologies.oppo_signature_server_url', ''))
        })
        return res

    def set_values(self):
        super(ResConfigSettings, self).set_values()
        
        # Encrypt values before saving
        self.env['ir.config_parameter'].sudo().set_param(
            'gobtechnologies.hubtel_client_id', 
            encrypt_text(self.hubtel_client_id or '')
        )
        self.env['ir.config_parameter'].sudo().set_param(
            'gobtechnologies.hubtel_client_secret', 
            encrypt_text(self.hubtel_client_secret or '')
        )
        self.env['ir.config_parameter'].sudo().set_param(
            'gobtechnologies.hubtel_merchant_account', 
            encrypt_text(self.hubtel_merchant_account or '')
        )
        self.env['ir.config_parameter'].sudo().set_param(
            'gobtechnologies.webhook_url', 
            encrypt_text(self.webhook_url or '')
        )
        self.env['ir.config_parameter'].sudo().set_param(
            'gobtechnologies.nuovopay_api_key',
            encrypt_text(self.nuovopay_api_key or '')
        )
        self.env['ir.config_parameter'].sudo().set_param(
            'gobtechnologies.nuovopay_api_url',
            encrypt_text(self.nuovopay_api_url or '')
        )

        # oppo pay
        self.env['ir.config_parameter'].sudo().set_param(
            'gobtechnologies.oppo_carrier_code',
            encrypt_text(self.oppo_carrier_code or '')
        )
        self.env['ir.config_parameter'].sudo().set_param(
            'gobtechnologies.oppo_token',
            encrypt_text(self.oppo_token or '')
        )
        self.env['ir.config_parameter'].sudo().set_param(
            'gobtechnologies.oppo_signature_server_url',
            encrypt_text(self.oppo_signature_server_url or '')
        )

    @api.model
    def get_hubtel_credentials(self):
        """Get decrypted Hubtel credentials"""
        params = self.env['ir.config_parameter'].sudo()
        return {
            'client_id': decrypt_text(params.get_param('gobtechnologies.hubtel_client_id', '')),
            'client_secret': decrypt_text(params.get_param('gobtechnologies.hubtel_client_secret', '')),
            'merchant_account': decrypt_text(params.get_param('gobtechnologies.hubtel_merchant_account', '')),
            'webhook_url': decrypt_text(params.get_param('gobtechnologies.webhook_url', ''))
        }

    @api.model
    def get_nuovopay_credentials(self):
        """Get decrypted NuovoPay credentials"""
        params = self.env['ir.config_parameter'].sudo()
        return {
            'api_key': decrypt_text(params.get_param('gobtechnologies.nuovopay_api_key', '')),
            'api_url': decrypt_text(params.get_param('gobtechnologies.nuovopay_api_url', ''))
        }

    @api.model
    def get_oppo_credentials(self):
        """Get decrypted Oppo credentials"""
        params = self.env['ir.config_parameter'].sudo()
        return {
            'carrier_code': decrypt_text(params.get_param('gobtechnologies.oppo_carrier_code', '')),
            'token': decrypt_text(params.get_param('gobtechnologies.oppo_token', '')),
            'signature_server_url': decrypt_text(params.get_param('gobtechnologies.oppo_signature_server_url', 'http://sarfosco-phones.com/sign'))
        }