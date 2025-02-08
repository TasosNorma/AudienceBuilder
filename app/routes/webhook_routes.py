from flask import Blueprint, request, jsonify
from ..core.whatsapp import WhatsappHandler
from ..core.response_handling import ResponseHandler
import logging
from app.extensions import csrf

webhook_bp = Blueprint('webhook', __name__)
responsehandler = ResponseHandler()

@webhook_bp.route('/twilio/webhook', methods=['POST'])
@csrf.exempt
def twilio_webhook():
    try:
        logging.info("Received webhook data:")
        logging.info(f"Form data: {request.form}")

        if request.form.get('MessageStatus'):
            logging.info(f"Received status update: {request.form.get('MessageStatus')}")
            return jsonify({'status': 'success'}), 200

        if request.form.get('ButtonText') == "Draft":
            original_message_sid = request.form.get('OriginalRepliedMessageSid')
            message_sid = request.form.get('Message_sid')
            response_body = request.form.get('Body')
            responsehandler.handle_response(original_message_sid, response_body.lower().strip(),message_sid=message_sid)
            logging.info(f"handle_repsonse() function initiated")

        elif request.form.get('ButtonText') == "Ignore Draft":
            original_message_sid = request.form.get('OriginalRepliedMessageSid')
            response_body = request.form.get('Body')
            logging.info(f"handle_repsonse() function initiated")
            responsehandler.handle_response(original_message_sid, response_body.lower().strip())

        elif request.form.get('ButtonText') == "Ignore":
            original_message_sid = request.form.get('OriginalRepliedMessageSid')
            response_body = request.form.get('Body')
            responsehandler.handle_response(original_message_sid, response_body.lower().strip())
            logging.info(f"handle_repsonse() function initiated")

        elif request.form.get('ButtonText') == "Post":
            original_message_sid = request.form.get('OriginalRepliedMessageSid')
            response_body = request.form.get('Body')
            responsehandler.handle_response(original_message_sid, response_body.lower().strip())
            logging.info(f"handle_repsonse() function initiated")
        
        if not original_message_sid or not response_body:
            logging.error("Missing required parameters")
            return jsonify({'status': 'error', 'message': 'Missing required parameters'}), 400
        
        return jsonify({'status': 'success'}), 200

    except Exception as e:
        logging.error(f"Error processing webhook: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500