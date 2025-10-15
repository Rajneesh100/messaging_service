import time
from kafka import KafkaProducer

TOPIC_NAME = "whatsapp_messages"
# Choose an appropriate SASL mechanism, for instance:
SASL_MECHANISM = 'SCRAM-SHA-256'

producer = KafkaProducer(
    bootstrap_servers=f"notification-service-streaming-with-fcm.k.aivencloud.com:10158",
    sasl_mechanism = SASL_MECHANISM,
    sasl_plain_username = "avnadmin",
    sasl_plain_password = "password",
    security_protocol="SASL_SSL",
    ssl_cafile="ca.pem",
)

for i in range(100):
    message = f"Hello from Python using SASL {i + 1}!"
    producer.send(TOPIC_NAME, message.encode('utf-8'))
    print(f"Message sent: {message}")
    time.sleep(1)

producer.close()