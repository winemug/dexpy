#!/usr/bin/python

import sharesession
import glucose
import paho.mqtt.client as mqttc
from paho.mqtt.client import MQTTv311
import argparse
import threading
import ssl

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

def glucoseValueCallback(gv):
    global mqttClient
    global shareSession
    msg = "%s|%s|%s" % (gv.st, gv.trend, gv.value)

    latestGvDate = None
    if shareSession.gvList is not None and len(shareSession.gvList) > 0:
        latestGvDate = shareSession.gvList[-1]

    if latestGvDate is None or latestGvDate < gv.st:
        verboseLog("publishing glucose value to mqtt server")
        mqttClient.publish(args.mqtt_topic, payload = msg, retain = True, qos = 2)
    else:
        verboseLog("publishing historical value to mqtt server")
        mqttClient.publish(args.mqtt_topic, payload = msg, retain = False, qos = 1)

def main():
    global args
    global mqttClient
    global shareSession

    parser = argparse.ArgumentParser()
    parser.add_argument("-ms", "--mqtt-server", required = True)
    parser.add_argument("-msp", "--mqtt-server-port", default = 1883, required = False)
    parser.add_argument("-mca", "--mqtt-ca", required = False)
    parser.add_argument("-mci", "--mqtt-client-id", required = True)
    parser.add_argument("-mt", "--mqtt-topic", required = True)
    parser.add_argument("-dsl", "--dexcom-server-location", choices=[ "eu", "us" ], required=True)
    parser.add_argument("-du", "--dexcom-username", required = True)
    parser.add_argument("-dp", "--dexcom-password", required = True)
    parser.add_argument("-dsi", "--dexcom-session-id", required = False)
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
    shareSession = sharesession.ShareSession(args.dexcom_server_location, args.dexcom_username, args.dexcom_password, args.dexcom_session_id, args.verbose, glucoseValueCallback)
    shareSession.startMonitoring()

    try:
        raw_input()
    except KeyboardInterrupt:
        pass

    shareSession.stopMonitoring()

    mqttClient.loop_stop()
    mqttClient.disconnect()

if __name__ == '__main__':
    main()