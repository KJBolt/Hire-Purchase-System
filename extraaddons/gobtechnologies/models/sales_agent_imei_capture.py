from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from datetime import date

class SalesAgentImeiCapture(models.Model):
    _name = 'sales.agent.imei.capture'
    _description = 'Sales Agent IMEI Capture'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'

    name = fields.Char(
        string="Reference",
        required=True, copy=False, readonly=True, index=True,
        default=lambda self: _('New')
    )
    agent_id = fields.Many2one(
        'res.users',
        string='Sales Agent',
        required=True,
        default=lambda self: self.env.user,
        readonly=True
    )
    agent_photo = fields.Binary(
        string='Agent Selfie',
        attachment=True,
        help='Upload a photo of the sales agent',
        required=True
    )
    warehouse_id = fields.Many2one(
        'stock.warehouse',
        string='Assigned Warehouse',
        readonly=True,
        compute='_compute_warehouse_id',
        store=True
    )
    capture_date = fields.Datetime(
        string='Date Captured',
        required=True,
        default=fields.Datetime.now,
        readonly=True
    )
    imei_ids = fields.Many2many(
        'stock.lot',
        string='IMEIs',
        domain="[('product_id', '!=', False), ('delivery_status', '!=', 'delivered'), ('warehouse_id', '=', warehouse_id), ('expiration_date', '<', context_today())]",
    )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved')
    ], string='Status', default='draft', tracking=True)
    notes = fields.Text(string='Notes')

    @api.depends('agent_id')
    def _compute_warehouse_id(self):
        for record in self:
            if record.agent_id and record.agent_id.property_warehouse_id:
                record.warehouse_id = record.agent_id.property_warehouse_id.id
            else:
                record.warehouse_id = False


    @api.constrains('imei_ids')
    def _check_imei_warehouse(self):
        for record in self:
            if not record.imei_ids:
                raise ValidationError('Please select at least one IMEI.')
            if record.imei_ids and record.warehouse_id:
                for lot in record.imei_ids:
                    if lot.warehouse_id != record.warehouse_id:
                        raise ValidationError(
                            f"IMEI '{lot.name}' is not in your assigned warehouse '{record.warehouse_id.name}'. "
                            f"Please select IMEIs from your assigned warehouse only."
                        )

    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('sales.agent.imei.capture') or _('New')
        return super(SalesAgentImeiCapture, self).create(vals)

    def action_submit(self):
        """Submit the capture record for documentation/review."""
        for record in self:
            if not record.agent_photo:
                raise ValidationError('Please upload a photo of the sales agent before submitting.')
            if not record.imei_ids:
                raise ValidationError('Please select at least one IMEI before submitting.')
            if not record.warehouse_id:
                raise ValidationError('Please ensure your user account has a warehouse assigned before submitting.')

            record.write({'state': 'submitted'})
            record.message_post(body='Capture record submitted successfully.')

    def action_approve(self):
        """Approve the capture record."""
        for record in self:
            record.write({'state': 'approved'})
            record.message_post(body='Capture record approved successfully.')
