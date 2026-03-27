from odoo import models, fields, api
from odoo.exceptions import UserError

class ProductTemplateInherit(models.Model):
    _inherit = 'product.template'
    
    # 60 days plan
    plan_60_deposit = fields.Float(string="Deposit", required=True)
    plan_60_daily = fields.Float(string="Daily", required=True)
    plan_60_weekly = fields.Float(string="Weekly", required=True)
    plan_60_total = fields.Float(string="Total", required=True)
    
    # 90 days plan
    plan_90_deposit = fields.Float(string="Deposit", required=True)
    plan_90_daily = fields.Float(string="Daily", required=True)
    plan_90_weekly = fields.Float(string="Weekly", required=True)
    plan_90_total = fields.Float(string="Total", required=True)
    
    # 120 days plan
    plan_120_deposit = fields.Float(string="Deposit", required=True)
    plan_120_daily = fields.Float(string="Daily", required=True)
    plan_120_weekly = fields.Float(string="Weekly", required=True)
    plan_120_total = fields.Float(string="Total", required=True)


    @api.constrains('plan_60_deposit', 'plan_60_daily', 'plan_60_weekly', 'plan_60_total', 'plan_90_deposit',
        'plan_90_daily', 'plan_90_weekly', 'plan_90_total', 'plan_120_deposit', 'plan_120_daily', 'plan_120_weekly',
        'plan_120_total'
    )
    def check_not_zero(self):
        for record in self:
            if not (record.plan_60_deposit or record.plan_60_daily or record.plan_60_weekly or record.plan_60_total
                or record.plan_90_deposit or record.plan_90_daily or record.plan_90_weekly or record.plan_90_total
                or record.plan_120_deposit or record.plan_120_daily or record.plan_120_weekly or record.plan_120_total):
                    raise UserError("Payment plan fields are required")

