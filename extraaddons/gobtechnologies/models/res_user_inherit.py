from odoo import api, models, fields, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)

ROLE_GROUP_MAP = {
    'general_manager': 'gobtechnologies.group_general_manager',
    'supervisor': 'gobtechnologies.group_supervisor',
    'sales_administrator': 'gobtechnologies.group_sales_administrator',
    'sales_manager': 'gobtechnologies.group_repayment_sales',
    'sales_agent': 'gobtechnologies.group_repayment_agent',
    'customer_care': 'gobtechnologies.group_customer_care',
    'internal_auditor': 'gobtechnologies.group_internal_auditor',
}

ALL_ROLE_GROUP_XMLIDS = list(ROLE_GROUP_MAP.values())


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
    ], string="User Role")
    supervisor = fields.Char(string="Supervisor")
    general_manager = fields.Char(string="General Manager")
    sales_administrator = fields.Char(string="Sales Administrator")
    sales_manager = fields.Char(string="Sales Manager")
    sales_agent = fields.Char(string="Sales Agent")

    @api.constrains('role')
    def _check_role(self):
        for user in self:
            if not user.role:
                raise ValidationError(_('User Role is required. Please select a role for this user.'))

    def _sync_role_to_group(self):
        for user in self:
            all_groups = self.env['res.groups']
            for xmlid in ALL_ROLE_GROUP_XMLIDS:
                all_groups |= self.env.ref(xmlid)

            # Remove from all role groups first
            current_role_groups = [g for g in all_groups if g in user.groups_id]
            if current_role_groups:
                user.sudo().write({'groups_id': [(3, g.id) for g in current_role_groups]})

            # Then add to the correct group (implied_ids handles the hierarchy)
            if user.role and user.role in ROLE_GROUP_MAP:
                target_group = self.env.ref(ROLE_GROUP_MAP[user.role])
                target_group.sudo().write({'users': [(4, user.id)]})

    @api.model
    def create(self, vals):
        user = super().create(vals)
        if user.role:
            user._sync_role_to_group()
            role_field_map = {
                'supervisor': 'supervisor',
                'general_manager': 'general_manager',
                'sales_administrator': 'sales_administrator',
                'sales_manager': 'sales_manager',
                'sales_agent': 'sales_agent',
            }
            field_name = role_field_map.get(self.env.user.role)
            if field_name:
                user.write({field_name: self.env.user.name})
                user.partner_id.write({
                    field_name: self.env.user.name,
                    'role': user.role,
                })
        return user

    def write(self, vals):
        if 'role' in vals and self.env.user.role:
            role_field_map = {
                'supervisor': 'supervisor',
                'general_manager': 'general_manager',
                'sales_administrator': 'sales_administrator',
                'sales_manager': 'sales_manager',
                'sales_agent': 'sales_agent',
            }
            field_name = role_field_map.get(self.env.user.role)
            if field_name:
                vals[field_name] = self.env.user.name
        
        res = super().write(vals)

        if 'role' in vals:
            self._sync_role_to_group()

        if 'role' in vals or any(f in vals for f in ['supervisor', 'general_manager', 'sales_administrator', 'sales_manager', 'sales_agent']):
            for user in self:
                partner_vals = {}
                if 'role' in vals:
                    partner_vals['role'] = vals['role']
                    if self.env.user.role:
                        role_field_map = {
                            'supervisor': 'supervisor',
                            'general_manager': 'general_manager',
                            'sales_administrator': 'sales_administrator',
                            'sales_manager': 'sales_manager',
                            'sales_agent': 'sales_agent',
                        }
                        field_name = role_field_map.get(self.env.user.role)
                        if field_name:
                            partner_vals[field_name] = self.env.user.name
                
                for field in ['supervisor', 'general_manager', 'sales_administrator', 'sales_manager', 'sales_agent']:
                    if field in vals:
                        partner_vals[field] = vals[field]
                
                if partner_vals:
                    user.partner_id.write(partner_vals)
        return res