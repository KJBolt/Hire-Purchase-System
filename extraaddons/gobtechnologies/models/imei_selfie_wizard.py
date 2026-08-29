from odoo import fields, models


class ImeiSelfieWizard(models.TransientModel):
    _name = 'imei.selfie.wizard'
    _description = 'IMEI Selfie Viewer'

    imei_selfie = fields.Image(string='IMEI Selfie', required=True)
    lot_name = fields.Char(string='IMEI / Lot')
