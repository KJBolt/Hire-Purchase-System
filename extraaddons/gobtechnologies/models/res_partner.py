from odoo import api, models, fields
import logging

_logger = logging.getLogger(__name__)

class ResPartnerInherit(models.Model):
    _inherit = 'res.partner'
    
    created_by = fields.Char(string="Created By")
    role = fields.Selection([
        ('general_manager', 'General Manager'),
        ('supervisor', 'Supervisor'),
        ('sales_administrator', 'Sales Administrator'),
        ('sales_manager', 'Sales Manager'),
        ('sales_agent', 'Sales Agent'),
        ('customer_care', 'Customer Care'),
        ('internal_auditor', 'Internal Auditor'),
    ], string="User Role")
    supervisor = fields.Char(string="Supervisor")
    general_manager = fields.Char(string="General Manager")
    sales_administrator = fields.Char(string="Sales Administrator")
    sales_manager = fields.Char(string="Sales Manager")
    sales_agent = fields.Char(string="Sales Agent")

    @api.model
    def create(self, vals):
        if self.env.user.role:
            role_field_map = {
                'general_manager': 'general_manager',
                'supervisor': 'supervisor',
                'sales_administrator': 'sales_administrator',
                'sales_manager': 'sales_manager',
                'sales_agent': 'sales_agent',
            }
            field_name = role_field_map.get(self.env.user.role)
            if field_name:
                vals[field_name] = self.env.user.name
        return super().create(vals)