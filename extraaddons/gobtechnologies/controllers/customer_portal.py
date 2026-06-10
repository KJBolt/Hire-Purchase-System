from odoo import http
from odoo.http import request
import json
import logging
import base64
import io
import secrets
from datetime import timedelta, datetime
from werkzeug.wrappers import Response
import requests

_logger = logging.getLogger(__name__)


class CustomerPortalController(http.Controller):

    def _get_portal_for_session(self):
        token = request.session.get('customer_portal_token')
        if not token:
            return False
        portal = request.env['customer.portal'].sudo().search([
            ('session_token', '=', token),
            ('otp_verified', '=', True),
        ], limit=1)
        if not portal:
            return False

        # Check session timeout (30 min inactivity)
        if portal.last_activity:
            if datetime.now() - timedelta(minutes=30) > fields.Datetime.from_string(portal.last_activity):
                portal.write({'session_token': False, 'otp_verified': False})
                request.session.pop('customer_portal_token', None)
                return False

        portal.write({'last_activity': fields.Datetime.now()})
        return portal

    def _get_repayment_data(self, repayment):
        """Helper to get repayment data for dashboard"""
        if not repayment:
            return {}
        return {
            'customer_name': repayment.customer_name.name if repayment.customer_name else '',
            'phone_no': repayment.phone_no or '',
            'unique_id': repayment.unique_id or '',
            'selling_price': repayment.selling_price or 0.0,
            'total_paid': repayment.total_paid or 0.0,
            'outstanding_balance': repayment.outstanding_loan or 0.0,
            'state': repayment.state or '',
        }

    # ------------------------------------------------------------
    # ROUTES
    # ------------------------------------------------------------

    @http.route('/customer/portal', type='http', auth='public', website=True, sitemap=False)
    def portal(self, **kw):
        return request.render('gobtechnologies.customer_portal_template')

    @http.route('/customer/request-otp', type='json', auth='public', methods=['POST'], csrf=False)
    def request_otp(self, **kw):
        phone_no = kw.get('phone_no', '').strip()
        if not phone_no or len(phone_no) < 10:
            return {'success': False, 'message': 'Please enter a valid phone number.'}

        try:
            portal = request.env['customer.portal'].sudo().find_or_create(phone_no)
            if not portal:
                return {'success': False, 'message': 'Could not create portal session.'}

            result = portal.generate_and_send_otp()
            if result:
                return {'success': True, 'message': 'OTP sent successfully. Please check your phone.'}
            else:
                return {'success': False, 'message': 'Failed to send OTP. Please try again.'}
        except Exception as e:
            _logger.error(f"OTP request error: {str(e)}", exc_info=True)
            return {'success': False, 'message': 'An error occurred. Please try again.'}

    @http.route('/customer/verify-otp', type='json', auth='public', methods=['POST'], csrf=False)
    def verify_otp(self, **kw):
        phone_no = kw.get('phone_no', '').strip()
        otp_code = kw.get('otp_code', '').strip()

        if not phone_no or not otp_code:
            return {'success': False, 'message': 'Please provide phone number and OTP code.'}

        if len(otp_code) != 6:
            return {'success': False, 'message': 'OTP code must be 6 digits.'}

        try:
            portal = request.env['customer.portal'].sudo().search([('phone_no', '=', phone_no)], limit=1)
            if not portal:
                return {'success': False, 'message': 'No OTP was requested for this number.'}

            result = portal.verify_otp(otp_code)
            if result['success']:
                token = secrets.token_urlsafe(32)
                portal.write({
                    'session_token': token,
                    'last_activity': fields.Datetime.now(),
                })
                request.session['customer_portal_token'] = token
                request.session['customer_portal_phone'] = phone_no
            return result
        except Exception as e:
            _logger.error(f"OTP verify error: {str(e)}", exc_info=True)
            return {'success': False, 'message': 'An error occurred. Please try again.'}

    @http.route('/customer/dashboard', type='http', auth='public', website=True, sitemap=False)
    def dashboard(self, **kw):
        portal = self._get_portal_for_session()
        if not portal:
            return request.redirect('/customer/portal')

        repayment = portal.repayment_id
        if not repayment:
            return request.render('gobtechnologies.customer_dashboard_template', {
                'customer_name': '',
                'phone_no': portal.phone_no,
                'repayment': False,
                'selling_price': 0,
                'total_paid': 0,
                'outstanding_balance': 0,
                'payment_lines': [],
            })

        payment_lines_data = []
        for line in repayment.payment_lines.sorted(key=lambda p: p.payment_date or fields.Date.today(), reverse=True):
            payment_lines_data.append({
                'id': line.id,
                'payment_date': str(line.payment_date) if line.payment_date else '',
                'payment_amount': f"{line.payment_amount:,.2f}",
                'payment_mode': dict(line._fields['payment_mode'].selection).get(line.payment_mode, line.payment_mode or ''),
                'payment_status': line.payment_status or 'Pending',
            })

        return request.render('gobtechnologies.customer_dashboard_template', {
            'customer_name': repayment.customer_name.name if repayment.customer_name else '',
            'phone_no': portal.phone_no,
            'repayment': repayment,
            'selling_price': f"{repayment.selling_price:,.2f}",
            'total_paid': f"{repayment.total_paid:,.2f}",
            'outstanding_balance': f"{repayment.outstanding_loan:,.2f}",
            'payment_lines': payment_lines_data,
        })

    @http.route('/customer/initiate-payment', type='json', auth='public', methods=['POST'], csrf=False)
    def initiate_payment(self, **kw):
        portal = self._get_portal_for_session()
        if not portal:
            return {'success': False, 'message': 'Session expired. Please login again.', 'redirect': '/customer/portal'}

        amount = kw.get('amount', 0)
        try:
            amount = float(amount)
        except (ValueError, TypeError):
            return {'success': False, 'message': 'Invalid payment amount.'}

        if amount <= 0:
            return {'success': False, 'message': 'Please enter a valid payment amount.'}

        repayment = portal.repayment_id
        if not repayment:
            return {'success': False, 'message': 'No repayment record found.'}

        try:
            result = self._initiate_hubtel_payment(portal, repayment, amount)
            return result
        except Exception as e:
            _logger.error(f"Payment initiation error: {str(e)}", exc_info=True)
            return {'success': False, 'message': 'Failed to initiate payment. Please try again.'}

    def _initiate_hubtel_payment(self, portal, repayment, amount):
        settings = request.env['res.config.settings'].sudo().get_hubtel_credentials()
        client_id = settings.get('client_id')
        client_secret = settings.get('client_secret')
        webhook_url = settings.get('webhook_url', '')

        if not all([client_id, client_secret]):
            return {'success': False, 'message': 'Hubtel not configured. Please contact support.'}

        phone = portal.phone_no
        if phone.startswith('0'):
            phone = '233' + phone[1:]
        phone = phone.replace(' ', '').replace('-', '')

        customer_name = repayment.customer_name.name if repayment.customer_name else 'Customer'
        client_ref = f"customer_portal_{phone}_{repayment.id}"

        payload = {
            'customerName': customer_name,
            'customerEmail': '',
            'customerPhoneNumber': phone,
            'channel': 'mobilemoney',
            'amount': amount,
            'description': f"HP Payment - {repayment.unique_id}",
            'primaryCallbackUrl': webhook_url or 'https://yourdomain.com/web/hook/d69a6f81-e899-4509-85dd-8655a1543259',
            'clientReference': client_ref,
        }

        api_url = 'https://api.hubtel.com/v1/merchant-account/transactions/receive-money'

        _logger.info(f"Initiating Hubtel payment: {json.dumps(payload)}")

        response = requests.post(
            api_url,
            auth=(client_id, client_secret),
            json=payload,
            timeout=30,
            headers={'Content-Type': 'application/json'}
        )

        _logger.info(f"Hubtel API Response: {response.status_code} - {response.text}")

        if response.status_code in [200, 201]:
            data = response.json()
            return {
                'success': True,
                'message': 'Payment prompt sent to your phone. Please approve the transaction.',
                'transaction_id': data.get('id', ''),
            }
        else:
            error_msg = 'Failed to initiate payment with Hubtel. Please try again.'
            try:
                error_data = response.json()
                if error_data.get('message'):
                    error_msg = error_data['message']
            except:
                pass
            return {'success': False, 'message': error_msg}

    @http.route('/customer/receipt/<int:payment_line_id>', type='http', auth='public', website=True, sitemap=False)
    def download_receipt(self, payment_line_id):
        portal = self._get_portal_for_session()
        if not portal:
            return request.redirect('/customer/portal')

        payment_line = request.env['repayment.payment.line'].sudo().browse(payment_line_id)
        if not payment_line.exists() or payment_line.repayment_id != portal.repayment_id:
            return request.not_found()

        repayment = payment_line.repayment_id

        receipt_html = """
        <html>
        <head>
            <meta charset="utf-8" />
            <style>
                body { font-family: 'DejaVu Sans', Arial, sans-serif; margin: 0; padding: 40px; color: #333; }
                .header { text-align: center; border-bottom: 3px solid #6366f1; padding-bottom: 20px; margin-bottom: 30px; }
                .header h1 { color: #6366f1; margin: 0; font-size: 24px; }
                .header p { color: #666; margin: 5px 0 0; font-size: 12px; }
                .receipt-details { margin-bottom: 30px; }
                .receipt-details table { width: 100%%; border-collapse: collapse; }
                .receipt-details td { padding: 8px 12px; border-bottom: 1px solid #eee; font-size: 13px; }
                .receipt-details td:first-child { font-weight: bold; color: #555; width: 40%%; }
                .receipt-details td:last-child { text-align: right; }
                .amount-row td { font-size: 15px; font-weight: bold; color: #6366f1; }
                .footer { text-align: center; margin-top: 40px; padding-top: 20px; border-top: 1px solid #ddd; font-size: 11px; color: #999; }
                .status-badge { display: inline-block; padding: 3px 12px; border-radius: 10px; font-size: 11px; font-weight: bold; }
                .status-paid { background: #d1fae5; color: #065f46; }
                .watermark { position: fixed; top: 50%%; left: 50%%; transform: translate(-50%%, -50%%) rotate(-30deg); font-size: 80px; color: rgba(99,102,241,0.04); font-weight: bold; z-index: -1; }
            </style>
        </head>
        <body>
            <div class="watermark">RECEIPT</div>
            <div class="header">
                <h1>PAYMENT RECEIPT</h1>
                <p>Sarfosco Hire Purchase System</p>
            </div>
            <div class="receipt-details">
                <table>
                    <tr><td>Receipt Number</td><td><strong>RCP-%s</strong></td></tr>
                    <tr><td>Customer Name</td><td><strong>%s</strong></td></tr>
                    <tr><td>Phone Number</td><td><strong>%s</strong></td></tr>
                    <tr><td>Reference</td><td><strong>%s</strong></td></tr>
                    <tr><td>Payment Date</td><td><strong>%s</strong></td></tr>
                    <tr><td>Payment Mode</td><td><strong>%s</strong></td></tr>
                    <tr class="amount-row"><td>Payment Amount (GHS)</td><td><strong>%s</strong></td></tr>
                    <tr><td>Status</td><td><strong><span class="status-badge status-paid">Paid</span></strong></td></tr>
                    <tr><td>Outstanding Balance</td><td><strong>GHS %s</strong></td></tr>
                </table>
            </div>
            <div class="footer">
                <p>This is a computer-generated receipt. No signature required.</p>
                <p>Sarfosco &copy; %s All Rights Reserved</p>
            </div>
        </body>
        </html>
        """ % (
            str(payment_line.id).zfill(6),
            repayment.customer_name.name or '',
            repayment.phone_no or '',
            repayment.unique_id or '',
            str(payment_line.payment_date or ''),
            dict(payment_line._fields['payment_mode'].selection).get(payment_line.payment_mode, payment_line.payment_mode or 'N/A'),
            f"{payment_line.payment_amount:,.2f}" if payment_line.payment_amount else '0.00',
            f"{repayment.outstanding_loan:,.2f}",
            fields.Date.today().year,
        )

        pdf_content = self._render_html_to_pdf(receipt_html)
        if not pdf_content:
            return Response(receipt_html, content_type='text/html')

        return request.make_response(
            pdf_content,
            headers=[
                ('Content-Type', 'application/pdf'),
                ('Content-Disposition', f'attachment; filename="receipt_{payment_line.id}.pdf"'),
            ]
        )

    def _render_html_to_pdf(self, html):
        try:
            import tempfile
            import subprocess
            import os

            with tempfile.NamedTemporaryFile(suffix='.html', delete=False, mode='w', encoding='utf-8') as f:
                f.write(html)
                html_path = f.name

            pdf_path = html_path.replace('.html', '.pdf')

            # Try wkhtmltopdf first
            try:
                subprocess.run(
                    ['wkhtmltopdf', '--encoding', 'utf-8', html_path, pdf_path],
                    capture_output=True, timeout=60
                )
                if os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 0:
                    with open(pdf_path, 'rb') as f:
                        pdf_data = f.read()
                    os.unlink(html_path)
                    os.unlink(pdf_path)
                    return pdf_data
            except:
                pass

            # Fallback: try weasyprint
            try:
                from weasyprint import HTML
                pdf_data = HTML(string=html).write_pdf()
                os.unlink(html_path)
                return pdf_data
            except:
                pass

            os.unlink(html_path)
            return False
        except Exception as e:
            _logger.error(f"PDF generation error: {str(e)}")
            return False

    @http.route('/customer/logout', type='http', auth='public', website=True, sitemap=False)
    def logout(self, **kw):
        token = request.session.get('customer_portal_token')
        if token:
            portal = request.env['customer.portal'].sudo().search([
                ('session_token', '=', token)
            ], limit=1)
            if portal:
                portal.write({
                    'session_token': False,
                    'otp_verified': False,
                })
        request.session.pop('customer_portal_token', None)
        request.session.pop('customer_portal_phone', None)
        return request.redirect('/customer/portal')


# Need to import fields at module level for the controller
from odoo import fields
