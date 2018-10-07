#!/usr/bin/python

import paho.mqtt.client as mqttc
from paho.mqtt.client import MQTTv311
import argparse
import threading
import ssl
from datetime import datetime
import argparse
from dexpy_receiver import ReceiverSession
import readdata
from sets import Set

def verboseLog(message):
    if args.verbose:
        print message

def on_mqtt_connect(client, userdata, flags, rc):
    global shareSession
    global latestGv
    latestGv = None
    verboseLog("Connected to mqtt server with result code "+str(rc))

def on_mqtt_disconnect(client, userdata, rc):
    verboseLog("Disconnected from mqtt with result code "+str(rc))

def on_mqtt_message_receive(client, userdata, msg):
    verboseLog("mqtt message received: " + msg)

def on_mqtt_message_publish(client, userdata, mid):
    verboseLog("mqtt message sent: " + mid)

sentDates = Set()
def glucoseValueCallback(dt, arrow, glucose):
    global mqttClient
    global sentDates

    ts = int((dt - datetime.utcfromtimestamp(0)).total_seconds())

    if ts not in sentDates:
        msg = "%d|%d|%f" % (ts, arrow, glucose)
        print msg
        verboseLog("publishing glucose value to mqtt server")
        mqttClient.publish(args.mqtt_topic, payload = msg, retain = True, qos = 2)
        sentDates.add(ts)


def main():
    global args
    global receiverSession
    global mqttClient

    parser = argparse.ArgumentParser()
    parser.add_argument("-ms", "--mqtt-server", required = True)
    parser.add_argument("-msp", "--mqtt-server-port", default = 1883, required = False)
    parser.add_argument("-mca", "--mqtt-ca", required = False)
    parser.add_argument("-mci", "--mqtt-client-id", required = True)
    parser.add_argument("-mt", "--mqtt-topic", required = True)
    parser.add_argument("-v", "--verbose", required = False, default = False, action='store_true')

    args = parser.parse_args()

    mqttClient = mqttc.Client(client_id=args.mqtt_client_id, clean_session=True, protocol=MQTTv311, transport="tcp")

    if args.mqtt_ca is not None:
        mqttClient.tls_set(ca_certs=args.mqtt_ca, certfile=None,
                                    keyfile=None, cert_reqs=ssl.CERT_REQUIRED,
                                    tls_version=ssl.PROTOCOL_TLSv1_2, ciphers=None)
        mqttClient.tls_insecure_set(True)

    mqttClient.on_connect = on_mqtt_connect
    mqttClient.on_disconnect = on_mqtt_disconnect
    mqttClient.on_message = on_mqtt_message_receive
    mqttClient.on_publish = on_mqtt_message_publish

    verboseLog("connecting to mqtt service")
    mqttClient.connect(args.mqtt_server, port=args.mqtt_server_port)
    mqttClient.loop_start()

    verboseLog("starting dexcom session")
    receiverSession = ReceiverSession(glucoseValueCallback)

    receiverSession.startMonitoring()

    try:
        raw_input()
    except KeyboardInterrupt:
        pass

    receiverSession.stopMonitoring()

    mqttClient.loop_stop()
    mqttClient.disconnect()

if __name__ == '__main__':
    main()