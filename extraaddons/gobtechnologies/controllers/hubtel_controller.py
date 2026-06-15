from odoo import http, fields
from odoo.http import request
import json
from werkzeug.wrappers import Response
import logging
import datetime

_logger = logging.getLogger(__name__)


class HubtelPaymentController(http.Controller):
    @http.route('/shop/hubtel_payment', type='http', auth='public', methods=['POST'], website=True, csrf=False)
    def hubtel_payment(self, **kwargs):
        order_id = kwargs.get("order_id")
        sale_order = request.env['sale.order'].sudo().browse(int(order_id))
        if not sale_order.exists():
            return http.Response('Order not found', content_type="text/plain")
        order_total = sale_order.amount_total
        return http.Response(str(order_total), content_type="text/plain")

    @http.route(['/web/hook/d69a6f81-e899-4509-85dd-8655a1543259'], type='json', auth="public", methods=['POST'], csrf=False)
    def save_payment_notifications(self, **kwargs):
        _logger.info("Webhook controller listener called")
        try:
            payload_raw = request.httprequest.get_data().decode('utf-8')
            payload = {}
            if payload_raw:
                try:
                    payload = json.loads(payload_raw)
                except Exception:
                    _logger.warning("Invalid JSON payload: %s", payload_raw)

            _logger.info("==== Webhook Received ====")
            _logger.info("Raw Payload: %s", payload)

            data = payload.get('Data', {}) or {}
            client_reference = (
                data.get('ClientReference')
                or payload.get('ClientReference')
                or ''
            )

            if client_reference.startswith('customer_portal_'):
                return self._process_customer_portal_payment(payload, data, client_reference)

            today = datetime.date.today()
            vals = {
                "invoice_id": data.get('InvoiceId', ''),
                "receipt_no": data.get('ReceiptNumber', ''),
                "amount_paid": data.get('AmountPaid', 0.0),
                "description": data.get('Description', ''),
                "payment_method": data.get('PaymentMethod', ''),
                "payment_channel": data.get('PaymentChannel', ''),
                "payee_phone_no": data.get('PayeePhoneNumber', ''),
                "payment_detail_id": data.get('PaymentDetailId', ''),
                "status": payload.get('Status', ''),
                "response_code": payload.get('ResponseCode', ''),
                "payment_date": today,
            }

            record = request.env['payment.notifications'].sudo().create(vals)
            _logger.info("Webhook data saved with ID: %s", record.id)

            return request.make_json_response({
                "status": "success",
                "message": "Webhook processed",
                "record_id": record.id,
            })

        except Exception as e:
            _logger.error("Error processing webhook: %s", str(e), exc_info=True)
            return request.make_json_response({
                "status": "error",
                "message": str(e),
            }, status=500)

    def _process_customer_portal_payment(self, payload, data, client_reference):
        status = payload.get('Status', '')
        response_code = payload.get('ResponseCode', '')

        if status.lower() not in ('success', 'paid') and response_code not in ('0000', '0001'):
            _logger.warning("Customer portal payment not successful: %s / %s", status, response_code)
            return request.make_json_response({
                "status": "ignored",
                "message": "Payment not successful",
            })

        webhook_vals = {
            'message': payload.get('Message', status),
            'amount': data.get('Amount', 0.0),
            'charges': data.get('Charges', 0.0),
            'amount_after_charges': data.get('AmountAfterCharges', 0.0),
            'description': data.get('Description', ''),
            'client_reference': client_reference,
            'transaction_id': data.get('TransactionId', '') or data.get('TransactionID', ''),
            'external_transaction_id': data.get('ExternalTransactionId', ''),
            'amount_charged': data.get('AmountCharged', data.get('Amount', 0.0)),
            'order_id': data.get('OrderId', ''),
            'payment_date': data.get('PaymentDate', str(fields.Date.today())),
        }

        record = request.env['hubtel.webhook'].sudo().create(webhook_vals)
        _logger.info("Customer portal webhook saved with ID: %s", record.id)

        return request.make_json_response({
            "status": "success",
            "message": "Customer portal payment processed",
            "record_id": record.id,
        })
