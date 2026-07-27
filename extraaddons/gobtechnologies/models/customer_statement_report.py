from odoo import api, fields, models, _
from datetime import timedelta
from dateutil.relativedelta import relativedelta 
import logging
from odoo.exceptions import ValidationError, UserError
import requests
import json
import base64
import magic
import datetime
import math
from datetime import timedelta


_logger = logging.getLogger(__name__)

OPPO_API_URL = "https://ilockcardf-isp.apps.coloros.com"

PAYMENT_STATE = [
    ('draft', "Draft"),
    ('approved', "Approved"),
    ('progress', "Progress"),
    ('paid', "Paid"),
    ('termination_warning', "Termination Warning"),
    ('terminated', "Terminated"),
]


class StockLot(models.Model):
    _inherit = 'stock.lot'

    delivery_status = fields.Selection([
        ('not_delivered', 'Not Delivered'),
        ('delivered', 'Delivered')
    ], string='Delivery Status', compute='_compute_delivery_status', store=True, readonly=True)

    is_expired = fields.Selection([
        ('expired', 'Expired'),
        ('not_expired', 'Not Expired')
    ], string='Is Expired', compute='_compute_is_expired')

    @api.depends('delivery_ids', 'delivery_ids.state')
    def _compute_delivery_status(self):
        for lot in self:
            if lot.delivery_ids and all(p.state == 'done' for p in lot.delivery_ids):
                lot.delivery_status = 'delivered'
            else:
                lot.delivery_status = 'not_delivered'

    @api.depends('expiration_date')
    def _compute_is_expired(self):
        from datetime import date
        today = date.today()
        for lot in self:
            if lot.expiration_date:
                exp_date = lot.expiration_date.date() if hasattr(lot.expiration_date, 'date') else lot.expiration_date
                lot.is_expired = 'expired' if exp_date < today else 'not_expired'
            else:
                lot.is_expired = 'not_expired'


class RepaymentItemLine(models.Model):
    _name = 'repayment.item.line'
    _description = 'Repayment Item Line'

    repayment_id = fields.Many2one('repayment', string='Repayment', ondelete='cascade', required=False)
    product_id = fields.Many2one('product.product', string='Product', required=True)
    quantity = fields.Float(string='Quantity', default=1, required=True)
    user_warehouse_id = fields.Many2one('stock.warehouse', default=lambda self: self.env.user.property_warehouse_id)
    price = fields.Float(string='Price', required=False)
    lot_id = fields.Many2many('stock.lot', string='Serial Number/IMEI',
        domain="[('product_id', '=', product_id), ('delivery_status', '!=', 'delivered'), ('warehouse_id', '=', user_warehouse_id)]")
       

    @api.onchange('product_id')
    def _onchange_product_id(self):
        """Fetch the price of the selected product and clear serial numbers."""
        if self.product_id:
            self.price = self.product_id.lst_price * self.quantity
            self.lot_id = False
        else:
            self.lot_id = False
            self.price = 0.0
        

    @api.onchange('lot_id')
    def _check_serial_availability(self):
        """Ensure selected serial number is not already delivered or expired."""
        from datetime import date
        for record in self:
            if record.lot_id:
                delivered = record.lot_id.filtered(lambda l: l.delivery_status == 'delivered')
                if delivered:
                    record.lot_id = record.lot_id - delivered
                    return {
                        'warning': {
                            'title': "Delivered Lot",
                            'message': "Serial Number/IMEI '%s' has already been delivered and cannot be selected." % delivered[0].name
                        }
                    }
                today = date.today()
                expired = record.lot_id.filtered(lambda l: l.expiration_date and (l.expiration_date.date() if hasattr(l.expiration_date, 'date') else l.expiration_date) < today)
                if expired:
                    record.lot_id = record.lot_id - expired
                    return {
                        'warning': {
                            'title': "Expired IMEI",
                            'message': "The IMEI has exceeded the sales deadline and cannot be sold. Contact Admin to reinstigate. IMEI Number '%s' expired on %s." % (expired[0].name, expired[0].expiration_date)
                        }
                    }

    @api.onchange('quantity')
    def _onchange_quantity(self):
        """Update the price based on the quantity."""
        if self.product_id:
            self.price = self.product_id.lst_price * self.quantity
            # if self.price > self.repayment_id.selling_price:
            #     raise UserError("Price of the product(s) cannot exceed the selling price")

    # @api.onchange('price')
    # def _onchange_price(self):
    #     _logger.info(f"Price: {self.price}")
    #     _logger.info(f"Repayment price: {self.repayment_id.selling_price}")

    #     if self.repayment_id.selling_price != 0 and self.price != 0:
    #         if self.price > self.repayment_id.selling_price:
    #             raise UserError("Price of the product(s) cannot exceed the selling price")


class RepaymentPaymentLine(models.Model):
    _name = 'repayment.payment.line'
    _description = 'Repayment Payment Line'

    repayment_id = fields.Many2one('repayment', string='Repayment', ondelete='cascade', required=False)
    payment_date = fields.Date(string='Date of Payment', required=False)
    payment_mode = fields.Selection([
        ('cash', 'Cash'),
        ('momo', 'Mobile Money'),
        ('cheque', 'Cheque'),
        ('bank', 'Bank Transfer'),
        ('deposit', 'Deposit'),
    ], string='Mode of Payment', required=False)
    payment_amount = fields.Float(string='Payment Amount', required=False)
    receipt_no = fields.Char(string='Receipt Number')
    transaction_ref = fields.Char(string='Transaction Reference')
    is_payment_insufficient = fields.Boolean(
        string='Payment Insufficient',
        compute='_compute_is_payment_insufficient',
        store=True
    )
    payment_status = fields.Char(
        string='Status',
        compute='_compute_payment_status',
        store=True
    )
    
    # This field is needed for underpayment expected to pay field
    expected_amount = fields.Float(
        string='Expected Amount',
        compute='_compute_expected_amount',
        store=True
    )

    description = fields.Selection([
        ('deposit', 'Deposit'),
        ('repayment', 'Repayment'),
    ], string='Description', compute='_compute_description', store=True)

    # Compute description based on payment mode and first payment line
    @api.depends('repayment_id.payment_lines', 'payment_mode')
    def _compute_description(self):
        for record in self:
            if record.repayment_id.payment_lines and record.repayment_id.payment_lines[0] == record and record.payment_mode == 'deposit':
                record.description = 'deposit'
            else:
                record.description = 'repayment'

    # Compute expected amount based on payment mode and first payment line
    @api.depends('repayment_id.expected_to_pay', 'repayment_id.deposit', 'repayment_id.payment_lines')
    def _compute_expected_amount(self):
        for record in self:
            if record.repayment_id.payment_lines and record.repayment_id.payment_lines[0] == record and record.payment_mode == 'deposit':
                record.expected_amount = record.repayment_id.deposit
            else:
                record.expected_amount = record.repayment_id.expected_to_pay

    # Check if payment is insufficient and change the payment amount color to red
    @api.depends('payment_amount', 'repayment_id.expected_to_pay', 'repayment_id.deposit', 'repayment_id.payment_lines')
    def _compute_is_payment_insufficient(self):
        for record in self:
            # Check if this is the first payment and its mode is deposit
            if record.repayment_id.payment_lines and record.repayment_id.payment_lines[0] == record and record.payment_mode == 'deposit':
                record.is_payment_insufficient = record.payment_amount < record.repayment_id.deposit
            else:
                record.is_payment_insufficient = record.payment_amount < record.repayment_id.expected_to_pay

    # Compute payment status
    @api.depends('payment_amount', 'expected_amount')
    def _compute_payment_status(self):
        for record in self:
            if record.payment_amount > record.expected_amount:
                record.payment_status = 'Overpaid'
                record.is_payment_insufficient = False
            elif record.payment_amount < record.expected_amount:
                record.payment_status = 'Underpaid'
                record.is_payment_insufficient = True
            else:
                record.payment_status = 'Fully Paid'
                record.is_payment_insufficient = False


    @api.model
    def create(self, vals):
        # Set payment_mode to 'deposit' for first payment line
        if vals.get('repayment_id'):
            repayment = self.env['repayment'].browse(vals.get('repayment_id'))
            existing_payments = self.search([('repayment_id', '=', vals.get('repayment_id'))])
            if not existing_payments:
                vals['payment_mode'] = 'deposit'
        
        res = super(RepaymentPaymentLine, self).create(vals)
        # Check and update state after payment
        repayment = res.repayment_id

        # Check if customer has an invoice id
        # if not repayment.invoice_id:
        #     raise UserError("You can only add payment for customers with an invoice generated for them")

        # Only mark as paid if total_paid matches or exceeds selling_price
        if repayment.total_paid >= repayment.selling_price:
            repayment.write({'state': 'paid'})
        else:
            repayment.write({'state': 'progress'})

        # send outstanding balance sms message after payment
        try:
            customer_name = repayment.customer_name.name
            outstanding_balance = repayment.outstanding_loan
            payment_amount = vals.get('payment_amount', 0)
            
            # Check if this is the first payment (deposit)
            existing_payments = self.search([('repayment_id', '=', repayment.id)])
            is_first_payment = len(existing_payments) == 1 and existing_payments[0].id == res.id
            
            # Prepare SMS message
            if is_first_payment:
                sms_message = f"Dear {customer_name}, thank you for your deposit payment of GHS {payment_amount}. Your outstanding balance is GHS {outstanding_balance}."
            else:
                sms_message = f"Dear {customer_name}, thank you for your payment of GHS {payment_amount}. Your outstanding balance is GHS {outstanding_balance}."
            
            # Send SMS if phone number exists
            if repayment.phone_no:
                repayment._send_bulkclix_sms(repayment.phone_no, sms_message, customer_name)
            else:
                _logger.warning(f"Could not send payment SMS: No phone number for {customer_name}")
                repayment.message_post(
                    body=f"Could not send payment SMS: No phone number for {customer_name}",
                    message_type='comment',
                    subtype_xmlid='mail.mt_note'
                )
                
        except Exception as e:
            _logger.error(f"Error sending payment SMS: {str(e)}")
        
        # Trigger Oppo push notification if deposit is not 0
        if not self.env.context.get('skip_oppo_edit'):
            if repayment.deposit and repayment.deposit > 0:
                try:
                    repayment.action_oppo_trigger_push()
                except Exception as e:
                    _logger.warning(f"Failed to send Oppo trigger push on payment: {str(e)}")
        

        # Trigger Oppo prepaid edit API call when payment is received
        if not self.env.context.get('skip_oppo_edit'):
            try:
                _logger.info("Triggering Oppo prepaid edit API call after payment")
                oppo_lock = self.env['oppo.lock'].search([('repayment_id', '=', repayment.id)], limit=1)
                if oppo_lock:
                    payment_amount = vals.get('payment_amount', 0)
                    repayment_frequency = repayment.repayment_frequency
                    oppo_lock.action_edit_prepaid(payment_amount, repayment_frequency)
                    _logger.info(f"Prepaid edit API called for repayment {repayment.unique_id} with payment amount {payment_amount}")
                else:
                    _logger.info(f"No Oppo lock record found for repayment {repayment.unique_id}, skipping prepaid edit")
            except Exception as e:
                _logger.error(f"Failed to call prepaid edit API on payment: {str(e)}")
                repayment.message_post(
                    body=f'Warning: Prepaid edit API call failed after payment. Device lock may not be updated: {str(e)}',
                    message_type='comment',
                    subtype_xmlid='mail.mt_note'
                )
        
        # Update lock_deadline on the repayment record
        try:
            payment_amount = vals.get('payment_amount', 0)
            if payment_amount > 0 and repayment.expected_to_pay:
                existing_count = len(self.search([('repayment_id', '=', repayment.id)]))
                frequency = repayment.repayment_frequency
                if existing_count <= 1:
                    frequency_days = int(frequency)
                else:
                    base_days = payment_amount / repayment.expected_to_pay
                    frequency_days = int(frequency)
                    frequency_days = int(base_days * frequency_days)
                if frequency_days > 0:
                    deadline = datetime.datetime.now() + datetime.timedelta(days=frequency_days)
                    repayment.sudo().write({'lock_deadline': deadline})
        except Exception as e:
            _logger.error(f"Failed to update lock_deadline: {str(e)}")

        res.testpayment(vals)
        return res
        

    def write(self, vals):
        # Set payment_mode to 'deposit' for first payment line if not already set
        # if 'payment_mode' not in vals and self.repayment_id:
        #     existing_payments = self.search([('repayment_id', '=', self.repayment_id.id)])
        #     if len(existing_payments) == 1 and existing_payments[0].id == self.id:
        #         vals['payment_mode'] = 'deposit'
        
        res = super(RepaymentPaymentLine, self).write(vals)
        # Check and update state after payment
        repayment = self.repayment_id
        _logger.info(f"Oustanding loan when updating: {repayment.outstanding_loan}")
        
        # Only mark as paid if total_paid matches or exceeds selling_price
        if repayment.total_paid >= repayment.selling_price:
            repayment.write({'state': 'paid'})
        else:
            repayment.write({'state': 'progress'})

        return res


    def testpayment(self, vals):
        # Get current payment date and amount
        current_payment_date = fields.Date.from_string(vals.get('payment_date'))
        current_payment_amount = vals.get('payment_amount')

        if current_payment_date and current_payment_amount:
            previous_payment_date = current_payment_date - timedelta(days=1)
        
            _logger.info(f"Previous payment date: {previous_payment_date}")
            _logger.info(f"Current payment amount: {current_payment_amount}")
            _logger.info(f"Current payment date: {current_payment_date}")

            # Get all payments for the previous date
            previous_date_payments = self.repayment_id.payment_lines.filtered(
                lambda p: p.payment_date == previous_payment_date
            )
            
            previous_payment_total = sum(previous_date_payments.mapped('payment_amount'))

            # Check if previous payment was insufficient
            if previous_date_payments and previous_payment_total < self.repayment_id.expected_to_pay:
                shortage = self.repayment_id.expected_to_pay - previous_payment_total
                
                # If current payment can cover the shortage
                if current_payment_amount >= shortage:
                    # Amount to be used from current payment
                    amount_to_previous = shortage
                    # Remaining amount for current payment
                    remaining_current = current_payment_amount - shortage
                    
                    if previous_date_payments:
                        # Update existing previous payment
                        previous_date_payments[0].write({
                            'payment_amount': previous_payment_total + amount_to_previous
                        })
                        
                        # Send SMS to customer
                        phone_no = self.repayment_id.phone_no
                        customer_name = self.repayment_id.customer_name.name
                        sms_message = f"Dear {customer_name}, a portion of GHS{current_payment_amount}, has been used to cover the previous payment shortage of GHS{previous_payment_total}. Your outstanding balance is GHS{remaining_current}. "

                        self.repayment_id._send_bulkclix_sms(phone_no, sms_message, customer_name)

                    else:
                        # Create new payment record for previous date
                        self.env['repayment.payment.line'].with_context(skip_oppo_edit=True).create({
                            'payment_date': previous_payment_date,
                            'payment_amount': amount_to_previous,
                            'repayment_id': self.repayment_id.id,
                            'payment_mode': 'momo'  
                        })

                    # Update the current payment with remaining amount
                    self.write({
                        'payment_amount': remaining_current
                    })

                    _logger.info(f"Previous payment was insufficient. Added {amount_to_previous} from current payment")
                    _logger.info(f"Previous payment updated to: {previous_payment_total + amount_to_previous}")
                    _logger.info(f"Current payment updated to: {remaining_current}")
                else:
                    _logger.info("Current payment insufficient to cover previous payment shortage")






