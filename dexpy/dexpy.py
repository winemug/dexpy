#!/usr/bin/python2

import paho.mqtt.client as mqttc
from paho.mqtt.client import MQTTv311
import argparse
import threading
import ssl
from datetime import datetime
import time
from dexcom_share import DexcomShareSession
import logging

def on_mqtt_connect(client, userdata, flags, rc):
    logging.info("Connected to mqtt server with result code "+str(rc))

def on_mqtt_disconnect(client, userdata, rc):
    logging.info("Disconnected from mqtt with result code "+str(rc))

def on_mqtt_message_receive(client, userdata, msg):
    logging.info("mqtt message received: " + msg)

def on_mqtt_message_publish(client, userdata, mid):
    logging.info("mqtt message sent: " + mid)

def glucoseValueCallback(gv):
    logging.debug("Received glucose value: " + str(gv))

def main():
    global args

    parser = argparse.ArgumentParser()
    parser.add_argument("-dsl", "--DEXCOM-SHARE-LISTEN", required=False) 
    parser.add_argument("-dsu", "--DEXCOM-SHARE-UPDATE", required=False) 
    parser.add_argument("-dssl", "--DEXCOM-SHARE-SERVER-LOCATION", required=False) 
    parser.add_argument("-dsun", "--DEXCOM-SHARE-USERNAME", required=False) 
    parser.add_argument("-dsp", "--DEXCOM-SHARE-PASSWORD", required=False) 
    parser.add_argument("-dsbf", "--DEXCOM-SHARE-BACKFILL", required=False) 
    parser.add_argument("-drl", "--DEXCOM-RECEIVER-LISTEN", required=False) 
    parser.add_argument("-drbf", "--DEXCOM-RECEIVER-BACKFILL", required=False) 
    parser.add_argument("-me", "--MQTT-ENABLED", required=False) 
    parser.add_argument("-ms", "--MQTT-SERVER", required=False) 
    parser.add_argument("-mp", "--MQTT-PORT", required=False) 
    parser.add_argument("-mci", "--MQTT-CLIENT-ID", required=False) 
    parser.add_argument("-mt", "--MQTT-TOPIC", required=False) 
    parser.add_argument("-mssl", "--MQTT-SSL", required=False) 
    parser.add_argument("-msslca", "--MQTT-SSL-CA", required=False)
    parser.add_argument("-ll", "--DEXPY-LOG-LEVEL", required=False)

    args = parser.parse_args()

    logging.basicConfig(level=args.DEXPY_LOG_LEVEL)

    mqttClient = None
    if args.MQTT_ENABLED:
        mqttClient = mqttc.Client(client_id=args.MQTT_CLIENT_ID, clean_session=True, protocol=MQTTv311, transport="tcp")

        if args.MQTT_SSL:
            mqttClient.tls_set(ca_certs=args.MQTT_SSL_CA, certfile=None,
                                        keyfile=None, cert_reqs=ssl.CERT_REQUIRED,
                                        tls_version=ssl.PROTOCOL_TLSv1_2, ciphers=None)
            mqttClient.tls_insecure_set(True)

        mqttClient.on_connect = on_mqtt_connect
        mqttClient.on_disconnect = on_mqtt_disconnect
        mqttClient.on_message = on_mqtt_message_receive
        mqttClient.on_publish = on_mqtt_message_publish

        logging.info("connecting to mqtt service")
        mqttClient.connect(args.MQTT_SERVER, port=args.MQTT_PORT)
        mqttClient.loop_start()

    dexcomShareSession = None
    if args.DEXCOM_SHARE_LISTEN or args.DEXCOM_SHARE_UPDATE:
        logging.info("starting dexcom share session")
        dexcomShareSession = DexcomShareSession(args.DEXCOM_SHARE_SERVER_LOCATION, \
                                                args.DEXCOM_SHARE_USERNAME, \
                                                args.DEXCOM_SHARE_PASSWORD, \
                                                glucoseValueCallback)
        
        if args.DEXCOM_SHARE_LISTEN:
            logging.info("starting monitoring the share server")
            dexcomShareSession.startMonitoring()

    if args.DEXCOM_RECEIVER_LISTEN:
        logging.info("connecting to usb receiver")

    print("press any key to stop")
    try:
        raw_input()
    except KeyboardInterrupt:
        pass

    if args.DEXCOM_RECEIVER_LISTEN:
        logging.info("stopping listening to dexcom receiver")

    if args.DEXCOM_SHARE_LISTEN:
        logging.info("stopping listening on dexcom share server")
        dexcomShareSession.stopMonitoring()

    if args.MQTT_ENABLED:
        mqttClient.loop_stop()
        mqttClient.disconnect()

if __name__ == '__main__':
    main()