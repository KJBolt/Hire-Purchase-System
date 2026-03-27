from odoo import models, fields, api

class RepaymentPenalty(models.Model):
    _name = 'repayment.penalty'
    _description = 'Repayment Penalty Records'

    repayment_id = fields.Many2one(
        'repayment',
        string='Repayment',
        required=True,
        ondelete='cascade'
    )
    penalty_date = fields.Date(
        string='Penalty Date',
        required=True,
        default=fields.Date.context_today
    )
    penalty_amount = fields.Float(
        string='Penalty Amount',
        required=True
    )
    reason = fields.Char(
        string='Reason',
        required=True
    )
    state = fields.Selection([
        ('pending', 'Pending'),
        ('paid', 'Paid')
    ], string='Status', default='pending')
