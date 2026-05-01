from odoo import models, fields, api
from odoo.exceptions import UserError

class ProductTemplateInherit(models.Model):
    _inherit = 'product.template'

    sales_commission_type = fields.Selection([
    ('percentage', 'Percentage'),
    ('fixed', 'Fixed Amount')
    ], string="Commission Type", default='percentage')
    sales_commission_value = fields.Float(string="Commission Value", digits=(16, 2))
    