class Repayment(models.Model):
    _name = 'repayment'
    _description = 'Repayment'
    _inherit = ['mail.thread']
    _rec_name = 'customer_name'

    unique_id = fields.Char(
        string="Reference",
        required=True, copy=False, readonly=True, index=True,
        default=lambda self: _('New')
    )
    
    # client_reference = fields.Char(string='Client Reference')
    customer_name = fields.Many2one('res.partner', string='Customer Name', required=True)
    gps_location = fields.Char(string='GPS Location', required=True)
    payment_lines = fields.One2many(
        'repayment.payment.line',  # Related model
        'repayment_id',  # Field in the related model pointing back to this model
        string='Payments',
    )

    product_lines = fields.One2many(
        'repayment.item.line',  # Related model
        'repayment_id',  # Field in the related model pointing back to this model
        string='Products',
        required=True
    )

    sales_commission = fields.Float(
        string="Sales Commission", 
        compute='_compute_sales_commission', 
        store=True
    )
    


    plan_id = fields.Many2one('payment.plan', string='Payment Plan', ondelete='set null')
    plan_duration = fields.Selection([
        ('30', '1 Month - 30 Days'),
        ('60', '2 Months - 60 Days'),
        ('90', '3 Months - 90 Days'),
        ('120', '4 Months - 120 Days'),
        ('150', '5 Months - 150 Days'),
        ('180', '6 Months - 180 Days'),
        ('210', '7 Months - 210 Days'),
    ], string='Plan Duration')
    start_date = fields.Date(string='Start Date', required=True)
    selling_price = fields.Float(string='Selling Price', required=True)
    deposit = fields.Float(string='Deposit', required=True)
    repayment = fields.Float(string='Repayment Amount', compute='_compute_repayment', readonly=True, store=True)
    expected_to_pay = fields.Float(string='Expected to Pay', compute='_compute_expected_to_pay', store=True)
    repayment_frequency = fields.Selection([
        ('1', 'Daily'),
        ('7', 'Weekly'),
        ('30', 'Monthly'),
        # ('0', 'Cash')
    ], string='Repayment Frequency', default='1', required=True)
    repayment_date = fields.Date(
        string='Repayment Date',
        compute='_compute_repayment_date',
        store=True
    )
    # last_repayment_date = fields.Date(string='Last Repayment Date', store=False)
    end_date = fields.Date(string='End Date', required=True)
    duration_left = fields.Integer(string='Duration Left', compute='_compute_duration_left', store=True)
    due_date = fields.Date(string='Due Date', compute='_compute_due_date', store=True)
    reminder = fields.Char(string='Reminder', compute='_compute_reminder', store=True)
    total_paid = fields.Float(string='Total Paid', compute='_compute_total_paid', store=True)
    outstanding_loan = fields.Float(string='Outstanding Debt', compute='_compute_outstanding_loan', store=True)
    outstanding_loan_status = fields.Text(string="Outstanding Debt", compute='_compute_outstanding_loan_status', store=True)
    phone_no = fields.Char(string='Phone Number', required=True)
    penalty = fields.Integer(string='Penalty')
    discount = fields.Integer(string='Discount')
    percentage_paid = fields.Float(string='Percentage Paid', compute='_compute_percentage_paid', store=True)
    paid_to_momo = fields.Float(string='Paid to Momo')
    guarantor_name = fields.Many2one('res.partner', string='Guarantor Name', required=True)
    guarantor_contact = fields.Char(string='Guarantor Contact', required=True)
    head_of_gob_contact = fields.Char(string='Head of Sarfosco Contact', help="This phone number is used to send messages to Sarfosco management", required=True)
    state = fields.Selection(
        selection=PAYMENT_STATE,
        string="Status",
        default='draft')
    total_price = fields.Float(
        string='Total Price', 
        compute='_compute_total_price', 
        store=True
    )
    currency_id = fields.Many2one(
        'res.currency', 
        string='Currency', 
        default=lambda self: self.env.company.currency_id.id
    )
    is_payment_missed = fields.Boolean(
        string='Payment Missed',
        compute='_compute_payment_missed',
        store=True
    )
    overdue_status = fields.Boolean(string="Overdue Status", compute='_compute_overdue_status', store=True)
    overdue_amount = fields.Float(string='Overdue Amount', compute='_compute_overdue_amount', store=True)
    payment_status = fields.Selection([
        ('on_track', 'On Track'),
        ('overdue', 'Overdue'),
        ('insufficient', 'Insufficient Payment')
    ], string='Payment Status', compute='_compute_payment_status', store=True)
    lock_deadline = fields.Datetime(string='Lock Deadline', readonly=True,
        help='When the device will be locked if no further payment is received')
    penalty_ids = fields.One2many('repayment.penalty', 'repayment_id', string='Penalties')
    total_penalties = fields.Float(string='Total Penalties', compute='_compute_total_penalties', store=True)

    # Relevant documents fields
    customer_ghana_card_front = fields.Binary(string='Customer Ghana Card Front', attachment=True, help="Upload Front Image", required=True)
    customer_ghana_card_back = fields.Binary(string='Customer Ghana Card Back', attachment=True, help="Upload Back Image", required=True)
    customer_image = fields.Binary(string='Customer Image', attachment=True, help="Upload Customer Image", required=True)
    guarantor_ghana_card_front = fields.Binary(string='Guarantor Ghana Card Front', attachment=True, help="Upload Front Image", required=False)
    guarantor_ghana_card_back = fields.Binary(string='Guarantor Ghana Card Back', attachment=True, help="Upload Back Image", required=False)
    mobile_money_statement = fields.Binary(string='Mobile Money Statement', attachment=True, help="Upload Statement", required=False)
    mobile_money_statement_filename = fields.Char(string='Statement Filename', compute='_compute_mobile_money_statement_filename', store=True)
    utility_bill = fields.Binary(string='Utility Bill', attachment=True, help="Upload Utility Bill", required=False)
    utility_bill_filename = fields.Char(string='Utility Bill Filename', compute='_compute_utility_bill_filename', store=True)

    # Invoice field
    branch = fields.Selection([
        ('sarfosco', 'Sarfosco'),
    ], string='Branch', required=False)

    #Invoice id used for the sales order computations
    invoice_id = fields.Char(string='Invoice ID', required=False)
    invoice_no = fields.Char(string='Invoice No', readonly=True, required=False, default=lambda self: self.env['ir.sequence'].next_by_code('invoice.ref'))
    invoice_payment_method = fields.Selection([
        # ('pay_at_once', 'Pay At Once'),
        # ('pay_in_installments', 'Pay In Installments'),
        ('auto_debit', 'Pay In Installments with Auto Debit')
    ], string='Payment Method', required=False)
    note = fields.Text(string='Note', required=False)
    payment_url = fields.Char(string="Payment Url", required=False)
    created_by = fields.Many2one('res.partner', string='Created By', required=True, default=lambda self: self.env.user.partner_id)

    def name_get(self):
        result = []
        for rec in self:
            name = rec.unique_id or ''
            result.append((rec.id, name))
        return result

    # Compute mobile money statement filename    @api.depends('mobile_money_statement')
    def _compute_mobile_money_statement_filename(self):
        for record in self:
            attachment = self.env['ir.attachment'].search([
                ('res_model', '=', 'repayment'),
                ('res_id', '=', record.id),
                ('res_field', '=', 'mobile_money_statement')
            ], limit=1)
            record.mobile_money_statement_filename = attachment.name if attachment else False

    @api.onchange('plan_duration', 'product_lines')
    def _onchange_plan_duration(self):
        """When plan duration is selected, search payment.plan by duration and populate fields."""
        if not self.plan_duration:
            self.plan_id = False
            self.selling_price = 0.0
            self.deposit = 0.0
            self.end_date = False
            return

        if not self.product_lines:
            self.plan_id = False
            self.selling_price = 0.0
            self.deposit = 0.0
            self.end_date = False
            return

        product_id = self.product_lines[:1].product_id
        plan = self.env['payment.plan'].search([
            ('plan_duration', '=', self.plan_duration),
            ('product_id', '=', product_id.id),
            ('active', '=', True),
        ], limit=1)

        if plan:
            self.plan_id = plan
            self.selling_price = plan.selling_price
            self.deposit = plan.deposit
        else:
            self.plan_id = False
            self.selling_price = 0.0
            self.deposit = 0.0

        # Compute end_date from start_date + duration
        if self.start_date and self.plan_duration:
            from datetime import timedelta
            self.end_date = self.start_date + timedelta(days=int(self.plan_duration))

    @api.onchange('start_date', 'plan_duration')
    def _onchange_start_date(self):
        """When start_date or plan_duration changes, recompute end_date if both are set."""
        if self.start_date and self.plan_duration:
            from datetime import timedelta
            self.end_date = self.start_date + timedelta(days=int(self.plan_duration))

    @api.onchange('plan_id')
    def _onchange_plan_id(self):
        """When a payment plan is selected, populate selling_price, deposit, and plan_duration."""
        if self.plan_id:
            self.selling_price = self.plan_id.selling_price
            self.deposit = self.plan_id.deposit
            self.plan_duration = self.plan_id.plan_duration

    @api.onchange('repayment_frequency')
    def _onchange_repayment_frequency(self):
        """When repayment frequency changes, update expected_to_pay from the plan."""
        if self.plan_duration and self.repayment_frequency and self.product_lines:
            product_id = self.product_lines[:1].product_id
            plan = self.env['payment.plan'].search([
                ('plan_duration', '=', self.plan_duration),
                ('product_id', '=', product_id.id),
                ('active', '=', True),
            ], limit=1)
            if plan:
                freq = self.repayment_frequency
                if freq == '1':
                    self.expected_to_pay = plan.daily_amount
                elif freq == '7':
                    self.expected_to_pay = plan.weekly_amount
                elif freq == '30':
                    self.expected_to_pay = plan.monthly_amount
                else:
                    self.expected_to_pay = 0.0

    @api.depends('plan_id', 'plan_duration', 'repayment_frequency')
    def _compute_expected_to_pay(self):
        for record in self:
            if record.plan_duration and record.repayment_frequency and record.product_lines:
                product_id = record.product_lines[:1].product_id
                plan = self.env['payment.plan'].search([
                    ('plan_duration', '=', record.plan_duration),
                    ('product_id', '=', product_id.id),
                    ('active', '=', True),
                ], limit=1)
                if plan:
                    freq = record.repayment_frequency
                    if freq == '1':
                        record.expected_to_pay = plan.daily_amount
                    elif freq == '7':
                        record.expected_to_pay = plan.weekly_amount
                    elif freq == '30':
                        record.expected_to_pay = plan.monthly_amount
                    else:
                        record.expected_to_pay = 0.0
                else:
                    record.expected_to_pay = 0.0
            else:
                record.expected_to_pay = 0.0

    @api.depends('product_lines.product_id')
    def _compute_sales_commission(self):
        for record in self:
            total_commission = 0.0
            if record.product_lines:
                for product_line in record.product_lines:
                    if product_line.product_id and product_line.product_id.product_tmpl_id:
                        commission = product_line.product_id.product_tmpl_id.sales_commission_value or 0.0
                        total_commission += commission
            record.sales_commission = total_commission

    # Compute utility bill filename
    @api.depends('utility_bill')
    def _compute_utility_bill_filename(self):
        for record in self:
            attachment = self.env['ir.attachment'].search([
                ('res_model', '=', 'repayment'),
                ('res_id', '=', record.id),
                ('res_field', '=', 'utility_bill')
            ], limit=1)
            record.utility_bill_filename = attachment.name if attachment else False

    # Check the extensions of documents uploaded
    @api.constrains('customer_ghana_card_front', 'customer_ghana_card_back', 'guarantor_ghana_card_front', 'guarantor_ghana_card_back', 'mobile_money_statement', 'utility_bill')
    def _check_file_types(self):
        for record in self:
            if record.customer_ghana_card_front:
                # Get file content type
                file_content = base64.b64decode(record.customer_ghana_card_front)
                file_type = magic.from_buffer(file_content, mime=True)

                # Define allowed file types
                allowed_types = [
                    'image/jpeg',
                    'image/jpg',
                    'image/png',
                ]

                if file_type not in allowed_types:
                    raise ValidationError("Ghana Card Front Image must be jpg, jpeg, or png format.")

                # Check file size (e.g., 10MB limit)
                if len(file_content) > 10 * 1024 * 1024:  # 10MB in bytes
                    raise ValidationError(
                        "File size must be less than 10MB!"
                    )

            if record.customer_ghana_card_back:
                # Get file content type
                file_content = base64.b64decode(record.customer_ghana_card_back)
                file_type = magic.from_buffer(file_content, mime=True)
                allowed_types = [
                    'image/jpeg',
                    'image/jpg',
                    'image/png',
                ]

                if file_type not in allowed_types:
                    raise ValidationError("Ghana Card Back Image must be jpg, jpeg, or png format.")
                    
                if len(file_content) > 10 * 1024 * 1024:  # 10MB in bytes
                    raise ValidationError(
                        "File size must be less than 10MB!"
                    )

            if record.guarantor_ghana_card_front:
                # Get file content type
                file_content = base64.b64decode(record.guarantor_ghana_card_front)
                file_type = magic.from_buffer(file_content, mime=True)
                allowed_types = [
                    'image/jpeg',
                    'image/jpg',
                    'image/png',
                ]    

                if file_type not in allowed_types:
                    raise ValidationError("Guarantor Ghana Card Front Image must be jpg, jpeg, or png format.")
                    
                if len(file_content) > 10 * 1024 * 1024:  # 10MB in bytes
                    raise ValidationError(
                        "File size must be less than 10MB!"
                    )

            if record.guarantor_ghana_card_back:
                # Get file content type
                file_content = base64.b64decode(record.guarantor_ghana_card_back)
                file_type = magic.from_buffer(file_content, mime=True)
                allowed_types = [
                    'image/jpeg',
                    'image/jpg',
                    'image/png',
                ]
                if file_type not in allowed_types:
                    raise ValidationError("Guarantor Ghana Card Back Image must be jpg, jpeg, or png format.")
                    
                if len(file_content) > 10 * 1024 * 1024:  # 10MB in bytes
                    raise ValidationError(
                        "File size must be less than 10MB!"
                    )

            if record.mobile_money_statement:
                # Get file content type
                file_content = base64.b64decode(record.mobile_money_statement)
                file_type = magic.from_buffer(file_content, mime=True)
                allowed_types = [
                    'application/pdf',
                    'image/jpeg',
                    'image/jpg',
                    'image/png',
                ]

                if file_type not in allowed_types:
                    raise ValidationError("Mobile Money Statement must be pdf, jpg, jpeg, or png format.")

                if len(file_content) > 10 * 1024 * 1024:  # 10MB in bytes
                    raise ValidationError(
                        "File size must be less than 10MB!"
                    )

            if record.utility_bill:
                # Get file content type
                file_content = base64.b64decode(record.utility_bill)
                file_type = magic.from_buffer(file_content, mime=True)
                allowed_types = [
                    'application/pdf',
                    'image/jpeg',
                    'image/jpg',
                    'image/png',
                ]

                if file_type not in allowed_types:
                    raise ValidationError("Utility bill must be pdf, jpg, jpeg, or png format.")

                if len(file_content) > 10 * 1024 * 1024:  # 10MB in bytes
                    raise ValidationError(
                        "File size must be less than 10MB!"
                    )



    @api.depends('penalty_ids.penalty_amount')
    def _compute_total_penalties(self):
        for record in self:
            record.total_penalties = sum(record.penalty_ids.mapped('penalty_amount'))

    # Outstanding loan status 
    @api.depends('outstanding_loan')
    def _compute_outstanding_loan_status(self):
        for record in self:
            if record.outstanding_loan < 0:
                record.outstanding_loan_status = f'{record.outstanding_loan} (Overpaid)'
            elif record.outstanding_loan == 0:
                record.outstanding_loan_status = f'{record.outstanding_loan} (Paid)'
            else:
                record.outstanding_loan_status = record.outstanding_loan


    @api.onchange('product_lines')
    def _check_product_lines(self):
        if len(self.product_lines) > 1:
            self.product_lines = self.product_lines[:1]
            return {
                'warning': {
                    'title': "Only One Product Allowed",
                    'message': "Only one product record is allowed."
                }
            }
    
    @api.onchange('product_lines')
    def _check_expired_serial_numbers(self):
        """Check that selected serial numbers (IMEIs) are not expired."""
        from datetime import date
        
        for record in self:
            if record.product_lines:
                for product_line in record.product_lines:
                    if product_line.lot_id:
                        for lot in product_line.lot_id:
                            if lot.expiration_date:
                                # Convert datetime to date for comparison
                                exp_date = lot.expiration_date.date() if hasattr(lot.expiration_date, 'date') else lot.expiration_date
                                # Check if expiration date is in the past
                                if exp_date < date.today():
                                    return {
                                        'warning': {
                                            'title': "Expired IMEI",
                                            'message': f"The IMEI has exceeded the sales deadline and cannot be sold. Contact Admin to reinstigate. Imei Number '{lot.name}' expired on {lot.expiration_date}."
                                        }
                                    }

    # Ensure the selling price, deposit and expected to pay is not zero
    @api.constrains('selling_price', 'deposit', 'start_date', 'end_date', 'repayment_frequency')
    def _check_not_zero_values(self):
        for record in self:
            if record.selling_price == 0:
                raise ValidationError('Please enter the selling price')

            # if record.deposit == 0:
            # raise ValidationError('Please enter the deposit')

            if not record.start_date or not record.end_date:
                raise ValidationError('Please enter the start date and end date')

            if record.start_date > record.end_date:
                raise ValidationError('End date must be after start date')

            if record.repayment_frequency == '0':
                raise ValidationError('Repayment frequency cannot be Cash when computing expected to pay')

    

    # Compute the repayment amount
    @api.depends('payment_lines.payment_amount', 'expected_to_pay', 'state')
    def _compute_repayment(self):
        for rec in self:
            if rec.state == 'paid':
                rec.repayment = 0.0
            elif rec.payment_lines:
                rec.repayment = sum(rec.payment_lines.mapped('payment_amount'))


    # Fetch Invoicing api
    # def fetch_invoicing_api(self, vals):
    #     # Get customer name from the ID
    #     customer_id = vals.get('customer_name')
    #     customer_name = ""
    #     if customer_id:
    #         customer = self.env['res.partner'].browse(customer_id)
    #         if not customer:
    #             raise UserError('Customer not found on the system')
    #         customer_name = customer.name
    #     else:
    #         raise UserError('Customer ID not provided')

    #     # Scrutinize the repayment frequency
    #     repayment_frequency_scrutinized = ''
    #     if vals.get('repayment_frequency') == '1':
    #         repayment_frequency_scrutinized = 'Daily'
    #     elif vals.get('repayment_frequency') == '7':
    #         repayment_frequency_scrutinized = 'Weekly'
    #     elif vals.get('repayment_frequency') == '30':
    #         repayment_frequency_scrutinized = 'Monthly'
    #     else:
    #         raise UserError('Invalid repayment frequency')

    #     # Get other input values
    #     phone_no = vals.get('phone_no')
    #     invoice_no = vals.get('invoice_no')

    #     # Get Hubtel credentials
    #     settings = self.env['res.config.settings'].get_hubtel_credentials()
    #     callback_url = settings.get('webhook_url')

    #     issue_by = vals.get('branch')
    #     created_by = vals.get("branch")
    #     start_date = vals.get("start_date")
    #     end_date = vals.get("end_date")
    #     selling_price = vals.get("selling_price")
    #     has_tax = ''
    #     days = int(vals.get('repayment_frequency', '0'))
    #     first_payment_amount = vals.get('deposit')
    #     frequency = repayment_frequency_scrutinized

    #     # Selling price validation
    #     if selling_price <= 0:
    #         raise UserError("Selling price cannot be 0")

    #     # Get price from repayment.item.line
    #     # item_lines = self.env['repayment.item.line'].search([('repayment_id', '=', self.id)])
    #     # for item_line in item_lines:
    #     #     if item_line.price > selling_price:
    #     #         raise UserError("Price of the product(s) cannot exceed the selling price")
            
        
    #     # Format dates in ISO 8601 format (YYYY-MM-DDTHH:MM:SS.sssZ)
    #     def format_date_to_iso8601(date_value):
    #         """Convert date to ISO 8601 format expected by the API"""
    #         if not date_value:
    #             return None
            
    #         # Convert to date object if it's a string
    #         if isinstance(date_value, str):
    #             try:
    #                 date_obj = fields.Date.from_string(date_value)
    #             except ValueError:
    #                 raise UserError(f'Invalid date format: {date_value}')
    #         else:
    #             date_obj = date_value
            
    #         # Convert date to datetime at midnight
    #         dt = datetime.datetime.combine(date_obj, datetime.time.min)
    #         # Format in ISO 8601 format
    #         return dt.isoformat() + "Z"

        
    #     # Process start date
    #     start_date_obj = None
    #     if start_date:
    #         if isinstance(start_date, str):
    #             start_date_obj = fields.Date.from_string(start_date)
    #         else:
    #             start_date_obj = start_date
        
        
    #     # Format start date for API
    #     start_date_formatted = format_date_to_iso8601(start_date_obj)

    #     # end date formatted
    #     end_date_obj = None
    #     if end_date:
    #         if isinstance(end_date, str):
    #             end_date_obj = fields.Date.from_string(end_date)
    #         else:
    #             end_date_obj = end_date

    #     # Format end date for API
    #     end_date_formatted = format_date_to_iso8601(end_date_obj)
        
    #     # Calculate and format first payment due date
    #     first_payment_due_date = None
    #     if start_date_obj and vals.get('repayment_frequency'):
    #         freq = int(vals.get('repayment_frequency'))
            
    #         if freq == 1:  # Daily
    #             first_payment_due_date = start_date_obj
    #         elif freq == 7:  # Weekly
    #             first_payment_due_date = start_date_obj + timedelta(weeks=1)
    #         elif freq == 30:  # Monthly
    #             first_payment_due_date = start_date_obj + relativedelta(months=1)
    #         else:
    #             first_payment_due_date = start_date_obj
    #     first_payment_due_date_formatted = format_date_to_iso8601(first_payment_due_date)

    #     _logger.info(f"End Date Formatted: {end_date_formatted}, First Payment Due Date Formatted: {first_payment_due_date_formatted}")

    #     item_lines = self.env['repayment.item.line'].search([('repayment_id', '=', self.id)])        
    #     items = []
    #     for item_line in item_lines:
    #         items.append({
    #             "description": item_line.product_id.name,
    #             "quantity": int(item_line.quantity),
    #             "unitPrice": item_line.price
    #         })

    #         # If total items price greater than selling price throw error
    #         total_price = sum(item.price for item in self.product_lines)
    #         if total_price > selling_price:
    #             raise UserError("The total price of items should match the selling price specified ")

        

    #     if len(items) == 0:
    #         raise UserError("Product is empty")
        
    #     # convert str to boolean
    #     str_value = 'false'
    #     is_before = bool(str_value.lower() == 'true')

    #     # Create payload
    #     payload = {
    #         "invoiceNumber": invoice_no,
    #         "customerName": customer_name,
    #         "customerPhoneNumber": phone_no,
    #         "IssuedBy": issue_by,
    #         "createdBy": created_by,
    #         "dueDate": end_date_formatted,
    #         "callbackUrl": callback_url,
    #         "firstPaymentDueDate": first_payment_due_date_formatted,
    #         "firstPaymentAmount": first_payment_amount,
    #         "frequency": frequency,
    #         "reminders": [
    #             {
    #                 "days": days,
    #                 "isBefore": is_before
    #             }
    #         ],
    #         "items": items
    #     }
        
    #     # Send request
    #     headers = {
    #         "Host": "invoicing.hubtel.com",
    #         "Accept": "application/json",
    #         "Content-Type": "application/json",
    #         "Authorization": "Basic TmtNdnpvODo3MmMzZWYxZWFhNzQ0OGMxYjVhMjE4YzE1YWRmYWMxZg==",
    #         "Cache-Control": "no-cache",
    #     }
    #     url = f"https://invoicing.hubtel.com/api/invoice/2030161/auto-debit"
        
    #     try:
    #         response = requests.post(url, headers=headers, json=payload)
    #         _logger.info(f"Response: {response.text}")
    #         if response.status_code == 200:
    #             response_data = response.json()
    #             _logger.info(f"Response Data: {response_data}")
                
    #             # Update the record with the invoice ID
    #             self.write({
    #                 'invoice_id': response_data['data']['invoiceId'],
    #                 'payment_url': response_data['data']['paymentUrl']
    #             })

    #             # Log message to chatter
    #             self.message_post(
    #                 body=f'Invoice generated successfully',
    #                 message_type='comment',
    #                 subtype_xmlid='mail.mt_note'
    #             )

    #             # Send notification to user
    #             # channel = f"hubtel_notification_{self.env.user.partner_id.id}"
    #             # notification_type = 'invoice'
    #             # message = {'msg': f'Invoice generated successfully'}
    #             # self.env['bus.bus']._sendone(channel, notification_type, message)
    #         else:
    #             _logger.info(f"Failed to create invoice: {response.text}")
    #             raise UserError(f"Oops something went wrong while creating the invoice. Please try again later.")
    #     except Exception as e:
    #         _logger.error(f"Exception during API call: {str(e)}")
    #         raise UserError(f"Oops something went wrong while creating the invoice. Please check the network and try again.")



    # Prepare the values for fetch invoicing api method                                                 
    def _prepare_invoice_vals(self):
        """Prepare a dictionary of values from the record for invoicing API."""
        return {
            'customer_name': self.customer_name.id,
            'repayment_frequency': self.repayment_frequency,
            'phone_no': self.phone_no,
            'invoice_no': self.invoice_no,
            'branch': self.branch,
            'start_date': self.start_date,
            'end_date': self.end_date,
            'selling_price': self.selling_price,
            'deposit': self.deposit,
        }



    # Create invoice for customer
    # def action_create_invoice(self):
    #     # Check if the invoice already exists
    #     if self.invoice_id:
    #         raise UserError("Invoice already created for this customer.")

    #     # Validate required fields
    #     if not self.invoice_no or not self.branch or not self.invoice_payment_method or not self.product_lines:
    #         raise UserError("Please fill in the Invoice Details before generating an invoice.")

    #     # Call the API to create the invoice
    #     try:
    #         self.fetch_invoicing_api(self._prepare_invoice_vals())

    #         # Set state to progress
    #         self.state = 'progress'
            
    #     except Exception as e:
    #         raise UserError(f"Error creating invoice: {str(e)}")

    #     return True





    # Set state to progress and generate a unique id for repayment when record is created
    @api.model
    def create(self, vals):
        if vals.get('unique_id', _('New')) == _('New'):
            vals['unique_id'] = self.env['ir.sequence'].next_by_code('repayment.sequence') or _('New')

        phone_no = vals.get('phone_no')
        if phone_no:
            existing = self.env['repayment'].search([('phone_no', '=', phone_no)], limit=1)
            if existing:
                raise ValidationError(_('Phone number %s already linked to a record in the database.') % phone_no)
        
        # vals['state'] = 'progress'
        res = super(Repayment, self.with_context(skip_oppo_edit=True)).create(vals)

        # res.fetch_invoicing_api(vals)
        
        # Check if this is an import operation
        is_import = self.env.context.get('import_file', False)

        # Check if Product lines price is greater than selling price BEFORE any side effects
        # total_price = sum(item.price for item in res.product_lines)
        # if total_price > res.selling_price:
        #     raise UserError("The total price of items should match the selling price specified ")
        
        # Only send SMS if this is not an import operation
        if not is_import:
            try:
                # Get customer name from res.partner
                customer = self.env['res.partner'].browse(vals.get('customer_name'))
                customer_name = customer.name if customer else "Customer"

                _logger.info(f"Customer Name, {customer_name}")
                _logger.info(f"Customer, {customer}")
                _logger.info(f"Phone No, {res.phone_no}")

                # Prepare SMS message
                sms_message = f"Dear {customer_name}, your account has been successfully created with Sarfosco Phones. Visit {self.get_base_url()}/customer/portal to make payment."

                # Send SMS
                if res.phone_no and res.state == 'draft':
                    res._send_bulkclix_sms(res.phone_no, sms_message, customer_name)
            
            except Exception as e:
                raise UserError(f"Error sending onboarding SMS: {str(e)}")
        else:
            _logger.info("Successfully imported record")

        # Create oppo lock record
        try:
            # Extract IMEIs from product lines
            imeis = []
            for line in res.product_lines:
                if line.lot_id:
                    for lot in line.lot_id:
                        if lot.name:
                            imeis.append(lot.name)
            
            oppo_lock_vals = {
                'repayment_id': res.id,
                'customer_name': res.customer_name.name if res.customer_name else '',
                'device_name': res.product_lines[0].product_id.name if res.product_lines and res.product_lines[0].product_id else 'Oppo Device',
                'imei_list': json.dumps(imeis) if imeis else json.dumps([]),
                'device_uid': imeis[0] if imeis else '',
            }
            oppo_lock = self.env['oppo.lock'].create(oppo_lock_vals)
            _logger.info(f"Oppo lock record created for repayment {res.unique_id}")

        except Exception as e:
            _logger.warning(f"Failed to create oppo lock record: {str(e)}")

        return res


    # Edit oppo lock helper function
    def _edit_oppo_lock(self):
        """Helper method to sync oppo.lock record with repayment data"""
        try:
            oppo_lock = self.env['oppo.lock'].search([('repayment_id', '=', self.id)], limit=1)
            if oppo_lock:
                # Extract IMEIs from product lines
                imeis = []
                for line in self.product_lines:
                    if line.lot_id:
                        for lot in line.lot_id:
                            if lot.name:
                                imeis.append(lot.name)
                
                # Prepare update values
                lock_vals = {
                    'imei_list': json.dumps(imeis) if imeis else json.dumps([]),
                    'device_uid': imeis[0] if imeis else '',
                    'device_name': self.product_lines[0].product_id.name if self.product_lines and self.product_lines[0].product_id else 'Oppo Device',
                    'customer_name': self.customer_name.name if self.customer_name else '',
                }
                oppo_lock.write(lock_vals)
                _logger.info(f"Oppo lock record synced for repayment {self.unique_id}")
        except Exception as e:
            _logger.warning(f"Failed to sync oppo lock record: {str(e)}")




    # update state when record is updated
    def write(self, vals):
        res = super(Repayment, self).write(vals)
        if 'state' not in vals:  # Only check payment status if state is not being explicitly changed
            if self.total_paid >= self.selling_price:
                vals['state'] = 'paid'
            else:
                vals['state'] = 'progress'
        
        # Check if Product lines price is greater than selling price
        # total_price = sum(item.price for item in self.product_lines)
        # if total_price > self.selling_price:
        #     raise UserError("The total price of items should match the selling price specified ")
        # elif total_price < self.selling_price:
        #     raise UserError("The total price of items should match the selling price specified ")

        # Call the edit oppo lock helper function
        self._edit_oppo_lock()

        return res


    # Generate the x_sign
    def _generate_oppo_x_sign(self, request_body):
        _logger.info("Oppo x-sign running")

        """Generate x-sign signature using the signing server"""
        self.ensure_one()
        
        oppo_credentials = self.env['res.config.settings'].get_oppo_credentials()
        carrier_code = oppo_credentials.get('carrier_code')
        token = oppo_credentials.get('token')
        signature_server_url = oppo_credentials.get('signature_server_url')
        
        if not carrier_code or not token:
            raise UserError(_('Oppo carrier code or token is not configured. Please configure it in the settings.'))
        
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

    # Check 24-hour grace period for Oppo device lock
    def _check_grace_period_lock(self):
        """Cron job method to check for repayments that need to be locked after 24-hour grace period"""
        
        # Calculate the cutoff time (24 hours ago)
        cutoff_time = fields.Datetime.now() - timedelta(hours=24)
        
        # Search for repayments with deposit but no payment after 24 hours
        repayments_to_lock = self.search([
            ('deposit', '>', 0),
            ('create_date', '<=', cutoff_time),
        ])
        
        for repayment in repayments_to_lock:
            # Check if there are any payment lines
            if not repayment.payment_lines:
                _logger.info(f"Checking grace period lock for repayment {repayment.unique_id}")
                # No payments at all - lock the device
                try:
                    oppo_lock = self.env['oppo.lock'].search([('repayment_id', '=', repayment.id)], limit=1)
                    if oppo_lock:
                        # Call prepaid edit with 0 days to lock immediately
                        oppo_lock.action_edit_prepaid(0, repayment.repayment_frequency)
                        _logger.info(f"Grace period lock triggered for repayment {repayment.unique_id} (no payments)")
                        repayment.message_post(
                            body=f'24-hour grace period expired. Device locked via prepaid edit (no payments received).',
                            message_type='comment',
                            subtype_xmlid='mail.mt_note'
                        )
                except Exception as e:
                    _logger.error(f"Failed to lock device for repayment {repayment.unique_id} after grace period: {str(e)}")
            else:
                # Check if the latest payment is more than 24 hours old
                _logger.info(f"Checking grace period for payment more tha 24hrs {repayment.unique_id} (has payments)")
                latest_payment = repayment.payment_lines.sorted(key=lambda x: x.payment_date, reverse=True)[:1]
                if latest_payment:
                    latest_payment_date = latest_payment.payment_date
                    if latest_payment_date:
                        # Convert payment_date (Date) to Datetime for comparison
                        latest_payment_datetime = fields.Datetime.to_datetime(latest_payment_date)
                        if latest_payment_datetime < cutoff_time:
                            try:
                                oppo_lock = self.env['oppo.lock'].search([('repayment_id', '=', repayment.id)], limit=1)
                                if oppo_lock:
                                    # Call prepaid edit with 0 days to lock immediately
                                    oppo_lock.action_edit_prepaid(0, repayment.repayment_frequency)
                                    _logger.info(f"Grace period lock triggered for repayment {repayment.unique_id} (payment expired)")
                                    repayment.message_post(
                                        body=f'24-hour grace period expired since last payment. Device locked via prepaid edit.',
                                        message_type='comment',
                                        subtype_xmlid='mail.mt_note'
                                    )
                            except Exception as e:
                                _logger.error(f"Failed to lock device for repayment {repayment.unique_id} after grace period: {str(e)}")

    # Trigger the push message
    def action_oppo_trigger_push(self):
        _logger.info("Trigger push message running")

        """Send payment balance message via Oppo trigger push API"""
        for record in self:
            # Check if there's an associated oppo.lock record
            oppo_lock = self.env['oppo.lock'].search([('repayment_id', '=', record.id)], limit=1)
            
            if not oppo_lock:
                _logger.info(f"No Oppo lock record found for repayment {record.unique_id}")
                return
            
            oppo_credentials = self.env['res.config.settings'].get_oppo_credentials()
            carrier_code = oppo_credentials.get('carrier_code')
            
            if not carrier_code:
                raise UserError(_('Oppo carrier code is not configured. Please configure it in the settings.'))
            
            # Parse IMEI list
            try:
                imei_list = json.loads(oppo_lock.imei_list) if isinstance(oppo_lock.imei_list, str) else [oppo_lock.device_uid]
            except json.JSONDecodeError:
                imei_list = [oppo_lock.device_uid]
            
            # Build request body
            request_body = {
                "deviceUid": oppo_lock.device_uid,
                "imeiList": imei_list
            }
            
            # Generate x-sign
            x_sign = record._generate_oppo_x_sign(request_body)

            _logger.info(f"Generated x-sign: {x_sign} for repayment {record.unique_id}")
            
            # Call Oppo API
            headers = {
                'Content-Type': 'application/json',
                'x-carrier-code': carrier_code,
                'x-sign': x_sign,
            }
            
            try:
                response = requests.post(
                    f"{OPPO_API_URL}/triggerPush",
                    headers=headers,
                    json=request_body,
                    timeout=30
                )
                response.raise_for_status()
                
                response_data = response.json()
                _logger.info(f"Oppo trigger push API response: {response_data}")
                
                if response_data.get('code') == 0:
                    record.message_post(
                        body=f'Payment balance message sent via Oppo API: Deposit: GHS {record.deposit}, Total Balance: GHS {record.selling_price}, New Balance: GHS {record.outstanding_loan}',
                        message_type='comment',
                        subtype_xmlid='mail.mt_note'
                    )
                    _logger.info(f"Trigger push successful for repayment {record.unique_id}")
                else:
                    raise UserError(_('Oppo API error: %s') % response_data.get('message', 'Unknown error'))
                    
            except requests.exceptions.RequestException as e:
                _logger.error(f"Error calling Oppo trigger push API: {e}")
                raise UserError(_('Failed to send trigger push via Oppo API: %s') % str(e))


    # Show overdue badge if todays date is greater than end date
    @api.depends('repayment_date', 'end_date', 'total_paid', 'selling_price')
    def _compute_overdue_status(self):
        for record in self:
            today = fields.Date.today()
            tomorrow = today + timedelta(days=1)
            
            # First check if record is fully paid
            if record.total_paid >= record.selling_price:
                record.overdue_status = False
                continue
                
            # Set to False if end_date is not set
            if not record.end_date:
                record.overdue_status = False
                continue
                
            # Only check overdue status if we have an end_date and not fully paid
            record.overdue_status = tomorrow > record.end_date
            _logger.info(f"Overdue Status: {record.overdue_status}")



    # Computes the duration left
    @api.depends('repayment_date', 'end_date')
    def _compute_duration_left(self):
        for record in self:
            if record.repayment_date and record.end_date:
                duration = record.end_date - record.repayment_date
                record.duration_left = duration.days
            else:
                record.duration_left = 0

    # Computes the due date
    @api.depends('repayment_date', 'repayment_frequency')
    def _compute_due_date(self):
        for record in self:
            if record.repayment_date and record.repayment_frequency:
                # Convert repayment_frequency to an integer if needed
                freq = int(record.repayment_frequency)

                if freq == 1:
                    due_date = record.repayment_date + timedelta(days=1)
                elif freq == 14:
                    due_date = record.repayment_date + timedelta(weeks=2)
                elif freq == 30:
                    due_date = record.repayment_date + relativedelta(months=1)
                elif freq == 0:
                    due_date = record.repayment_date
                else:
                    due_date = False  # Fallback in case of an invalid value

                record.due_date = due_date
            else:
                record.due_date = False 

    # Computes the reminder
    @api.depends('due_date')
    def _compute_reminder(self):
        today = fields.Date.today()
        for record in self:
            if not record.due_date:
                record.reminder = 'Not Due'
                continue
                
            if today >= record.due_date:
                record.reminder = 'Due'
            else:
                record.reminder = 'Not Due'



    # Computes the total paid
    @api.depends('payment_lines.payment_amount')
    def _compute_total_paid(self):
        for record in self:
            if record.payment_lines:
                record.total_paid = sum(record.payment_lines.mapped('payment_amount'))
            else:
                record.total_paid = 0.0

    # Computes the outstnding loan
    @api.depends('selling_price', 'total_paid', 'deposit', 'expected_to_pay')
    def _compute_outstanding_loan(self):
        for record in self:
            if record.selling_price and record.total_paid:
                record.outstanding_loan = record.selling_price - record.total_paid
            else:
                record.total_paid = 0.0
                record.outstanding_loan = record.selling_price


    # computes the percentage paid
    @api.depends('selling_price', 'total_paid')
    def _compute_percentage_paid(self):
        for record in self:
            if record.selling_price and record.total_paid:
                record.percentage_paid = (record.total_paid / record.selling_price) * 100
            else:
                record.percentage_paid = 0


    # Send toast message to Customer
    def action_button_method(self):
        # Your method logic here
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Success',
                'message': f'Sms sent to {self.customer_name.name}',
                'sticky': False,
                'type': 'success',  # Can also use 'warning', 'danger', etc.
                'position': 'bottom-right'
            }
        }

    # Approve button
    def action_initiate_delivery(self):
        # Check if sales order already exists
        if self.invoice_id:
            sale_order = self.env['sale.order'].browse(int(self.invoice_id))
            if sale_order.exists():
                return {
                    'type': 'ir.actions.act_window',
                    'name': 'Sales Order',
                    'res_model': 'sale.order',
                    'res_id': sale_order.id,
                    'view_mode': 'form',
                    'target': 'current',
                }
        
        self.state = 'progress'
        
        # Create sales order
        sale_order = self.env['sale.order'].create({
            'partner_id': self.customer_name.id,
            'origin': self.unique_id,
            'note': f"Hire Purchase Order for {self.customer_name.name}",
            'client_order_ref': self.unique_id,
        })
        
        # Add product lines
        for line in self.product_lines:
            self.env['sale.order.line'].create({
                'order_id': sale_order.id,
                'product_id': line.product_id.id,
                'name': line.product_id.name,
                'product_uom_qty': line.quantity,
                'price_unit': line.price / line.quantity if line.quantity else line.price,
            })
        
        # Confirm the sales order
        sale_order.action_confirm()
        
        # Link the sales order to the repayment
        self.write({
            'invoice_id': str(sale_order.id),
        })
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'Sales Order',
            'res_model': 'sale.order',
            'res_id': sale_order.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_sales_order(self):
        if self.invoice_id:
            return {
                'type': 'ir.actions.act_window',
                'name': 'Sales Order',
                'res_model': 'sale.order',
                'res_id': int(self.invoice_id),
                'view_mode': 'form',
                'target': 'current',
            }
        return False

    # Confirm button
    def action_confirm_payment(self):
        self.state = 'paid'
        return True

    # Cancel Button
    def action_cancel(self):
        self.state = 'draft'
        return True


    # Computes the next repayment date
    @api.depends('start_date', 'repayment_frequency', 'payment_lines.payment_date', 'expected_to_pay')
    def _compute_repayment_date(self):
        for record in self:
            # Default to False
            record.repayment_date = False
            
            # Basic validation
            if not record.start_date or not record.repayment_frequency:
                continue

            try:
                freq = int(record.repayment_frequency)
            except (ValueError, TypeError):
                continue

            # If no payment lines, calculate from start date
            if not record.payment_lines:
                if freq == 1:
                    record.repayment_date = record.start_date
                elif freq == 7:
                    record.repayment_date = record.start_date + timedelta(weeks=1)
                elif freq == 30:
                    record.repayment_date = record.start_date + relativedelta(months=1)
                else:
                    record.repayment_date = record.start_date
                continue

            # Get payments sorted by date
            payment_lines_sorted = record.payment_lines.filtered(lambda p: p.payment_date).sorted(lambda p: p.payment_date, reverse=True)
            if not payment_lines_sorted:
                record.repayment_date = record.start_date
                continue

            current_payment = payment_lines_sorted[0]
            current_payment_date = current_payment.payment_date
            current_payment_amount = current_payment.payment_amount

            # Calculate next repayment date based on payment amount
            if record.expected_to_pay > 0 and current_payment_amount >= record.expected_to_pay:
                full_payments = int(current_payment_amount // record.expected_to_pay)
                if freq == 1:
                    record.repayment_date = current_payment_date + timedelta(days=full_payments)
                elif freq == 7:
                    record.repayment_date = current_payment_date + timedelta(weeks=full_payments)
                elif freq == 30:
                    record.repayment_date = current_payment_date + relativedelta(months=full_payments)
            else:
                # If payment is insufficient or expected_to_pay is 0, keep current repayment date
                record.repayment_date = current_payment_date


    # Computes payment missed
    @api.depends('repayment_date', 'payment_lines.payment_date', 'payment_lines.payment_amount', 'expected_to_pay')
    def _compute_payment_missed(self):
        today = fields.Date.today()
        for record in self:
            if not record.repayment_date:
                record.is_payment_missed = False
                continue

            # Find payments made on the expected repayment date
            payments_on_date = record.payment_lines.filtered(
                lambda p: p.payment_date == record.repayment_date
            )
            
            # Calculate total payment amount for that date
            total_payment = sum(payments_on_date.mapped('payment_amount'))

            _logger.info(f"Payments found: {payments_on_date}")
            _logger.info(f"Repayment Date, Total payment: {record.repayment_date}, {total_payment}")

            if record.state == 'paid':
                record.is_payment_missed = False
                continue
            
            if payments_on_date:
                if total_payment < record.expected_to_pay:
                    record.is_payment_missed = True
                else:
                    record.is_payment_missed = False

                if record.state == 'paid':
                    record.is_payment_missed = False
            else:
                record.is_payment_missed = record.repayment_date < today



    # Check if payment is missed runs every minute
    def check_payment_missed(self):
        today = fields.Date.today()
        for record in self:
            if not record.repayment_date:
                record.is_payment_missed = False
                continue

            if record.repayment_date < today:
                record.is_payment_missed = True
                continue



    # Send SMS to customer
    def _send_hubtel_sms(self, phone, sms_message, customer_name):
        """Helper method to send SMS via Hubtel API using GET request"""
        try:
            # Get Hubtel credentials from settings
            settings = self.env['res.config.settings'].get_hubtel_credentials()
            client_id = settings.get('client_id')
            client_secret = settings.get('client_secret')
            merchant_account = settings.get('merchant_account')
            
            if not all([client_id, client_secret, merchant_account]):
                raise UserError("Missing Hubtel credentials")
                return False

            # Validate phone number format
            if not phone or len(phone) < 10:
                _logger.error(f"Invalid phone number: {phone}")
                return False

            # Construct URL directly
            url = f"https://sms.hubtel.com/v1/messages/send?clientsecret={client_secret}&clientid={client_id}&from={merchant_account}&to={phone}&content={sms_message}"
            
            # Log the URL (with sensitive data masked)
            _logger.info(f"Making request to: {url}")
            
            # Make GET request
            response = requests.get(url, timeout=30)
            
            _logger.info(f"SMS API Response Status: {response.status_code}")
            _logger.info(f"SMS API Response: {response.text}")
            
            if response.status_code in [200, 201]:
                _logger.info(f"SMS sent successfully to {phone}")
                # Send notification to user
                # channel = f"hubtel_notification_{self.env.user.partner_id.id}"
                # notification_type = 'notify_user'
                # message = {'msg': f'Account creation sms sent to {customer_name}'}
                # self.env['bus.bus']._sendone(channel, notification_type, message)
                return True
            else:
                _logger.info(f"Failed to send SMS. Status: {response.status_code}, Response: {response.text}")

                # Send toast message to user
                channel = f"hubtel_notification_{self.env.user.partner_id.id}"
                notification_type = 'sms_error'
                message = {'msg': f'Something went wrong sending sms!'}
                self.env['bus.bus']._sendone(channel, notification_type, message)

                return False
            
        except Exception as e:
            raise UserError(f"Failed to send SMS: {str(e)}")

            # Send toast message to user
            # channel = f"hubtel_notification_{self.env.user.partner_id.id}"
            # notification_type = 'sms_error'
            # message = {'msg': f'Something went wrong sending sms!'}
            # self.env['bus.bus']._sendone(channel, notification_type, message)

            return False


    # BulkClix SMS API
    def _send_bulkclix_sms(self, phone, sms_message, customer_name):
        """Helper method to send SMS via BulkClix API using POST request"""
        try:
            settings = self.env['res.config.settings'].get_bulkclix_credentials()
            api_key = settings.get('api_key')
            sender_id = settings.get('sender_id')

            if not all([api_key, sender_id]):
                raise UserError("Missing BulkClix credentials")

            if not phone or len(phone) < 10:
                _logger.error(f"Invalid phone number: {phone}")
                return False

            url = 'https://api.bulkclix.com/api/v1/sms-api/send'
            headers = {
                'x-api-key': api_key,
                'Content-Type': 'application/json',
                'Accept': 'application/json',
            }
            payload = {
                'sender_id': sender_id,
                'message': sms_message,
                'recipients': [phone],
            }
            response = requests.post(url, json=payload, headers=headers, timeout=15)

            if response.status_code in [200, 201]:
                self.message_post(
                    body=f"SMS sent successfully to {phone}",
                    message_type='comment',
                    subtype_xmlid='mail.mt_note'
                )
                return True

            self.message_post(
                body=f"Failed to send SMS. Status: {response.status_code}, Response: {response.text}",
                message_type='comment',
                subtype_xmlid='mail.mt_note'
            )
            channel = f"hubtel_notification_{self.env.user.partner_id.id}"
            self.env['bus.bus']._sendone(channel, 'sms_error', {'msg': 'Something went wrong sending sms!'})
            return False

        except Exception as e:
            raise UserError(f"Failed to send SMS: {str(e)}")



    # Send repayment reminders
    @api.model
    def _send_repayment_reminders(self):
        today = fields.Date.today()
        tomorrow = today + timedelta(days=1)
        yesterday = today - timedelta(days=1)
        two_days_ago = today - timedelta(days=2)
        three_days_ago = today - timedelta(days=3)
        seven_days_ago = today - timedelta(days=7)
        ten_days_ago = today - timedelta(days=10)
        fourteen_days_ago = today - timedelta(days=14) 
        
        # Find all active repayments
        repayments = self.search([
            ('state', 'in', ['progress', 'termination_warning']),  # Include termination_warning state
            ('outstanding_loan', '>', 0)
        ])
        
        for repayment in repayments:
            try:
                # Skip if no repayment date
                if not repayment.repayment_date:
                    continue
                
                # Check for upcoming payments and overdue payments
                should_remind = False
                is_overdue = False
                should_send_penalty_reminder = False
                should_charge_penalty = False
                should_send_termination_warning = False
                should_send_termination_warning_two = False
                should_send_final_termination = False
                
                if repayment.repayment_frequency == '1':  # Daily
                    should_remind = tomorrow == repayment.repayment_date
                    is_overdue = yesterday == repayment.repayment_date
                    should_send_penalty_reminder = two_days_ago == repayment.repayment_date
                    should_charge_penalty = three_days_ago == repayment.repayment_date
                    should_send_termination_warning = seven_days_ago >= repayment.repayment_date
                    should_send_termination_warning_two = ten_days_ago >= repayment.repayment_date
                    should_send_final_termination = fourteen_days_ago >= repayment.repayment_date
                elif repayment.repayment_frequency == '7':
                    if repayment.repayment_date:
                        continue
                    # Weekly
                    days_since_payment = (today - repayment.repayment_date).days
                    should_remind = (repayment.repayment_date - tomorrow).days == 0
                    is_overdue = days_since_payment == 1
                    should_send_penalty_reminder = days_since_payment == 2
                    should_charge_penalty = days_since_payment == 3
                    should_send_termination_warning = days_since_payment >= 7
                    should_send_termination_warning_two = days_since_payment >= 10
                    should_send_final_termination = days_since_payment >= 14
                elif repayment.repayment_frequency == '30':
                    if repayment.repayment_date:
                        continue  # Monthly
                    days_since_payment = (today - repayment.repayment_date).days
                    should_remind = (repayment.repayment_date - tomorrow).days == 0
                    is_overdue = days_since_payment == 1
                    should_send_penalty_reminder = days_since_payment == 2
                    should_charge_penalty = days_since_payment == 3
                    should_send_termination_warning = days_since_payment >= 7
                    should_send_termination_warning_two = days_since_payment >= 10
                    should_send_final_termination = days_since_payment >= 14
                elif repayment.repayment_frequency == '0':  # Cash
                    continue

                # Handle termination warning period (7-14 days)
                # if should_send_termination_warning and repayment.outstanding_loan > 0:
                #     # Check if any payments were made in the last 7 days
                #     recent_payments = repayment.payment_lines.filtered(
                #         lambda p: p.payment_date >= seven_days_ago
                #     )
                #     total_recent_payment = sum(recent_payments.mapped('payment_amount'))
                    
                #     if not recent_payments or total_recent_payment < repayment.expected_to_pay:
                #         termination_warning_message = (
                #             f"Dear {repayment.customer_name.name}, "
                #             f"your contract with Sarfosco Phones terminates, "
                #             f"in 14 days if payment is not made today. "
                #             f"We shall retrieve our item & refund 50% of your deposit into your momo account. "
                #             f"Kindly dial *713*7678# to make immediate payment. "
                #             f"Thank you for choosing Sarfosco Phones."
                #         )
                        
                #         if repayment.phone_no:
                #             self._send_bulkclix_sms(repayment.phone_no, termination_warning_message, repayment.customer_name.name)
                        
                #         _logger.info(
                #             f"Sent termination warning to {repayment.customer_name.name} "
                #             f"for payment due on {seven_days_ago}"
                #         )
                        
                #         # Update the state to indicate termination warning
                #         if repayment.state != 'termination_warning':
                #             repayment.write({
                #                 'state': 'termination_warning'
                #             })



                # Handle termination warning period (10-14 days)
                # if should_send_termination_warning_two and repayment.outstanding_loan > 0:
                #     # Check if any payments were made in the last 10 days
                #     recent_payments = repayment.payment_lines.filtered(
                #         lambda p: p.payment_date >= ten_days_ago
                #     )
                #     total_recent_payment = sum(recent_payments.mapped('payment_amount'))

                #     if not recent_payments or total_recent_payment < repayment.expected_to_pay:
                #         termination_warning_message_two = (
                #             f"Dear {repayment.customer_name.name}, "
                #             f"your contract with Sarfosco Phones terminates, "
                #             f"in 3 days if payment is not made today. "
                #             f"We shall retrieve our item & refund 50% of your deposit into your momo account. "
                #             f"Kindly dial *713*7678# to make immediate payment. Thank you for choosing Sarfosco Phones. "
                #         )
                #         if repayment.phone_no:
                #             self._send_bulkclix_sms(repayment.phone_no, termination_warning_message_two, repayment.customer_name.name)

                #         # Update the state to indicate termination warning
                #         if repayment.state != 'termination_warning':
                #             repayment.write({
                #                 'state': 'termination_warning'
                #             })



                # Handle final termination (after 14 days)
                # if should_send_final_termination and repayment.outstanding_loan > 0:
                #     # Check if any payments were made in the last 14 days
                #     recent_payments = repayment.payment_lines.filtered(
                #         lambda p: p.payment_date >= fourteen_days_ago
                #     )
                #     total_recent_payment = sum(recent_payments.mapped('payment_amount'))
                    
                #     if not recent_payments or total_recent_payment < repayment.expected_to_pay:
                #         # Message for customer
                #         customer_message = (
                #             f"Dear {repayment.customer_name.name}, "
                #             f"Due to non-payment for the past 14 days, "
                #             f"your contract with Sarfosco Phones has been terminated. "
                #             f"Please contact our office immediately to resolve this issue."
                #         )

                #         # Message for guarantor
                #         guarantor_message = (
                #             f"Dear {repayment.guarantor_name.name}, "
                #             f"This is to inform you that {repayment.customer_name.name}, "
                #             f"for whom you stood as guarantor, has defaulted on their payment, "
                #             f"for the past 14 days. "
                #             f"As a guarantor, you may be contacted regarding this matter."
                #         )

                #         # Message for Head of Sarfosco Phones
                #         head_message = (
                #             f"TERMINATION NOTICE\n"
                #             f"Customer: {repayment.customer_name.name}\n"
                #             f"Phone: {repayment.phone_no}\n"
                #             f"Outstanding Balance: GHS {repayment.outstanding_loan}\n"
                #             f"Default Duration: 14+ days\n"
                #             f"Guarantor: {repayment.guarantor_name.name}\n"
                #             f"Guarantor Phone: {repayment.guarantor_phone}\n"
                #             f"Contract has been automatically terminated due to payment default."
                #         )
                        
                #         if repayment.phone_no:
                #             self._send_bulkclix_sms(repayment.phone_no, final_termination_message, repayment.customer_name.name)

                #         if repayment.guarantor_contact:
                #             self._send_bulkclix_sms(repayment.guarantor_contact, guarantor_message, repayment.guarantor_name.name)

                #         if repayment.head_of_gob_contact:
                #             self._send_bulkclix_sms(repayment.head_of_gob_contact, head_message, "Head of Sarfosco Phones")
                        
                #         _logger.info(
                #             f"Sent final termination notice to {repayment.customer_name.name} "
                #             f"for payment due on {fourteen_days_ago}"
                #         )
                        
                #         # Update the state to terminated
                #         repayment.write({
                #             'state': 'terminated'
                #         })



                # Send reminder for upcoming payment
                if should_remind and repayment.outstanding_loan > 0:
                    reminder_message = (
                        f"Dear {repayment.customer_name.name}, "
                        f"this is a reminder that your payment of GHS {repayment.expected_to_pay} "
                        f"is due tomorrow {tomorrow.strftime('%d-%m-%Y')}. "
                        f"Kindly pay on time. "
                        f"Thank you for choosing Sarfosco Phones."
                    )
                    
                    if repayment.phone_no:
                        self._send_bulkclix_sms(repayment.phone_no, reminder_message, repayment.customer_name.name)
                        
                    _logger.info(
                        f"Sent reminder to {repayment.customer_name.name} "
                        f"for {repayment.repayment_frequency} payment due on {tomorrow}"
                    )
                

                # Check if payment was made yesterday or today
                if is_overdue and repayment.outstanding_loan > 0:
                    # Find payments made on the due date (yesterday) or today
                    payments = repayment.payment_lines.filtered(
                        lambda p: p.payment_date in [yesterday, today]
                    )
                    
                    # Calculate total payment amount
                    total_payment = sum(payments.mapped('payment_amount'))
                    
                    # Only send overdue notice if no payment or insufficient payment
                    if not payments or total_payment < repayment.expected_to_pay:
                        payment_status = "not made" if not payments else "insufficient"
                        overdue_message = (
                            f"Dear {repayment.customer_name.name}, "
                            f"your payment of GHS {repayment.expected_to_pay} was due yesterday. "
                            f"Kindly make payment to avoid any penalties. "
                            f"Thank you for choosing Sarfosco Phones."
                        )
                        
                        if repayment.phone_no:
                            self._send_bulkclix_sms(repayment.phone_no, overdue_message, repayment.customer_name.name)
                            
                        _logger.info(
                            f"Sent overdue notice to {repayment.customer_name.name} "
                            f"for {repayment.repayment_frequency} payment due on {yesterday}. "
                            f"Payment status: {payment_status}"
                        )
                    else:
                        _logger.info(
                            f"No overdue notice sent to {repayment.customer_name.name} "
                            f"as payment was received (Total: {total_payment})"
                        )


                # Check for penalty reminder (2 days after due date)
                # if should_send_penalty_reminder and repayment.outstanding_loan > 0:
                #     # Check if payment was made in the last 2 days
                #     recent_payments = repayment.payment_lines.filtered(
                #         lambda p: p.payment_date >= two_days_ago
                #     )
                #     total_recent_payment = sum(recent_payments.mapped('payment_amount'))
                    
                #     if not recent_payments or total_recent_payment < repayment.expected_to_pay:
                #         penalty_reminder_message = (
                #             f"Dear {repayment.customer_name.name}, "
                #             f"your payment of GHS {repayment.expected_to_pay} is still pending. "
                #             f"Please note that a penalty fee of GHS 10 will be charged tomorrow "
                #             f"if payment is not made today. "
                #             f"Kindly dial *713*7678# to pay now. "
                #             f"Thank you for choosing Sarfosco Phones."
                #         )
                        
                #         if repayment.phone_no:
                #             self._send_bulkclix_sms(repayment.phone_no, penalty_reminder_message, repayment.customer_name.name)
                        
                #         _logger.info(
                #             f"Sent penalty warning to {repayment.customer_name.name} "
                #             f"for payment due on {two_days_ago}"
                #         )


                # Check for penalty charge (3 days after due date)
                # if should_charge_penalty and repayment.outstanding_loan > 0:
                #     # Check if payment was made in the last 3 days
                #     recent_payments = repayment.payment_lines.filtered(
                #         lambda p: p.payment_date >= three_days_ago
                #     )
                #     total_recent_payment = sum(recent_payments.mapped('payment_amount'))
                    
                #     if not recent_payments or total_recent_payment < repayment.expected_to_pay:
                #         # Add penalty charge
                #         penalty_amount = 10.0  # GHS 10
                        
                #         # Create penalty charge record
                #         self.env['repayment.penalty'].create({
                #             'repayment_id': repayment.id,
                #             'penalty_date': today,
                #             'penalty_amount': penalty_amount,
                #             'reason': 'Late payment penalty'
                #         })
                        
                        
                #         # Update outstanding loan amount to include penalty
                #         repayment.write({
                #             'outstanding_loan': repayment.outstanding_loan + penalty_amount,
                #             'penalty': penalty_amount
                #         })
                        
                #         penalty_charge_message = (
                #             f"Dear {repayment.customer_name.name}, "
                #             f"a penalty fee of GHS {penalty_amount} has been charged to your account "
                #             f"due to delayed payment. Your new outstanding balance is "
                #             f"GHS {repayment.outstanding_loan}. "
                #             f"Kindly dial *713*7678# to pay now. "
                #             f"Thank you for choosing Sarfosco Phones."
                #         )
                        
                #         if repayment.phone_no:
                #             self._send_bulkclix_sms(repayment.phone_no, penalty_charge_message, repayment.customer_name.name)
                        
                #         _logger.info(
                #             f"Applied penalty charge to {repayment.customer_name.name} "
                #             f"for payment due on {three_days_ago}"
                #         )

            except Exception as e:
                _logger.error(f"Failed to process reminders for {repayment.customer_name.name}: {str(e)}")
                raise ValidationError(f"Failed to process reminders for {repayment.customer_name.name}: {str(e)}")


    # Compute payment status
    @api.depends('repayment_date', 'payment_lines.payment_date', 'payment_lines.payment_amount', 'expected_to_pay')
    def _compute_payment_status(self):
        today = fields.Date.today()
        for record in self:
            if not record.repayment_date:
                record.payment_status = 'on_track'
                continue

            # Get payments in current period
            current_period_start = record.start_date
            current_period_end = record.repayment_date
            
            current_period_payments = record.payment_lines.filtered(
                lambda p: p.payment_date and current_period_start <= p.payment_date <= current_period_end
            )
            total_paid_in_period = sum(current_period_payments.mapped('payment_amount'))

            if today > record.repayment_date:
                if total_paid_in_period < record.expected_to_pay:
                    record.payment_status = 'overdue'
                else:
                    record.payment_status = 'on_track'
            else:
                if total_paid_in_period < record.expected_to_pay:
                    record.payment_status = 'insufficient'
                else:
                    record.payment_status = 'on_track'



    # Compute overdue amount
    @api.depends('expected_to_pay', 'payment_lines.payment_amount', 'repayment_date')
    def _compute_overdue_amount(self):
        today = fields.Date.today()
        for record in self:
            if not record.repayment_date or today <= record.repayment_date:
                record.overdue_amount = 0.0
                continue

            # Get all payments up to current date
            past_payments = record.payment_lines.filtered(
                lambda p: p.payment_date <= record.repayment_date
            )
            total_paid = sum(past_payments.mapped('payment_amount'))
            
            # Calculate overdue amount
            if total_paid < record.expected_to_pay:
                record.overdue_amount = record.expected_to_pay - total_paid
            else:
                record.overdue_amount = 0.0

    @api.model
    def get_payment_distribution(self):
        """
        Calculate payment distribution percentages for all repayments
        Returns: dict with paid, pending, and overdue percentages
        """
        today = fields.Date.today()
        
        # Get all repayment records
        all_repayments = self.search([])
        total_count = len(all_repayments)
        
        if total_count == 0:
            return {'paid': 0.0, 'pending': 0.0, 'overdue': 0.0}
        
        paid_count = 0
        pending_count = 0
        overdue_count = 0
        
        for repayment in all_repayments:
            # Paid: state is 'paid' or total_paid >= selling_price
            if repayment.state == 'paid' or repayment.total_paid >= repayment.selling_price:
                paid_count += 1
            # Overdue: overdue_status is True and not fully paid
            elif repayment.overdue_status and repayment.total_paid < repayment.selling_price:
                overdue_count += 1
            # Pending: everything else (progress, draft, etc.)
            else:
                pending_count += 1
        
        # Calculate percentages
        paid_percentage = (paid_count / total_count) * 100 if total_count > 0 else 0
        pending_percentage = (pending_count / total_count) * 100 if total_count > 0 else 0
        overdue_percentage = (overdue_count / total_count) * 100 if total_count > 0 else 0
        
        return {
            'paid': round(paid_percentage, 1),
            'pending': round(pending_percentage, 1),
            'overdue': round(overdue_percentage, 1)
        }

    @api.model
    def get_active_customer_installments(self, limit=10):
        """
        Fetch active customer installments for dashboard table
        Returns: list of dicts with customer installment data
        """
        # Get active repayments (not paid, not terminated)
        active_repayments = self.search([
            ('state', 'in', ['draft', 'progress', 'termination_warning'])
        ], order='create_date desc', limit=limit)
        
        installments = []
        for repayment in active_repayments:
            # Get product information (first product if multiple)
            product_name = "No Product"
            if repayment.product_lines:
                product_name = repayment.product_lines[0].product_id.name
            
            # Calculate installments progress
            total_installments = 0
            paid_installments = 0
            
            # Estimate installments based on payment frequency and dates
            if repayment.start_date and repayment.end_date and repayment.repayment_frequency:
                if repayment.repayment_frequency == '0':  # Cash
                    total_installments = 1
                    paid_installments = 1 if repayment.total_paid >= repayment.selling_price else 0
                else:
                    freq_days = int(repayment.repayment_frequency)
                    total_days = (repayment.end_date - repayment.start_date).days
                    total_installments = max(1, total_days // freq_days)
                    
                    # Count actual payments made
                    paid_installments = len(repayment.payment_lines)
            
            # Determine status
            status = 'Active'
            status_color = '#10b981'  # Green
            if repayment.overdue_status:
                status = 'At Risk'
                status_color = '#ef4444'  # Red
            elif repayment.state == 'termination_warning':
                status = 'Warning'
                status_color = '#f59e0b'  # Orange
            elif repayment.state == 'draft':
                status = 'Draft'
                status_color = '#6b7280'  # Gray
            
            installments.append({
                'customer_name': repayment.customer_name.name if repayment.customer_name else 'Unknown',
                'customer_initials': self._get_customer_initials(repayment.customer_name.name if repayment.customer_name else 'Unknown'),
                'product': product_name,
                'installments': f"{paid_installments}/{total_installments}",
                'total_price': repayment.selling_price,
                'paid_percentage': round(repayment.percentage_paid, 0),
                'status': status,
                'status_color': status_color,
                'unique_id': repayment.unique_id
            })
        
        return installments
    
    def _get_customer_initials(self, name):
        """Get initials from customer name"""
        if not name:
            return 'NA'
        
        parts = name.split()
        if len(parts) >= 2:
            return (parts[0][0] + parts[1][0]).upper()
        elif len(parts) == 1:
            return parts[0][:2].upper()
        return 'NA'

    @api.model
    def get_top_agents_by_performance(self, limit=10):
        """
        Fetch top sales agents by repayment performance
        Returns: list of dicts with agent names and repayment percentages
        """
        # Get all repayments with sales agents (created_by field)
        all_repayments = self.search([
            ('created_by', '!=', False)
        ])
        
        if not all_repayments:
            return []
        
        # Group repayments by agent
        agent_stats = {}
        for repayment in all_repayments:
            agent_id = repayment.created_by
            agent_name = agent_id.name if agent_id else 'Unknown Agent'
            
            if agent_id.id not in agent_stats:
                agent_stats[agent_id.id] = {
                    'agent_name': agent_name,
                    'total_repayments': 0,
                    'paid_repayments': 0,
                    'total_value': 0,
                    'paid_value': 0
                }
            
            # Update agent statistics
            agent_stats[agent_id.id]['total_repayments'] += 1
            agent_stats[agent_id.id]['total_value'] += repayment.selling_price
            
            # Count as paid if fully paid
            if repayment.state == 'paid' or repayment.total_paid >= repayment.selling_price:
                agent_stats[agent_id.id]['paid_repayments'] += 1
                agent_stats[agent_id.id]['paid_value'] += repayment.selling_price
        
        # Calculate repayment percentages for each agent
        agents_data = []
        for agent_id, stats in agent_stats.items():
            # Calculate repayment percentage (by count and by value)
            repayment_percentage_by_count = 0
            repayment_percentage_by_value = 0
            
            if stats['total_repayments'] > 0:
                repayment_percentage_by_count = (stats['paid_repayments'] / stats['total_repayments']) * 100
            
            if stats['total_value'] > 0:
                repayment_percentage_by_value = (stats['paid_value'] / stats['total_value']) * 100
            
            # Use value-based percentage as primary metric (more meaningful for sales performance)
            final_percentage = repayment_percentage_by_value
            
            agents_data.append({
                'agent_name': stats['agent_name'],
                'repayment_percentage': round(final_percentage, 1),
                'total_repayments': stats['total_repayments'],
                'paid_repayments': stats['paid_repayments'],
                'total_value': round(stats['total_value'], 2),
                'paid_value': round(stats['paid_value'], 2)
            })
        
        # Sort by repayment percentage (descending) and limit results
        agents_data.sort(key=lambda x: x['repayment_percentage'], reverse=True)
        
        return agents_data[:limit]



