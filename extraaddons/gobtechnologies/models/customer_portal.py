from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from werkzeug.security import generate_password_hash, check_password_hash
import logging
import secrets
import string
from datetime import timedelta

_logger = logging.getLogger(__name__)


class CustomerPortal(models.Model):
    _name = 'customer.portal'
    _description = 'Customer Portal'
    _rec_name = 'phone_no'

    phone_no = fields.Char(string='Phone Number', required=True, index=True)
    otp_code = fields.Char(string='OTP Code')
    otp_expiry = fields.Datetime(string='OTP Expiry')
    otp_verified = fields.Boolean(string='OTP Verified', default=False)
    repayment_id = fields.Many2one('repayment', string='Repayment', ondelete='cascade')
    last_activity = fields.Datetime(string='Last Activity')
    session_token = fields.Char(string='Session Token')
    password = fields.Char(string='Password')

    _sql_constraints = [
        ('unique_phone_no', 'unique(phone_no)', 'This phone number already exists in the portal!')
    ]

    def _generate_otp_code(self):
        return ''.join(secrets.choice(string.digits) for _ in range(6))

    def generate_and_send_otp(self):
        self.ensure_one()

        otp = self._generate_otp_code()
        expiry = fields.Datetime.now() + timedelta(minutes=5)

        self.write({
            'otp_code': otp,
            'otp_expiry': expiry,
            'otp_verified': False,
        })

        # Find the repayment record for this phone number
        repayment = self.env['repayment'].sudo().search([('phone_no', '=', self.phone_no)], limit=1)
        customer_name = repayment.customer_name.name if repayment else self.phone_no

        sms_message = f"Your OTP code is {otp}. Valid for 5 minutes. Do not share this code with anyone."
        try:
            if repayment:
                repayment._send_bulkclix_sms(self.phone_no, sms_message, customer_name)
            else:
                _logger.warning(f"No repayment found for phone {self.phone_no}, cannot send SMS via repayment model")
                return False
            return True
        except Exception as e:
            _logger.error(f"Failed to send OTP SMS: {str(e)}")
            return False

    def verify_otp(self, otp_code):
        self.ensure_one()

        if not self.otp_code or not self.otp_expiry:
            return {'success': False, 'message': 'No OTP has been requested. Please request a new OTP.'}

        if fields.Datetime.now() > self.otp_expiry:
            return {'success': False, 'message': 'OTP has expired. Please request a new OTP.'}

        if self.otp_code != otp_code:
            return {'success': False, 'message': 'Invalid OTP code. Please try again.'}

        self.write({
            'otp_verified': True,
            'otp_code': False,
            'otp_expiry': False,
            'last_activity': fields.Datetime.now(),
        })

        return {'success': True, 'message': 'OTP verified successfully.'}

    @property
    def is_password_set(self):
        return bool(self.password)

    # Verify Password
    def verify_password(self, raw_password):
        self.ensure_one()
        if not self.password:
            return {'success': False, 'message': 'Password not set. Please use OTP login or set a password first.'}
        if not check_password_hash(self.password, raw_password):
            return {'success': False, 'message': 'Invalid password. Please try again.'}
        return {'success': True, 'message': 'Password verified successfully.'}

    # Change Password
    def change_password(self, new_password):
        self.ensure_one()
        if len(new_password) < 8:
            return {'success': False, 'message': 'Password must be at least 8 characters.'}
        self.write({
            'password': generate_password_hash(new_password),
            'session_token': False,
            'otp_verified': False,
        })
        return {'success': True, 'message': 'Password changed successfully.'}

    def find_or_create(self, phone_no):
        portal = self.sudo().search([('phone_no', '=', phone_no)], limit=1)
        if not portal:
            portal = self.sudo().create({
                'phone_no': phone_no,
                'password': generate_password_hash(phone_no),  # Default password = phone number (hashed)
            })
        elif not portal.password:
            portal.write({'password': generate_password_hash(phone_no)})
        return portal

    def link_repayment(self, repayment):
        self.ensure_one()
        if repayment and not self.repayment_id:
            self.write({'repayment_id': repayment.id})
