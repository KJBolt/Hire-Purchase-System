from odoo import http
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


    # Save invoice callback on webhook trigger
    # Make sure the InvoiceId and phone no is an actual record in the database else the data wont be saved
    @http.route(['/web/hook/d69a6f81-e899-4509-85dd-8655a1543259'], type='json', auth="public", methods=['POST'], csrf=False)
    def save_payment_notifications(self, **kwargs):
        _logger.info("Webhook controller listener called")
        try:
            # Raw payload
            payload_raw = request.httprequest.get_data().decode('utf-8')
            payload = {}
            if payload_raw:
                try:
                    payload = json.loads(payload_raw)
                except Exception:
                    _logger.warning("Invalid JSON payload: %s", payload_raw)

            _logger.info("==== Webhook Received ====")
            _logger.info("Raw Payload: %s", payload)

            # Extract data
            today = datetime.date.today()
            data = payload.get('Data', {}) or {}

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
                "payment_date": today
            }

            # Save into DB (payment.notifications model)
            record = request.env['payment.notifications'].sudo().create(vals)
            _logger.info("Webhook data saved with ID: %s", record.id)

            return request.make_json_response({
                "status": "success",
                "message": "Webhook processed",
                "record_id": record.id
            })

        except Exception as e:
            _logger.error("Error processing webhook: %s", str(e), exc_info=True)
            return request.make_json_response({
                "status": "error",
                "message": str(e),
            }, status=500)


