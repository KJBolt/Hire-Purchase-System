from odoo import api, fields, models


class StockLot(models.Model):
    _inherit = 'stock.lot'

    warehouse_id = fields.Many2one(
        'stock.warehouse',
        string='Warehouse',
        compute='_compute_warehouse_id',
        store=True,
        help='Warehouse where this lot is currently located'
    )

    imei_selfie = fields.Image(string='IMEI Photo', help='Selfie image captured with IMEI')

    def action_view_imei_selfie(self):
        self.ensure_one()
        wizard = self.env['imei.selfie.wizard'].create({
            'imei_selfie': self.imei_selfie,
            'lot_name': self.name,
        })
        return {
            'name': 'IMEI Selfie',
            'type': 'ir.actions.act_window',
            'res_model': 'imei.selfie.wizard',
            'view_mode': 'form',
            'res_id': wizard.id,
            'target': 'new',
        }

    @api.depends('quant_ids')
    def _compute_warehouse_id(self):
        for lot in self:
            if lot.quant_ids:
                # Find the warehouse based on the lot's location
                for quant in lot.quant_ids:
                    if quant.location_id:
                        # Search for warehouse that contains this location
                        warehouse = self.env['stock.warehouse'].search([
                            ('lot_stock_id', 'parent_of', quant.location_id.id)
                        ], limit=1)
                        if warehouse:
                            lot.warehouse_id = warehouse.id
                            break
                if not lot.warehouse_id:
                    lot.warehouse_id = False
            else:
                lot.warehouse_id = False
