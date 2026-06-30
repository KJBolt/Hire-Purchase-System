from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class PaymentPlan(models.Model):
    _name = 'payment.plan'
    _description = 'Payment Plan'
    _rec_name = 'display_name'

    name = fields.Char(
        string='Plan Name',
        required=True,
        help="A descriptive name for this plan, e.g. 'Samsung A14 - 6 Month Plan'"
    )
    product_id = fields.Many2one(
        'product.product',
        string='Product',
        required=True,
        ondelete='cascade',
        help="The product this payment plan applies to"
    )
    plan_duration = fields.Selection([
        ('30', '1 Month - 30 Days'),
        ('60', '2 Months - 60 Days'),
        ('90', '3 Months - 90 Days'),
        ('120', '4 Months - 120 Days'),
        ('150', '5 Months - 150 Days'),
        ('180', '6 Months - 180 Days'),
        ('210', '7 Months - 210 Days'),
    ], string='Plan Duration', required=True)
    selling_price = fields.Float(
        string='Selling Price',
        required=True,
        help="Total selling price for this plan"
    )
    deposit = fields.Float(
        string='Deposit',
        required=True,
        help="Upfront deposit amount"
    )
    daily_amount = fields.Float(
        string='Daily Amount',
        help="Fixed amount to pay per day (used when frequency is Daily)"
    )
    weekly_amount = fields.Float(
        string='Weekly Amount',
        help="Fixed amount to pay per week (used when frequency is Weekly)"
    )
    monthly_amount = fields.Float(
        string='Monthly Amount',
        help="Fixed amount to pay per month (used when frequency is Monthly)"
    )
    active = fields.Boolean(
        string='Active',
        default=True,
        help="Inactive plans are hidden from selection"
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True
    )

    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=True,
    )

    @api.depends('name', 'product_id', 'plan_duration', 'selling_price')
    def _compute_display_name(self):
        for record in self:
            product_name = record.product_id.name or ''
            duration_label = dict(record._fields['plan_duration'].selection).get(record.plan_duration, '')
            record.display_name = f"{record.name} ({product_name} - {duration_label} - GHS {record.selling_price})"

    @api.constrains('selling_price', 'deposit')
    def _check_prices(self):
        for record in self:
            if record.selling_price <= 0:
                raise ValidationError(_('Selling price must be greater than zero.'))
            if record.deposit < 0:
                raise ValidationError(_('Deposit cannot be negative.'))
            if record.deposit > record.selling_price:
                raise ValidationError(_('Deposit cannot exceed the selling price.'))

    @api.constrains('daily_amount', 'weekly_amount', 'monthly_amount')
    def _check_amounts(self):
        for record in self:
            if record.daily_amount < 0:
                raise ValidationError(_('Daily amount cannot be negative.'))
            if record.weekly_amount < 0:
                raise ValidationError(_('Weekly amount cannot be negative.'))
            if record.monthly_amount < 0:
                raise ValidationError(_('Monthly amount cannot be negative.'))
