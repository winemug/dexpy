#!/usr/bin/python2

import paho.mqtt.client as mqttc
from paho.mqtt.client import MQTTv311
import argparse
import threading
import ssl
from datetime import datetime
import time

def verboseLog(message):
    if args.DEXPY_VERBOSE:
        print message

def on_mqtt_connect(client, userdata, flags, rc):
    verboseLog("Connected to mqtt server with result code "+str(rc))

def on_mqtt_disconnect(client, userdata, rc):
    verboseLog("Disconnected from mqtt with result code "+str(rc))

def on_mqtt_message_receive(client, userdata, msg):
    verboseLog("mqtt message received: " + msg)

def on_mqtt_message_publish(client, userdata, mid):
    verboseLog("mqtt message sent: " + mid)

def glucoseValueCallback(gv):
    # global mqttClient
    # global shareSession

    # ts = int((gv.st - datetime.utcfromtimestamp(0)).total_seconds())
    # msg = "%d|%s|%s" % (ts, gv.trend, gv.value)

    # latestGvDate = None
    # if shareSession.gvList is not None and len(shareSession.gvList) > 0:
    #     latestGvDate = shareSession.gvList[-1]

    # if latestGvDate is None or latestGvDate < gv.st:
    #     verboseLog("publishing glucose value to mqtt server")
    #     mqttClient.publish(args.mqtt_topic, payload = msg, retain = True, qos = 2)
    # else:
    #     verboseLog("publishing historical value to mqtt server")
    #     mqttClient.publish(args.mqtt_topic, payload = msg, retain = False, qos = 1)
    pass

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
    parser.add_argument("-verbose", "--DEXPY-VERBOSE", required=False)

    args = parser.parse_args()

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

        verboseLog("connecting to mqtt service")
        mqttClient.connect(args.MQTT_SERVER, port=args.MQTT_PORT)
        mqttClient.loop_start()

    if args.DEXCOM_SHARE_LISTEN or args.DEXCOM_SHARE_UPDATE:
        verboseLog("starting dexcom session")

    if args.DEXCOM_RECEIVER_LISTEN:
        verboseLog("connecting to receiver")

    verboseLog("press any key to stop")
    try:
        raw_input()
    except KeyboardInterrupt:
        pass

    if args.MQTT_ENABLED:
        mqttClient.loop_stop()
        mqttClient.disconnect()

if __name__ == '__main__':
    main()