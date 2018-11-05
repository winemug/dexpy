#!/usr/bin/python2

import paho.mqtt.client as mqttc
from paho.mqtt.client import MQTTv311
from influxdb import InfluxDBClient
from Queue import Queue, Empty
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
from glucose import GlucoseValue

exitEvent = threading.Event()
finishUpEvent = threading.Event()
messagePublishedEvent = threading.Event()
mqttClient = None

callbackQueue = Queue()
mqttLocalTracking = {}
sortedGvs = []

def on_mqtt_connect(client, userdata, flags, rc):
    logging.info("Connected to mqtt server with result code "+str(rc))
    logging.debug("Pending %d messages in local queue" % len(mqttLocalTracking))

def on_mqtt_disconnect(client, userdata, rc):
    logging.info("Disconnected from mqtt with result code "+str(rc))
    logging.debug("Pending %d messages in local queue" % len(mqttLocalTracking))

def on_mqtt_message_receive(client, userdata, msg):
    logging.info("mqtt message received: " + msg)

def on_mqtt_message_publish(client, userdata, mid):
    logging.info("mqtt message published: " + str(mid))
    if mqttLocalTracking.has_key(mid):
        mqttLocalTracking.pop(mid)
    else:
        logging.debug("unknown message id: " + str(mid))
    logging.debug("Pending %d messages in local queue" % len(mqttLocalTracking))

def glucoseValueCallback(gv):
    global callbackQueue
    callbackQueue.put(gv)

def queueHandlerLoop():
    global mqttClient
    global callbackQueue
    global finishUpEvent

    while not finishUpEvent.wait(timeout=0.050):
        try:
            gv = callbackQueue.get(block = True, timeout=1)
            processGlucoseValue(gv)
        except Empty:
            pass

    while True:
        try:
            gv = callbackQueue.get(block = False)
            processGlucoseValue(gv)
        except Empty:
            break
       
def processGlucoseValue(gv):
    global sortedGvs

    logging.debug("Processing glucose value: %s" % gv)
    shouldRetain = False

    i = bisect.bisect_right(sortedGvs, gv)
    if i > 0 and sortedGvs[i-1] == gv:
        logging.debug("Received value is a duplicate, skipping.")
        return
    elif i == len(sortedGvs):
        sortedGvs.append(gv)
        shouldRetain = True
    else:
        newList = sortedGvs[0:i]
        newList.append(gv)
        newList.extend(sortedGvs[i:])
        sortedGvs = newList

    if len(sortedGvs) > 200:
        cutOffDate = datetime.utcnow() - timedelta(hours = 3)
        cutOffGv = GlucoseValue(None, None, cutOffDate, 0, 0)
        cutOffPosition = bisect.bisect_left(sortedGvs, cutOffGv)
        if cutOffPosition:
            sortedGvs = sortedGvs[cutOffPosition:]
        else:
            sortedGvs = []

    if args.MQTT_SERVER:
        ts = int((gv.st - datetime.utcfromtimestamp(0)).total_seconds())
        msg = "%d|%s|%s" % (ts, gv.trend, gv.value)
        x, mid = mqttClient.publish(args.MQTT_TOPIC, payload = msg, retain = shouldRetain, qos = 2)
        logging.debug("publish to mqtt requested with message id: " + str(mid))
        mqttLocalTracking[mid] = gv

    if args.INFLUXDB_SERVER:
        client = InfluxDBClient(args.INFLUXDB_SERVER, args.INFLUXDB_PORT, args.INFLUXDB_USERNAME, args.INFLUXDB_PASSWORD, args.INFLUXDB_DATABASE, ssl = args.INFLUXDB_SSL)

        point = {
                    "measurement": "measurements",
                    "tags": { "device": "dexcomg6", "source": "dexpy", "unit": "mg/dL" },
                    "time": gv.st.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "fields": { "cbg": float(gv.value), "direction": int(gv.trend) }
                }
        client.write_points([point])
        pass
    
    if args.NIGHTSCOUT_URL:
        pass

