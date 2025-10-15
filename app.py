from flask import Flask, request, abort
from twilio.twiml.messaging_response import MessagingResponse
from twilio.request_validator import RequestValidator
from functools import wraps
from kafka import KafkaProducer
import json
import os

app = Flask(__name__)

TWILIO_AUTH_TOKEN = "token"
TOPIC_NAME = "whatsapp_messages"
SASL_MECHANISM = 'SCRAM-SHA-256'

# Initialize Kafka Producer
producer = KafkaProducer(
    bootstrap_servers="notification-service-streaming-with-fcm.k.aivencloud.com:10158",
    sasl_mechanism=SASL_MECHANISM,
    sasl_plain_username="avnadmin",
    sasl_plain_password="password",
    security_protocol="SASL_SSL",
    ssl_cafile="ca.pem",
)

def validate_twilio_request(f):
    """Validates that incoming requests genuinely originated from Twilio"""
    @wraps(f)
    def decorated_function(*args, **kwargs):

        validator = RequestValidator(TWILIO_AUTH_TOKEN)

        request_valid = validator.validate(
            request.url,
            request.form,
            request.headers.get('X-TWILIO-SIGNATURE', ''))
 
        if request_valid:
            return f(*args, **kwargs)
        else:
            return abort(403)
    return decorated_function

@app.route("/whatsapp-message", methods=['POST'])
# @validate_twilio_request
def whatsapp_webhook():
    """Receive incoming WhatsApp messages and push to Kafka."""
    try:
        # Extract message data from Twilio webhook
        message_data = {
            'From': request.form.get('From'),
            'To': request.form.get('To'),
            'Body': request.form.get('Body'),
            'MessageSid': request.form.get('MessageSid'),
            'NumMedia': request.form.get('NumMedia'),
            'ProfileName': request.form.get('ProfileName'),
            'WaId': request.form.get('WaId'),
        }
        
        # Push the message to Kafka
        producer.send(TOPIC_NAME, json.dumps(message_data).encode('utf-8'))
        producer.flush()  # Ensure message is sent
        
        print(f"Message pushed to Kafka: {message_data}")
        
        resp = MessagingResponse()
        return str(resp)
        
    except Exception as e:
        print(f"Error processing message: {str(e)}")
        resp = MessagingResponse()
        return str(resp), 500


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)


    