from odoo import http, fields
from odoo.http import request
import json
import logging
import secrets
import subprocess
import os
import tempfile
from datetime import timedelta
import requests

_logger = logging.getLogger(__name__)


class CustomerPortalController(http.Controller):

    SESSION_TIMEOUT_MINUTES = 30

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

        if portal.last_activity:
            last_activity = fields.Datetime.from_string(portal.last_activity)
            if fields.Datetime.now() - last_activity > timedelta(minutes=self.SESSION_TIMEOUT_MINUTES):
                portal.write({'session_token': False, 'otp_verified': False})
                request.session.pop('customer_portal_token', None)
                request.session.pop('customer_portal_phone', None)
                return False

        portal.write({'last_activity': fields.Datetime.now()})
        return portal

    def _portal_values(self, **extra):
        values = {
            'show_otp_form': False,
            'phone_no': '',
            'error_message': '',
            'success_message': '',
        }
        values.update(extra)
        return values

    def _dashboard_values(self, portal, **extra):
        repayment = portal.repayment_id
        payment_lines_data = []
        if repayment:
            for line in repayment.payment_lines.sorted(
                key=lambda p: p.payment_date or fields.Date.today(), reverse=True
            ):
                payment_lines_data.append({
                    'id': line.id,
                    'payment_date': str(line.payment_date) if line.payment_date else '',
                    'payment_amount': f"{line.payment_amount:,.2f}",
                    'payment_mode': dict(line._fields['payment_mode'].selection).get(
                        line.payment_mode, line.payment_mode or ''
                    ),
                    'payment_status': line.payment_status or 'Pending',
                    'receipt_no': line.receipt_no or str(line.id).zfill(6),
                })

        values = {
            'customer_name': repayment.customer_name.name if repayment and repayment.customer_name else '',
            'phone_no': portal.phone_no,
            'repayment': repayment,
            'selling_price': f"{repayment.selling_price:,.2f}" if repayment else '0.00',
            'total_paid': f"{repayment.total_paid:,.2f}" if repayment else '0.00',
            'outstanding_balance': f"{repayment.outstanding_loan:,.2f}" if repayment else '0.00',
            'payment_lines': payment_lines_data,
            'current_year': fields.Date.today().year,
            'error_message': '',
            'success_message': '',
        }
        values.update(extra)
        return values

    @http.route('/customer/portal', type='http', auth='public', website=True, sitemap=False)
    def portal(self, **kw):
        portal = self._get_portal_for_session()
        if portal:
            return request.redirect('/customer/dashboard')
        return request.render('gobtechnologies.customer_portal_template', self._portal_values())

    @http.route('/customer/request-otp', type='http', auth='public', methods=['POST'], website=True, csrf=True)
    def request_otp(self, **post):
        phone_no = (post.get('phone_no') or '').strip()
        if not phone_no or len(phone_no) < 10:
            return request.render('gobtechnologies.customer_portal_template', self._portal_values(
                error_message='Please enter a valid phone number.',
                phone_no=phone_no,
            ))

        try:
            portal = request.env['customer.portal'].sudo().find_or_create(phone_no)
            repayment = request.env['repayment'].sudo().search([('phone_no', '=', phone_no)], limit=1)
            if not repayment:
                return request.render('gobtechnologies.customer_portal_template', self._portal_values(
                    error_message='No hire purchase account found for this phone number.',
                    phone_no=phone_no,
                ))

            if not portal.generate_and_send_otp():
                return request.render('gobtechnologies.customer_portal_template', self._portal_values(
                    error_message='Failed to send OTP. Please try again.',
                    phone_no=phone_no,
                ))

            return request.render('gobtechnologies.customer_portal_template', self._portal_values(
                show_otp_form=True,
                phone_no=phone_no,
                success_message='OTP sent successfully. Please check your phone.',
            ))
        except Exception as e:
            _logger.error("OTP request error: %s", str(e), exc_info=True)
            return request.render('gobtechnologies.customer_portal_template', self._portal_values(
                error_message='An error occurred. Please try again.',
                phone_no=phone_no,
            ))

    @http.route('/customer/verify-otp', type='http', auth='public', methods=['POST'], website=True, csrf=True)
    def verify_otp(self, **post):
        phone_no = (post.get('phone_no') or '').strip()
        otp_code = (post.get('otp_code') or '').strip()

        if not phone_no or not otp_code:
            return request.render('gobtechnologies.customer_portal_template', self._portal_values(
                show_otp_form=True,
                phone_no=phone_no,
                error_message='Please provide your phone number and OTP code.',
            ))

        if len(otp_code) != 6 or not otp_code.isdigit():
            return request.render('gobtechnologies.customer_portal_template', self._portal_values(
                show_otp_form=True,
                phone_no=phone_no,
                error_message='OTP code must be 6 digits.',
            ))

        try:
            portal = request.env['customer.portal'].sudo().search([('phone_no', '=', phone_no)], limit=1)
            if not portal:
                return request.render('gobtechnologies.customer_portal_template', self._portal_values(
                    error_message='No OTP was requested for this number.',
                    phone_no=phone_no,
                ))

            result = portal.verify_otp(otp_code)
            if not result['success']:
                return request.render('gobtechnologies.customer_portal_template', self._portal_values(
                    show_otp_form=True,
                    phone_no=phone_no,
                    error_message=result['message'],
                ))

            token = secrets.token_urlsafe(32)
            portal.write({
                'session_token': token,
                'last_activity': fields.Datetime.now(),
            })
            request.session['customer_portal_token'] = token
            request.session['customer_portal_phone'] = phone_no
            return request.redirect('/customer/dashboard')
        except Exception as e:
            _logger.error("OTP verify error: %s", str(e), exc_info=True)
            return request.render('gobtechnologies.customer_portal_template', self._portal_values(
                show_otp_form=True,
                phone_no=phone_no,
                error_message='An error occurred. Please try again.',
            ))

    @http.route('/customer/dashboard', type='http', auth='public', website=True, sitemap=False)
    def dashboard(self, **kw):
        portal = self._get_portal_for_session()
        if not portal:
            return request.redirect('/customer/portal')

        return request.render(
            'gobtechnologies.customer_dashboard_template',
            self._dashboard_values(portal),
        )

    @http.route('/customer/initiate-payment', type='http', auth='public', methods=['POST'], website=True, csrf=True)
    def initiate_payment(self, **post):
        portal = self._get_portal_for_session()
        if not portal:
            return request.redirect('/customer/portal')

        amount_raw = post.get('amount', 0)
        try:
            amount = float(amount_raw)
        except (ValueError, TypeError):
            return request.render('gobtechnologies.customer_dashboard_template', self._dashboard_values(
                portal,
                error_message='Invalid payment amount.',
            ))

        if amount <= 0:
            return request.render('gobtechnologies.customer_dashboard_template', self._dashboard_values(
                portal,
                error_message='Please enter a valid payment amount.',
            ))

        repayment = portal.repayment_id
        if not repayment:
            return request.render('gobtechnologies.customer_dashboard_template', self._dashboard_values(
                portal,
                error_message='No repayment record found for your account.',
            ))

        try:
            result = self._initiate_hubtel_payment(portal, repayment, amount)
            if result.get('success'):
                return request.render('gobtechnologies.customer_dashboard_template', self._dashboard_values(
                    portal,
                    success_message=result.get('message', 'Payment prompt sent to your phone.'),
                ))
            return request.render('gobtechnologies.customer_dashboard_template', self._dashboard_values(
                portal,
                error_message=result.get('message', 'Failed to initiate payment.'),
            ))
        except Exception as e:
            _logger.error("Payment initiation error: %s", str(e), exc_info=True)
            return request.render('gobtechnologies.customer_dashboard_template', self._dashboard_values(
                portal,
                error_message='Failed to initiate payment. Please try again.',
            ))

    def _detect_momo_channel(self, phone):
        phone = phone.replace(' ', '').replace('-', '')
        if phone.startswith('0'):
            phone = '233' + phone[1:]
        if phone.startswith('233'):
            phone = phone[3:]
        prefixes = {
            'mtn-gh': ['24', '54', '55', '59'],
            'vodafone-gh': ['20', '50'],
            'tigo-gh': ['26', '27', '56', '57'],
        }
        for channel, codes in prefixes.items():
            if any(phone.startswith(code) for code in codes):
                _logger.info(f"Detected channel: {channel} for phone: {phone}")
                return channel
        return 'mtn-gh'

    def _initiate_hubtel_payment(self, portal, repayment, amount):
        settings = request.env['res.config.settings'].sudo().get_hubtel_credentials()
        collection_account = settings.get('collection_account')
        token = settings.get('hubtel_token')
        hubtel_receive_money_webhook = settings.get('hubtel_receive_money_webhook', '')

        if not collection_account:
            return {'success': False, 'message': 'Hubtel collection account not configured. Please contact support.'}
        if not token:
            return {'success': False, 'message': 'Hubtel token not configured. Please contact support.'}

        phone = portal.phone_no.replace(' ', '').replace('-', '')
        if phone.startswith('0'):
            phone = '233' + phone[1:]

        customer_name = repayment.customer_name.name if repayment.customer_name else 'Customer'
        client_ref = f"customer_portal_{phone}_{repayment.unique_id}"

        payload = {
            'CustomerName': customer_name,
            'CustomerMsisdn': phone,
            'CustomerEmail': '',
            'Channel': self._detect_momo_channel(phone),
            'Amount': round(float(amount), 2),
            'PrimaryCallbackUrl': str(hubtel_receive_money_webhook),
            'Description': client_ref,
            'ClientReference': str(repayment.unique_id),
        }

        _logger.info(f'Payload => {payload}')

        url = f"https://rmp.hubtel.com/merchantaccount/merchants/{collection_account}/receive/mobilemoney"

        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Basic {token}',
            'Cache-Control': 'no-cache',
        }

        body_string = json.dumps(payload, ensure_ascii=False, separators=(',', ':'))

        response = requests.post(
            url,
            data=body_string,
            timeout=30,
            headers=headers,
        )

        _logger.info("Hubtel receive-money response: %s - %s", response.status_code, response.text)

        if response.status_code in (200, 201):
            data = response.json()
            response_code = data.get('ResponseCode') or data.get('Data', {}).get('ResponseCode')
            if response_code not in ('0000', '0001'):
                error_message = data.get('Message') or data.get('Description') or data.get('Data', {}).get('Description') or 'Payment failed'
                
                # Check actual transaction status with Hubtel status check API
                _logger.info("Initial payment failed, checking transaction status with client_reference: %s", client_ref)
                status_data = self._check_hubtel_transaction_status(str(repayment.unique_id), collection_account)
                
                if status_data:
                    # Transaction actually succeeded despite initial failure response
                    _logger.info("Status check confirmed successful transaction")
                    self._create_payment_line_from_status(status_data, repayment, portal)
                    return {
                        'success': True,
                        'message': 'Payment confirmed. Your payment has been successfully processed.',
                        'transaction_id': status_data.get('Data', {}).get('TransactionId') or status_data.get('TransactionId', ''),
                    }
                
                return {
                    'success': False,
                    'message': error_message,
                }
            return {
                'success': True,
                'message': 'Payment prompt sent to your phone. Please approve the transaction on your mobile money wallet.',
                'transaction_id': data.get('Data', {}).get('TransactionId') or data.get('id', ''),
            }

        error_msg = f'Failed to initiate payment with Hubtel. Status: {response.status_code}'
        try:
            error_data = response.json()
            if error_data.get('message'):
                error_msg = error_data['message']
            elif error_data.get('status'):
                error_msg = f"{error_data.get('status')}: {error_data.get('message', 'No details')}"
            else:
                error_msg = f"Error {response.status_code}: {response.text}"
        except Exception:
            error_msg = f"Error {response.status_code}: {response.text}"
        return {'success': False, 'message': error_msg}

    def _create_payment_line_from_status(self, status_data, repayment, portal):
        """Create payment line from successful status check data."""
        data = status_data.get('Data', {}) or status_data
        
        transaction_id = data.get('TransactionId') or data.get('TransactionID', '')
        amount = data.get('Amount') or data.get('AmountPaid', 0.0)
        receipt_no = transaction_id or data.get('ExternalTransactionId') or data.get('OrderId', '')
        
        # Check if payment line already exists
        existing = request.env['repayment.payment.line'].sudo().search([
            ('repayment_id', '=', repayment.id),
            ('transaction_ref', '=', transaction_id),
        ], limit=1) if transaction_id else False
        
        if existing:
            _logger.info("Payment line already exists for transaction %s", transaction_id)
            return
        
        # Create payment line
        repayment.payment_lines.create({
            'payment_date': fields.Date.today(),
            'payment_mode': 'momo',
            'payment_amount': amount,
            'repayment_id': repayment.id,
            'receipt_no': receipt_no,
            'transaction_ref': transaction_id,
        })
        
        _logger.info("Created payment line for transaction %s with amount %s", transaction_id, amount)

    # Method to check transaction status api
    def _check_hubtel_transaction_status(self, client_reference, collection_account):
        """Check transaction status using Hubtel Transaction Status Check API."""
        settings = request.env['res.config.settings'].sudo().get_hubtel_credentials()
        token = settings.get('hubtel_token')
        
        if not token:
            _logger.error("Hubtel token not configured for status check")
            return None
        
        url = f"https://api-txnstatus.hubtel.com/transactions/{collection_account}/status"
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Basic {token}',
        }
        params = {
            'clientReference': client_reference,
        }
        
        try:
            response = requests.get(url, headers=headers, params=params, timeout=30)
            _logger.info("Hubtel status check response: %s - %s", response.status_code, response.text)
            
            if response.status_code in (200, 201):
                data = response.json()
                response_code = data.get('ResponseCode')
                status = data.get('Status', '').lower()
                
                if response_code in ('0000', '0001') or status in ('Success', 'Paid'):
                    _logger.info("Transaction status check successful for client reference: %s", client_reference)
                    return data
            return None
        except Exception as e:
            _logger.error("Error checking Hubtel transaction status: %s", str(e))
            return None

    @http.route('/customer/receipt/<int:payment_line_id>', type='http', auth='public', website=True, sitemap=False)
    def download_receipt(self, payment_line_id):
        portal = self._get_portal_for_session()
        if not portal:
            return request.redirect('/customer/portal')

        payment_line = request.env['repayment.payment.line'].sudo().browse(payment_line_id)
        if not payment_line.exists() or payment_line.repayment_id != portal.repayment_id:
            return request.not_found()

        repayment = payment_line.repayment_id
        receipt_number = payment_line.receipt_no or f"RCP-{str(payment_line.id).zfill(6)}"
        payment_mode = dict(payment_line._fields['payment_mode'].selection).get(
            payment_line.payment_mode, payment_line.payment_mode or 'N/A'
        )

        receipt_html = """
        <html>
        <head>
            <meta charset="utf-8" />
            <style>
                body { font-family: 'DejaVu Sans', Arial, sans-serif; margin: 0; padding: 40px; color: #333; }
                .header { text-align: center; border-bottom: 3px solid #6366f1; padding-bottom: 20px; margin-bottom: 30px; }
                .header h1 { color: #6366f1; margin: 0; font-size: 24px; }
                .header p { color: #666; margin: 5px 0 0; font-size: 12px; }
                .receipt-details table { width: 100%%; border-collapse: collapse; }
                .receipt-details td { padding: 8px 12px; border-bottom: 1px solid #eee; font-size: 13px; }
                .receipt-details td:first-child { font-weight: bold; color: #555; width: 40%%; }
                .receipt-details td:last-child { text-align: right; }
                .amount-row td { font-size: 15px; font-weight: bold; color: #6366f1; }
                .footer { text-align: center; margin-top: 40px; padding-top: 20px; border-top: 1px solid #ddd; font-size: 11px; color: #999; }
            </style>
        </head>
        <body>
            <div class="header">
                <h1>PAYMENT RECEIPT</h1>
                <p>Sarfosco Hire Purchase System</p>
            </div>
            <div class="receipt-details">
                <table>
                    <tr><td>Receipt Number</td><td><strong>%s</strong></td></tr>
                    <tr><td>Customer Name</td><td><strong>%s</strong></td></tr>
                    <tr><td>Phone Number</td><td><strong>%s</strong></td></tr>
                    <tr><td>Reference</td><td><strong>%s</strong></td></tr>
                    <tr><td>Transaction Ref</td><td><strong>%s</strong></td></tr>
                    <tr><td>Payment Date</td><td><strong>%s</strong></td></tr>
                    <tr><td>Payment Mode</td><td><strong>%s</strong></td></tr>
                    <tr class="amount-row"><td>Payment Amount (GHS)</td><td><strong>%s</strong></td></tr>
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
            receipt_number,
            repayment.customer_name.name or '',
            repayment.phone_no or '',
            repayment.unique_id or '',
            payment_line.transaction_ref or '',
            str(payment_line.payment_date or ''),
            payment_mode,
            f"{payment_line.payment_amount:,.2f}" if payment_line.payment_amount else '0.00',
            f"{repayment.outstanding_loan:,.2f}",
            fields.Date.today().year,
        )

        pdf_content = self._render_html_to_pdf(receipt_html)
        if not pdf_content:
            return request.make_response(receipt_html, headers=[('Content-Type', 'text/html')])

        return request.make_response(
            pdf_content,
            headers=[
                ('Content-Type', 'application/pdf'),
                ('Content-Disposition', f'attachment; filename="receipt_{payment_line.id}.pdf"'),
            ],
        )

    def _render_html_to_pdf(self, html):
        try:
            with tempfile.NamedTemporaryFile(suffix='.html', delete=False, mode='w', encoding='utf-8') as f:
                f.write(html)
                html_path = f.name

            pdf_path = html_path.replace('.html', '.pdf')
            try:
                subprocess.run(
                    ['wkhtmltopdf', '--encoding', 'utf-8', html_path, pdf_path],
                    capture_output=True, timeout=60, check=False,
                )
                if os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 0:
                    with open(pdf_path, 'rb') as f:
                        pdf_data = f.read()
                    os.unlink(html_path)
                    os.unlink(pdf_path)
                    return pdf_data
            except Exception:
                pass

            try:
                from weasyprint import HTML
                pdf_data = HTML(string=html).write_pdf()
                os.unlink(html_path)
                return pdf_data
            except Exception:
                pass

            os.unlink(html_path)
        except Exception as e:
            _logger.error("PDF generation error: %s", str(e))
        return False

    @http.route('/customer/logout', type='http', auth='public', website=True, sitemap=False)
    def logout(self, **kw):
        token = request.session.get('customer_portal_token')
        if token:
            portal = request.env['customer.portal'].sudo().search([
                ('session_token', '=', token),
            ], limit=1)
            if portal:
                portal.write({
                    'session_token': False,
                    'otp_verified': False,
                })
        request.session.pop('customer_portal_token', None)
        request.session.pop('customer_portal_phone', None)
        return request.redirect('/customer/portal')
