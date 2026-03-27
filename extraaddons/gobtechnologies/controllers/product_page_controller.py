from odoo import http
from odoo.http import request

class ProductPageController(http.Controller):
    @http.route('/shop/products', type='http', auth='public', methods=['GET'], website=True, csrf=False)
    def product_page(self, **kwargs):
        # Get search query from request parameters
        search_query = kwargs.get('search', '')
        
        # Fetch products that are active and can be sold
        domain = [
            ('sale_ok', '=', True),
            ('active', '=', True)
        ]
        
        # Add search condition if query exists
        if search_query:
            domain += [('name', 'ilike', search_query)]
        
        products = request.env['product.template'].sudo().search(domain)
        
        if products:
            values = {
                'products': products,
                'search_query': search_query
            }
            return request.render('gobtechnologies.product_page_template', values)
        else:
            values = {
                'products': products,
                'search_query': search_query
            }
            return request.render('gobtechnologies.product_page_template', values)