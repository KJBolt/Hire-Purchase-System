from odoo import api, fields, models
import logging

_logger = logging.getLogger(__name__)

class HubtelWebhook(models.Model):
    _name = 'hubtel.webhook'
    _description = 'Hubtel Webhook'
    
    # Data Fields
    message = fields.Char(string='Message', readonly=True)
    amount = fields.Float(string='Amount', readonly=True)
    charges = fields.Float(string='Charges', readonly=True)
    amount_after_charges = fields.Float(string='Amount After Charges', readonly=True)
    description = fields.Text(string='Description', readonly=True)
    client_reference = fields.Char(string='Client Reference', readonly=True)
    transaction_id = fields.Char(string='Transaction ID', readonly=True)
    external_transaction_id = fields.Char(string='External Transaction ID', readonly=True)
    amount_charged = fields.Float(string='Amount Charged', readonly=True)
    order_id = fields.Char(string='Order ID', readonly=True)
    payment_date = fields.Char(string='Payment Date', readonly=True)
    phone_no = fields.Char(string='Phone No', readonly=True, compute='_compute_phone_no', store=True)
    customer_name = fields.Char(string='Customer Name', readonly=True, store=True)
    is_read = fields.Boolean(string='Is Read', default=False)



    def mark_as_read(self):
        """Mark all notifications as read"""
        try:
            notifications = self.search([('is_read', '=', False)])
            if notifications:
                notifications.write({'is_read': True})

                # Recalculate unread count
                unread_count = self.search_count([('is_read', '=', False)])
                
                # Send to string channel
                channel = f"hubtel_notification_{self.env.user.partner_id.id}"
                notification_type = 'count_notification'
                message = {'count': unread_count}
                self.env['bus.bus']._sendone(channel, notification_type, message)
        except Exception as e:
            _logger.error(f"Error marking notifications as read: str{e}")
            return False



    @api.depends('transaction_id')
    def _compute_phone_no(self):
        _logger.info("Computing Phone No")
        for record in self:
            if record.client_reference:
                parts = record.client_reference.split("_")  # Split by "_"
                if len(parts) >= 2:  # Ensure the split has enough parts
                    phone_no = parts[1] # Extract phone number

                    # If phone_no starts with '233', replace with '0'
                    if phone_no.startswith('233'):
                        phone_no = '0' + phone_no[3:]

                    record.phone_no = phone_no

                    _logger.info(f"Extracted Phone No: {record.phone_no}")

                    self._process_customer_name(record)
                    self._process_payment(record)
                else:
                    record.phone_no = "" 
            else:
                _logger.info("Client Reference is empty")


    def _process_customer_name(self, record):
            search_repayment = self.env['repayment'].search([('phone_no', '=', record.phone_no)], limit=1)
            if search_repayment:
                record.customer_name = search_repayment.customer_name.name


    def _process_payment(self, record):
        _logger.info("Computing Payment")
        repayment = self.env['repayment'].search([('phone_no', '=', record.phone_no)], limit=1)
        if repayment:
            repayment.payment_lines.create({
                'payment_date': record.payment_date,
                'payment_mode': 'momo',
                'payment_amount': record.amount_charged,
                'repayment_id': repayment.id
            })
        else:
            _logger.info("Phone Number not found")
        
        
    
    
    


