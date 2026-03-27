from odoo import models, fields, api

class SettingsInherit(models.Model):
    _inherit = 'res.users'

    @api.model
    def create(self, vals):
        res = super(SettingsInherit, self).create(vals)
        # check if email field in contacts is not empty before saving
        user_id = self.env['res.users'].search([('id', '=', res.id)])
        if not user_id.email:
            raise UserError('Email field is required')
        return res