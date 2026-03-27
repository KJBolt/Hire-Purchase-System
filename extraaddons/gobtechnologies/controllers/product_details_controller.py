from odoo import http
from odoo.http import request
import logging
import json

_logger = logging.getLogger(__name__)

class ProductDetailsController(http.Controller):
    @http.route('/shop/product/<int:product_id>', type='http', auth='public', methods=['GET'], website=True, csrf=False)
    def get_product_details(self, product_id, **kwargs):
        """
        Display product details for a specific product
        :param product_id: ID of the product to display
        """
        # Search for the product by ID
        product = request.env['product.template'].sudo().search([
            ('id', '=', product_id),
            ('sale_ok', '=', True),
            ('active', '=', True)
        ], limit=1)
        
        # If product not found, redirect to products page or show 404
        if not product:
            return request.render('website.404')
        
        # Prepare values for the template
        values = {
            'product': product,
        }
        
        return request.render('gobtechnologies.product_details_template', values)  

    # Fetch assiciate data based on selected options
    @http.route('/shop/product/<int:product_id>/select_plan', type='http', auth="public", methods=['GET', 'POST'], website=True, csrf=True)
    def select_payment_plan(self, product_id, plan_days=None, repayment_frequency=None, proceed_payment=None, **kw):
        """
        Handle payment plan selection and display updated product details
        """

        _logger.info(f"Plan Days => {plan_days}")
        # Search for the product by ID
        product = request.env['product.template'].sudo().search([
            ('id', '=', product_id),
            ('sale_ok', '=', True),
            ('active', '=', True)
        ], limit=1)

        # Initialize the values dictionary
        values = {
            'product': product,
            'plan_days': plan_days,
            'repayment_frequency': repayment_frequency,
        }

        # if plan days is set and repayment frequency is empty
        if plan_days and not repayment_frequency:
            values['payment_details'] = {
                'plan_60_deposit': '',
                'plan_60_daily': '',
                # 'plan_60_weekly': product.plan_60_weekly,
                'plan_60_total': '',
                'currency': ''
            }

            return request.render('gobtechnologies.product_details_template', values)


        # if plan days is empty and repayment frequency is set
        if not plan_days and repayment_frequency:
            values['payment_details'] = {
                'plan_60_deposit': '',
                'plan_60_daily': '',
                # 'plan_60_weekly': product.plan_60_weekly,
                'plan_60_total': '',
                'currency': ''
            }

            return request.render('gobtechnologies.product_details_template', values)


        if plan_days == '60' and repayment_frequency == 'daily':
            values['payment_details'] = {
                'plan_60_deposit': product.plan_60_deposit,
                'plan_60_daily': product.plan_60_daily,
                # 'plan_60_weekly': product.plan_60_weekly,
                'plan_60_total': product.plan_60_total,
                'currency': product.currency_id.name or 'GHS'
            }

            return request.render('gobtechnologies.product_details_template', values)

        if plan_days == '60' and repayment_frequency == 'weekly':
            values['payment_details'] = {
                'plan_60_deposit': product.plan_60_deposit,
                # 'plan_60_daily': product.plan_60_daily,
                'plan_60_weekly': product.plan_60_weekly,
                'plan_60_total': product.plan_60_total,
                'currency': product.currency_id.name or 'GHS'
            }

            return request.render('gobtechnologies.product_details_template', values)

        if plan_days == '90' and repayment_frequency == 'daily':
            values['payment_details'] = {
                'plan_90_deposit': product.plan_90_deposit,
                'plan_90_daily': product.plan_90_daily,
                # 'plan_90_weekly': product.plan_90_weekly,
                'plan_90_total': product.plan_90_total,
                'currency': product.currency_id.name or 'GHS'
            }

            return request.render('gobtechnologies.product_details_template', values)

        if plan_days == '90' and repayment_frequency == 'weekly':
            values['payment_details'] = {
                'plan_90_deposit': product.plan_90_deposit,
                # 'plan_90_daily': product.plan_90_daily,
                'plan_90_weekly': product.plan_90_weekly,
                'plan_90_total': product.plan_90_total,
                'currency': product.currency_id.name or 'GHS'
            }

            return request.render('gobtechnologies.product_details_template', values)

        if plan_days == '120' and repayment_frequency == 'daily':
            values['payment_details'] = {
                'plan_120_deposit': product.plan_120_deposit,
                'plan_120_daily': product.plan_120_daily,
                # 'plan_120_weekly': product.plan_120_weekly,
                'plan_120_total': product.plan_120_total,
                'currency': product.currency_id.name or 'GHS'
            }

            return request.render('gobtechnologies.product_details_template', values)

        if plan_days == '120' and repayment_frequency == 'weekly':
            values['payment_details'] = {
                'plan_120_deposit': product.plan_120_deposit,
                # 'plan_120_daily': product.plan_120_daily,
                'plan_120_weekly': product.plan_120_weekly,
                'plan_120_total': product.plan_120_total,
                'currency': product.currency_id.name or 'GHS'
            }

            return request.render('gobtechnologies.product_details_template', values)
        
        # Default case when no valid plan or frequency is selected
        return request.redirect(f'/shop/product/{product_id}')