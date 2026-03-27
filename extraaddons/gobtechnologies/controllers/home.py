from odoo import http
from odoo.http import request


class Home(http.Controller):
    @http.route('/home', type='http', auth="public", website=True)
    def home(self, **kw):
        return request.render('gobtechnologies.home')
