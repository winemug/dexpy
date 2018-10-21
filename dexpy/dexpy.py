#!/usr/bin/python2

import paho.mqtt.client as mqttc
from paho.mqtt.client import MQTTv311
import argparse
import threading
import ssl
from datetime import datetime, time, timedelta
import time
from dexcom_share import DexcomShareSession
from dexcom_receiver import DexcomReceiverSession
import logging
import bisect
import sys

gvDates = []
mqttClient = None
mqttLocalQueue = {}

def on_mqtt_connect(client, userdata, flags, rc):
    logging.info("Connected to mqtt server with result code "+str(rc))
    logging.debug("Pending %d messages in local queue" % len(mqttLocalQueue))

def on_mqtt_disconnect(client, userdata, rc):
    logging.info("Disconnected from mqtt with result code "+str(rc))
    logging.debug("Pending %d messages in local queue" % len(mqttLocalQueue))

def on_mqtt_message_receive(client, userdata, msg):
    logging.info("mqtt message received: " + msg)

def on_mqtt_message_publish(client, userdata, mid):
    logging.info("mqtt message published: " + str(mid))
    if mqttLocalQueue.has_key(mid):
        mqttLocalQueue.pop(mid)
    else:
        logging.debug("unknown message id: " + str(mid))
    logging.debug("Pending %d messages in local queue" % len(mqttLocalQueue))

def glucoseValueCallback(gv):
    global mqttClient
    global gvDates

    logging.debug("Received glucose value: %s" % gv)

    shouldRetain = False
    i = bisect.bisect_right(gvDates, gv.st)
    if i > 0 and gvDates[i-1] == gv.st:
        logging.debug("Received value is a duplicate, skipping.")
        return
    elif i == len(gvDates):
        gvDates.append(gv.st)
        shouldRetain = True
    else:
        newList = gvDates[0:i]
        newList.append(gv.st)
        newList.extend(gvDates[i:])
        gvDates = newList

    if len(gvDates) > 100:
        cutOffDate = datetime.utcnow() - timedelta(hours = 3)
        cutOffPosition = bisect.bisect_left(gvDates, cutOffDate)
        if cutOffPosition:
            gvDates = gvDates[cutOffPosition:]
        else:
            gvDates = []

    if args.MQTT_ENABLED:
        ts = int((gv.st - datetime.utcfromtimestamp(0)).total_seconds())
        msg = "%d|%s|%s" % (ts, gv.trend, gv.value)
        x, mid = mqttClient.publish(args.MQTT_TOPIC, payload = msg, retain = shouldRetain, qos = 2)
        logging.debug("publish to mqtt requested with message id: " + str(mid))
        mqttLocalQueue[mid] = gv
        logging.debug("Pending %d messages in local queue" % len(mqttLocalQueue))

def main():
    global args
    global mqttClient

    parser = argparse.ArgumentParser()
    parser.add_argument("-dsl", "--DEXCOM-SHARE-LISTEN", required=False) 
    parser.add_argument("-dsu", "--DEXCOM-SHARE-UPDATE", required=False) 
    parser.add_argument("-dssl", "--DEXCOM-SHARE-SERVER-LOCATION", required=False) 
    parser.add_argument("-dsun", "--DEXCOM-SHARE-USERNAME", required=False) 
    parser.add_argument("-dsp", "--DEXCOM-SHARE-PASSWORD", required=False) 
    parser.add_argument("-drl", "--DEXCOM-RECEIVER-LISTEN", required=False) 
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

    dexcomReceiverSession = None
    if args.DEXCOM_RECEIVER_LISTEN:
        logging.info("connecting to usb receiver")
        dexcomReceiverSession = DexcomReceiverSession(glucoseValueCallback)
        dexcomReceiverSession.startMonitoring()

    exitEvent.wait()

    if args.DEXCOM_RECEIVER_LISTEN:
        logging.info("stopping listening to dexcom receiver")
        dexcomReceiverSession.stopMonitoring()

    if args.DEXCOM_SHARE_LISTEN:
        logging.info("stopping listening on dexcom share server")
        dexcomShareSession.stopMonitoring()

    if args.MQTT_ENABLED:
        mqttClient.loop_stop()
        mqttClient.disconnect()

exitEvent = threading.Event()

def signalHandler(signo, _frame):
    exitEvent.set()

if __name__ == '__main__':
    import signal
    for sig in ('TERM', 'HUP', 'INT'):
        signal.signal(getattr(signal, 'SIG'+sig), signalHandler)
    main()