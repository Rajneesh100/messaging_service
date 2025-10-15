from kafka import KafkaConsumer
from tio_agent import LlamaSession
import json
import requests

TOPIC_NAME = "whatsapp_messages"
SASL_MECHANISM = 'SCRAM-SHA-256'

TWILIO_ACCOUNT_SID = "sid"
TWILIO_AUTH_TOKEN = "token"
TWILIO_WHATSAPP_NUMBER = "whatsapp:+phone"

# Global map to store user sessions: from_number -> LlamaSession
user_sessions = {}

def get_session(from_number):
    """Get or create a session for a specific user"""
    if from_number not in user_sessions:
        print(f"Creating new session for {from_number}")
        user_sessions[from_number] = LlamaSession()
    return user_sessions[from_number]

consumer = KafkaConsumer(
    TOPIC_NAME,
    auto_offset_reset="latest",
    bootstrap_servers=f"notification-service-streaming-with-fcm.k.aivencloud.com:10158",
    client_id = "CONSUMER_CLIENT_ID",
    group_id = "CONSUMER_GROUP_ID",
    sasl_mechanism = SASL_MECHANISM,
    sasl_plain_username = "avnadmin",
    sasl_plain_password = "password",
    security_protocol = "SASL_SSL",
    ssl_cafile = "ca.pem"
)

def send_whatsapp_message(to_number, message_body):
    """Send WhatsApp message via Twilio API"""
    url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Messages.json"
    
    data = {
        'To': to_number,
        'From': TWILIO_WHATSAPP_NUMBER,
        'Body': message_body
    }
    
    response = requests.post(
        url,
        data=data,
        auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    )
    
    if response.status_code == 201:
        print(f"Message sent successfully to {to_number}")
    else:
        print(f"Failed to send message: {response.status_code} - {response.text}")
    
    return response

print("Consumer started, waiting for messages...")

while True:
    for message in consumer.poll().values():
        raw_message = message[0].value.decode('utf-8')
        print(f"Got message using SASL: {raw_message}")
        
        try:
            msg_data = json.loads(raw_message)
            
            from_number = msg_data.get('From')
            user_message = msg_data.get('Body')
            
            if not from_number or not user_message:
                print("Missing From or Body in message")
                continue
            
            print(f"Processing message from {from_number}: {user_message}")
            
            # Get or create session for this user
            user_session = get_session(from_number)
            
            # Get AI response
            ai_response = user_session.chat(user_message)
            print(f"AI Response: {ai_response}")
            
            # Send response back to user
            send_whatsapp_message(from_number, ai_response)
            
        except json.JSONDecodeError as e:
            print(f"Failed to parse message JSON: {e}")
        except Exception as e:
            print(f"Error processing message: {e}")