def main():
    global args
    global mqttClient
    global finishUpEvent
    global mqttLocalTracking

    parser = argparse.ArgumentParser()
    parser.add_argument("--DEXCOM-SHARE-SERVER", required=False, default=None, nargs="?")
    parser.add_argument("--DEXCOM-SHARE-USERNAME", required=False, default="", nargs="?") 
    parser.add_argument("--DEXCOM-SHARE-PASSWORD", required=False, default="", nargs="?") 
    parser.add_argument("--MQTT-SERVER", required=False, default=None, nargs="?") 
    parser.add_argument("--MQTT-PORT", required=False, default="1881", nargs="?") 
    parser.add_argument("--MQTT-SSL", required=False, default="", nargs="?") 
    parser.add_argument("--MQTT-CLIENTID", required=False, default="dexpy", nargs="?") 
    parser.add_argument("--MQTT-TOPIC", required=False, default="cgm", nargs="?")
    parser.add_argument("--INFLUXDB-SERVER", required=False, default=None, nargs="?")
    parser.add_argument("--INFLUXDB-PORT", required=False, default="8086", nargs="?")
    parser.add_argument("--INFLUXDB-SSL", required=False, default="", nargs="?")
    parser.add_argument("--INFLUXDB-USERNAME", required=False, default="", nargs="?")
    parser.add_argument("--INFLUXDB-PASSWORD", required=False, default="", nargs="?")
    parser.add_argument("--INFLUXDB-DATABASE", required=False, default="", nargs="?")
    parser.add_argument("--NIGHTSCOUT-URL", required=False, default=None, nargs="?")
    parser.add_argument("--NIGHTSCOUT-SECRET", required=False, default="", nargs="?")
    parser.add_argument("--NIGHTSCOUT-TOKEN", required=False, default="", nargs="?")
    parser.add_argument("--LOG-LEVEL", required=False, default="INFO", nargs="?")

    args = parser.parse_args()

    logging.basicConfig(level=args.LOG_LEVEL)

    if args.MQTT_SERVER:
        mqttClient = mqttc.Client(client_id=args.MQTT_CLIENTID, clean_session=True, protocol=MQTTv311, transport="tcp")

        if args.MQTT_SSL != "":
            mqttClient.tls_set(certfile=None,
                                        keyfile=None, cert_reqs=ssl.CERT_REQUIRED,
                                        tls_version=ssl.PROTOCOL_TLSv1_2, ciphers=None)
            mqttClient.tls_insecure_set(True)

        mqttClient.on_connect = on_mqtt_connect
        mqttClient.on_disconnect = on_mqtt_disconnect
        mqttClient.on_message = on_mqtt_message_receive
        mqttClient.on_publish = on_mqtt_message_publish

        logging.info("connecting to mqtt service")
        mqttClient.reconnect_delay_set(min_delay=15, max_delay=120)
        mqttClient.connect_async(args.MQTT_SERVER, port=args.MQTT_PORT, keepalive=60)
        mqttClient.retry_first_connection=True
        mqttClient.loop_start()

    dexcomShareSession = None
    if args.DEXCOM_SHARE_SERVER:
        logging.info("starting dexcom share session")
        dexcomShareSession = DexcomShareSession(args.DEXCOM_SHARE_SERVER, \
                                                args.DEXCOM_SHARE_USERNAME, \
                                                args.DEXCOM_SHARE_PASSWORD, \
                                                glucoseValueCallback)
        
        logging.info("starting monitoring the share server")
        dexcomShareSession.startMonitoring()

    logging.info("looking for and connecting to usb receiver")
    dexcomReceiverSession = DexcomReceiverSession(glucoseValueCallback)
    dexcomReceiverSession.startMonitoring()

    queueHandler = threading.Thread(target = queueHandlerLoop)
    queueHandler.start()

    try:
        while not exitEvent.wait(timeout = 1000):
            pass
    except KeyboardInterrupt:
        pass

    exitEvent.clear()

    logging.info("stopping listening to dexcom receiver")
    dexcomReceiverSession.stopMonitoring()

    if args.DEXCOM_SHARE_SERVER:
        logging.info("stopping listening on dexcom share server")
        dexcomShareSession.stopMonitoring()

    logging.info("Finishing up queued work")
    finishUpEvent.set()
    queueHandler.join()

    if args.MQTT_SERVER:
        pendingMessages = len(mqttLocalTracking)
        if pendingMessages > 0:
            logging.info("Pending %d messages in local queue, waiting for all to be published" % pendingMessages)
            logging.info("Press CTRL + C to abort")
            try:
                mqttClient.loop_stop()
                while pendingMessages > 0:
                    mqttClient.loop(timeout=0.5)
                    pendingMessages = len(mqttLocalTracking)
                    if exitEvent.wait(timeout=0.1):
                        logging.info("Aborted")
                        break
            except KeyboardInterrupt:
                logging.info("Aborted")
                pass
        logging.info("Disconnecting from mqtt")
        mqttClient.loop_stop()
        mqttClient.disconnect()

def signalHandler(signo, _frame):
    exitEvent.set()

if __name__ == '__main__':
    import signal
    for sig in ('TERM', 'HUP', 'INT'):
        signal.signal(getattr(signal, 'SIG'+sig), signalHandler)
    main()
