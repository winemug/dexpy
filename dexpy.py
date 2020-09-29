#!/usr/bin/python3
import time
import signal

import json
import sqlite3
from queue import Queue, Empty

import paho.mqtt.client as mqttc
from paho.mqtt.client import MQTTv311
from influxdb import InfluxDBClient
import argparse
import threading
import ssl
import datetime as dt
from dexcom_share import DexcomShareSession
from dexcom_receiver import DexcomReceiverSession
import logging
import bisect
from glucose import GlucoseValue
import requests


class DexPy:
    def __init__(self, args):
        logging.basicConfig(level=args.LOG_LEVEL)
        self.logger = logging.getLogger('DEXPY')
        self.args = args
        self.exit_event = threading.Event()
        self.finish_up_event = threading.Event()
        self.message_published_event = threading.Event()

        self.initialize_db()
        self.mqtt_client = None
        if args.MQTT_SERVER:
            self.mqtt_client = mqttc.Client(client_id=args.MQTT_CLIENTID, clean_session=True, protocol=MQTTv311,
                                      transport="tcp")

            if args.MQTT_SSL != "":
                self.mqtt_client.tls_set(certfile=None,
                                   keyfile=None, cert_reqs=ssl.CERT_REQUIRED,
                                   tls_version=ssl.PROTOCOL_TLSv1_2, ciphers=None)
                self.mqtt_client.tls_insecure_set(True)

            self.mqtt_client.on_connect = self.on_mqtt_connect
            self.mqtt_client.on_disconnect = self.on_mqtt_disconnect
            self.mqtt_client.on_message = self.on_mqtt_message_receive
            self.mqtt_client.on_publish = self.on_mqtt_message_publish

        self.influx_client = None
        if args.INFLUXDB_SERVER:
            self.influx_client = InfluxDBClient(args.INFLUXDB_SERVER, args.INFLUXDB_PORT, args.INFLUXDB_USERNAME,
                                          args.INFLUXDB_PASSWORD, args.INFLUXDB_DATABASE, ssl=args.INFLUXDB_SSL)

        self.callback_queue = Queue()
        self.glucose_values = []
        self.mqtt_pending = {}
        self.influx_pending = []
        self.ns_pending = []

        if args.NIGHTSCOUT_URL:
            self.ns_session = requests.Session()

        self.dexcom_share_session = None
        if args.DEXCOM_SHARE_SERVER:
            logging.info("starting dexcom share session")
            self.dexcom_share_session = DexcomShareSession(args.DEXCOM_SHARE_SERVER, \
                                                    args.DEXCOM_SHARE_USERNAME, \
                                                    args.DEXCOM_SHARE_PASSWORD, \
                                                    self.glucoseValueCallback)

        self.dexcom_receiver_session = None

        for sig in ('TERM', 'HUP', 'INT'):
            signal.signal(getattr(signal, 'SIG' + sig), lambda _0, _1: self.exit_event.set())

    def run(self):
        if self.mqtt_client is not None:
            logging.info("starting mqtt service connection")
            self.mqtt_client.reconnect_delay_set(min_delay=15, max_delay=120)
            self.mqtt_client.connect_async(args.MQTT_SERVER, port=args.MQTT_PORT, keepalive=60)
            self.mqtt_client.retry_first_connection = True
            self.mqtt_client.loop_start()

        if self.dexcom_share_session is not None:
            logging.info("starting monitoring dexcom share server")
            self.dexcom_share_session.startMonitoring()

        if self.dexcom_receiver_session is not None:
            logging.info("starting usb receiver service")
            self.dexcom_receiver_session.startMonitoring()

        queue_thread = threading.Thread(target=self.queueHandlerLoop)
        queue_thread.start()

        try:
            while not self.exit_event.wait(timeout=1000):
                pass
        except KeyboardInterrupt:
            pass

        self.exit_event.clear()
        if self.dexcom_receiver_session is not None:
            logging.info("stopping dexcom receiver service")
            self.dexcom_receiver_session.stopMonitoring()

        if self.dexcom_share_session is not None:
            logging.info("stopping listening on dexcom share server")
            self.dexcom_share_session.stopMonitoring()

        if self.mqtt_client is not None:
            logging.info("stopping mqtt client")
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()

        if self.influx_client is not None:
            logging.info("closing influxdb client")
            self.influx_client.close()

        if self.ns_session is not None:
            logging.info("closing nightscout session")
            self.ns_session.close()

    def on_mqtt_connect(self, client, userdata, flags, rc):
        logging.info("Connected to mqtt server with result code " + str(rc))
        logging.debug("Pending %d messages in local queue" % len(self.mqtt_pending))

    def on_mqtt_disconnect(self, client, userdata, rc):
        logging.info("Disconnected from mqtt with result code " + str(rc))
        logging.debug("Pending %d messages in local queue" % len(self.mqtt_pending))

    def on_mqtt_message_receive(self, client, userdata, msg):
        logging.info("mqtt message received: " + msg)

    def on_mqtt_message_publish(self, client, userdata, msg_id):
        logging.info("mqtt message published: " + str(msg_id))
        if msg_id in self.mqtt_pending:
            self.mqtt_pending.pop(msg_id)
        else:
            logging.debug("unknown message id: " + str(msg_id))
        logging.debug("Pending %d messages in local queue" % len(self.mqtt_pending))

    def glucoseValueCallback(self, gv):
        self.callback_queue.put(gv)

    def queueHandlerLoop(self):
        while not self.finish_up_event.wait(timeout=0.200):
            while True:
                try:
                    gv = self.callback_queue.get(block=True, timeout=0.5)
                    self.processGlucoseValue(gv)
                except Empty:
                    break

        while True:
            try:
                gv = self.callback_queue.get(block=False)
                self.processGlucoseValue(gv)
            except Empty:
                break

    def processGlucoseValue(self, gv):
        logging.debug("Processing glucose value: %s" % gv)
        shouldRetain = False

        i = bisect.bisect_right(self.glucose_values, gv)
        if i > 0 and self.glucose_values[i - 1] == gv:
            logging.debug("Received value is a duplicate, skipping.")
            return
        elif i == len(self.glucose_values):
            self.glucose_values.append(gv)
            shouldRetain = True
        else:
            newList = self.glucose_values[0:i]
            newList.append(gv)
            newList.extend(self.glucose_values[i:])
            self.glucose_values = newList

        if len(self.glucose_values) > 200:
            cutoff_ts = time.time() - 3 * 60 * 60
            cutoff_gv = GlucoseValue(None, None, cutoff_ts, 0, 0)
            i_cutoff = bisect.bisect_left(self.glucose_values, cutoff_ts)
            if i_cutoff:
                self.glucose_values = self.glucose_values[i_cutoff:]
            else:
                self.glucose_values = []
        if self.mqtt_client is not None:
            msg = "%d|%s|%s" % (gv.st, gv.trend, gv.value)
            x, mid = self.mqtt_client.publish(args.MQTT_TOPIC, payload=msg, retain=shouldRetain, qos=2)
            self.mqtt_pending[mid] = gv
            logging.debug("publish to mqtt requested with message id: " + str(mid))

        if self.influx_client is not None:
            point = {
                "measurement": "measurements",
                "tags": {"device": "dexcomg6", "source": "dexpy", "unit": "mg/dL"},
                "time": dt.datetime.utcfromtimestamp(gv.st).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "fields": {"cbg": float(gv.value), "direction": int(gv.trend)}
            }
            self.influx_pending.append(point)
            try:
                self.influx_client.write_points(self.pendingInfluxPoints)
                self.influx_pending = []
            except:
                logging.error("Error writing to influxdb")

        if self.ns_session is not None:
            apiUrl = args.NIGHTSCOUT_URL
            if apiUrl[-1] != "/":
                apiUrl += "/"
            apiUrl += "api/v1/entries/"
            payload = {"sgv": gv.value, "type": "sgv", "direction": gv.trendString, "date": gv.st * 1000}
            headers = {"Content-Type": "application/json"}
            if args.NIGHTSCOUT_SECRET:
                headers["api-secret"] = args.NIGHTSCOUT_SECRET
            if args.NIGHTSCOUT_TOKEN:
                apiUrl += "?token=" + args.NIGHTSCOUT_TOKEN

            self.ns_pending.append(json.dumps(payload))
            try:
                for pendingEntry in self.ns_pending:
                    self.ns_session.post(apiUrl, headers=headers, data=pendingEntry)
                    self.ns_pending.remove(pendingEntry)
            except:
                logging.error("Error writing to nightscout")
                return

    def initialize_db(self):
        try:
            with sqlite3.connect(self.args.DB_PATH) as conn:
                sql = """ CREATE TABLE IF NOT EXISTS gv (
                          ts REAL,
                          gv REAL,
                          trend TEXT
                          ) """
                conn.execute(sql)

                sql = """ CREATE INDEX "idx_ts" ON "gv" ("ts");"""
                try:
                    conn.execute(sql)
                except:
                    pass
        except Exception as e:
            pass



if __name__ == '__main__':
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
    parser.add_argument("--NIGHTSCOUT-SECRET", required=False, default=None, nargs="?")
    parser.add_argument("--NIGHTSCOUT-TOKEN", required=False, default=None, nargs="?")
    parser.add_argument("--LOG-LEVEL", required=False, default="INFO", nargs="?")
    parser.add_argument("--DB-PATH", required=False, default="dexpy.db", nargs="?")
    args = parser.parse_args()
