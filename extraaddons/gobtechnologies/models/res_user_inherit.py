from odoo import api, models, fields
import logging

_logger = logging.getLogger(__name__)

class ResUserInherit(models.Model):
    _inherit = 'res.users'
    
    created_by = fields.Char(string="Created By")
    role = fields.Selection([
        ('general_manager', 'General Manager'),
        ('supervisor', 'Supervisor'),
        ('sales_administrator', 'Sales Administrator'),
        ('sales_manager', 'Sales Manager'),
        ('sales_agent', 'Sales Agent'),
        ('customer_care', 'Customer Care'),
        ('internal_auditor', 'Internal Auditor'),
    ], string="User Role", required=True)
    supervisor = fields.Char(string="Supervisor")
    general_manager = fields.Char(string="General Manager")
    sales_administrator = fields.Char(string="Sales Administrator")
    sales_manager = fields.Char(string="Sales Manager")
    sales_agent = fields.Char(string="Sales Agent")

    # @api.model
    # def create(self, vals):
    #     if self.env.user.role:
    #         role_field_map = {
    #             'general_manager': 'general_manager',
    #             'supervisor': 'supervisor',
    #             'sales_administrator': 'sales_administrator',
    #             'sales_manager': 'sales_manager',
    #             'sales_agent': 'sales_agent',
    #         }
    #         field_name = role_field_map.get(self.env.user.role)
    #         if field_name:
    #             vals[field_name] = self.env.user.name
    #     return super().create(vals)
    

    # populate the roles fields in contacts when a user is created in settings
    @api.model
    def create(self, vals):
        user = super().create(vals)
        if user.role:
            role_field_map = {
                'general_manager': 'general_manager',
                'supervisor': 'supervisor',
                'sales_administrator': 'sales_administrator',
                'sales_manager': 'sales_manager',
                'sales_agent': 'sales_agent',
            }
            field_name = role_field_map.get(user.role)
            if field_name:
                user.partner_id.write({
                    field_name: user.env.user.name,
                    'role': user.role,
                })
        return user


    # update the roles fields in contacts when a user is updated in settings
    def write(self, vals):
        res = super().write(vals)
        if 'role' in vals or any(f in vals for f in ['supervisor', 'general_manager', 'sales_administrator', 'sales_manager', 'sales_agent']):
            for user in self:
                partner_vals = {}
                if 'role' in vals:
                    partner_vals['role'] = vals['role']
                for field in ['supervisor', 'general_manager', 'sales_administrator', 'sales_manager', 'sales_agent']:
                    if field in vals:
                        partner_vals[field] = vals[field]
                if partner_vals:
                    user.partner_id.write(partner_vals)
        return res