from odoo import api, fields, models
import logging

_logger = logging.getLogger(__name__)


class HubtelWebhook(models.Model):
    _name = 'hubtel.webhook'
    _description = 'Hubtel Webhook'

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
        try:
            notifications = self.search([('is_read', '=', False)])
            if notifications:
                notifications.write({'is_read': True})
                unread_count = self.search_count([('is_read', '=', False)])
                channel = f"hubtel_notification_{self.env.user.partner_id.id}"
                self.env['bus.bus']._sendone(channel, 'count_notification', {'count': unread_count})
        except Exception as e:
            _logger.error("Error marking notifications as read: %s", str(e))
            return False

    def _extract_phone_and_repayment(self, client_reference):
        phone_no = ''
        repayment_id = False

        if client_reference.startswith('customer_portal_'):
            remainder = client_reference[len('customer_portal_'):]
            if '_' in remainder:
                phone_part, repayment_part = remainder.rsplit('_', 1)
                phone_no = phone_part
                if repayment_part.isdigit():
                    repayment_id = int(repayment_part)
            else:
                phone_no = remainder
        else:
            parts = client_reference.split('_')
            if len(parts) >= 2:
                phone_no = parts[1]

        if phone_no.startswith('233'):
            phone_no = '0' + phone_no[3:]

        return phone_no, repayment_id

    @api.depends('transaction_id', 'client_reference')
    def _compute_phone_no(self):
        for record in self:
            if not record.client_reference:
                record.phone_no = ''
                continue

            phone_no, repayment_id = self._extract_phone_and_repayment(record.client_reference)
            record.phone_no = phone_no
            _logger.info("Extracted Phone No: %s", record.phone_no)

            self._process_customer_name(record)
            self._process_payment(record, repayment_id)

    def _process_customer_name(self, record):
        search_repayment = self.env['repayment'].search([('phone_no', '=', record.phone_no)], limit=1)
        if search_repayment:
            record.customer_name = search_repayment.customer_name.name

    def _process_payment(self, record, repayment_id=False):
        repayment = False
        if repayment_id:
            repayment = self.env['repayment'].browse(repayment_id)
            if not repayment.exists():
                repayment = False

        if not repayment:
            repayment = self.env['repayment'].search([('phone_no', '=', record.phone_no)], limit=1)

        if not repayment:
            _logger.info("Repayment not found for phone %s", record.phone_no)
            return

        payment_date = fields.Date.today()
        if record.payment_date:
            try:
                payment_date = fields.Date.to_date(str(record.payment_date)[:10])
            except Exception:
                payment_date = fields.Date.today()

        receipt_no = record.transaction_id or record.external_transaction_id or record.order_id

        existing = self.env['repayment.payment.line'].search([
            ('repayment_id', '=', repayment.id),
            ('transaction_ref', '=', record.transaction_id),
        ], limit=1) if record.transaction_id else False

        if existing:
            _logger.info("Payment line already exists for transaction %s", record.transaction_id)
            return

        repayment.payment_lines.create({
            'payment_date': payment_date,
            'payment_mode': 'momo',
            'payment_amount': record.amount_charged or record.amount,
            'repayment_id': repayment.id,
            'receipt_no': receipt_no,
            'transaction_ref': record.transaction_id,
        })
