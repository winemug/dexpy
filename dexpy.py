#!/usr/bin/python3
import time
import signal

import simplejson as json
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
        self.logger = logging.getLogger('DEXPY')

        self.args = args
        self.exit_event = threading.Event()
        self.message_published_event = threading.Event()

        self.initialize_db()
        self.mqtt_client = None
        if args.MQTT_SERVER is not None:
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
        if args.INFLUXDB_SERVER is not None:
            self.influx_client = InfluxDBClient(args.INFLUXDB_SERVER, args.INFLUXDB_PORT, args.INFLUXDB_USERNAME,
                                                args.INFLUXDB_PASSWORD, args.INFLUXDB_DATABASE,
                                                ssl=args.INFLUXDB_SSL, verify_ssl=args.INFLUXDB_SSL_VERIFY)

        self.callback_queue = Queue()
        self.glucose_values = []
        self.mqtt_pending = {}
        self.influx_pending = []
        self.ns_pending = []

        self.ns_session = None
        if args.NIGHTSCOUT_URL is not None:
            self.ns_session = requests.Session()

        self.dexcom_share_session = None
        if args.DEXCOM_SHARE_SERVER is not None:
            self.logger.info("starting dexcom share session")
            self.dexcom_share_session = DexcomShareSession(args.DEXCOM_SHARE_SERVER,
                                                           args.DEXCOM_SHARE_USERNAME,
                                                           args.DEXCOM_SHARE_PASSWORD,
                                                           self.glucoseValueCallback)

        self.dexcom_receiver_session = None
        if args.USB_RECEIVER is not None and args.USB_RECEIVER:
            self.dexcom_receiver_session = DexcomReceiverSession(self.glucoseValueCallback)

        for sig in ('HUP', 'INT'):
            signal.signal(getattr(signal, 'SIG' + sig), lambda _0, _1: self.exit_event.set())

    def run(self):
        if self.mqtt_client is not None:
            self.logger.info("starting mqtt service connection")
            self.mqtt_client.reconnect_delay_set(min_delay=15, max_delay=120)
            self.mqtt_client.connect_async(args.MQTT_SERVER, port=args.MQTT_PORT, keepalive=60)
            self.mqtt_client.retry_first_connection = True
            self.mqtt_client.loop_start()

        if self.dexcom_share_session is not None:
            self.logger.info("starting monitoring dexcom share server")
            self.dexcom_share_session.start_monitoring()

        if self.dexcom_receiver_session is not None:
            self.logger.info("starting usb receiver service")
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
            self.logger.info("stopping dexcom receiver service")
            self.dexcom_receiver_session.stopMonitoring()

        if self.dexcom_share_session is not None:
            self.logger.info("stopping listening on dexcom share server")
            self.dexcom_share_session.stop_monitoring()

        if self.mqtt_client is not None:
            self.logger.info("stopping mqtt client")
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()

        if self.influx_client is not None:
            self.logger.info("closing influxdb client")
            self.influx_client.close()

        if self.ns_session is not None:
            self.logger.info("closing nightscout session")
            self.ns_session.close()

    def on_mqtt_connect(self, client, userdata, flags, rc):
        self.logger.info("Connected to mqtt server with result code " + str(rc))
        self.logger.debug("Pending %d messages in local queue" % len(self.mqtt_pending))

    def on_mqtt_disconnect(self, client, userdata, rc):
        self.logger.info("Disconnected from mqtt with result code " + str(rc))
        self.logger.debug("Pending %d messages in local queue" % len(self.mqtt_pending))

    def on_mqtt_message_receive(self, client, userdata, msg):
        self.logger.info("mqtt message received: " + msg)

    def on_mqtt_message_publish(self, client, userdata, msg_id):
        self.logger.info("mqtt message published: " + str(msg_id))
        if msg_id in self.mqtt_pending:
            self.mqtt_pending.pop(msg_id)
        else:
            self.logger.debug("unknown message id: " + str(msg_id))
        self.logger.debug("Pending %d messages in local queue" % len(self.mqtt_pending))

    def glucoseValueCallback(self, gvs):
        for gv in gvs:
            self.callback_queue.put(gv)

    def queueHandlerLoop(self):
        while not self.exit_event.wait(timeout=0.200):
            gvs = []
            while True:
                try:
                    gv = self.callback_queue.get(block=True, timeout=5)
                    gvs.append(gv)
                except Empty:
                    if len(gvs) > 0:
                        self.processGlucoseValues(gvs)
                        gvs = []

    def processGlucoseValues(self, gvs):
        new_values = []
        for gv in gvs:
            new_val = True
            for gv_check in self.glucose_values:
                if gv_check == gv:
                    new_val = False
                    break
            if new_val:
                new_values.append(gv)
                self.logger.info(f"New gv: {gv}")

        if self.mqtt_client is not None:
            for gv in new_values:
                msg = "%d|%s|%s" % (gv.st, gv.trend, gv.value)
                x, mid = self.mqtt_client.publish(args.MQTT_TOPIC, payload=msg, retain=last_gv, qos=1)
                self.mqtt_pending[mid] = gv
                self.logger.debug("publish to mqtt requested with message id: " + str(mid))

        if self.influx_client is not None:
            for gv in new_values:
                point = {
                    "measurement": self.args.INFLUXDB_MEASUREMENT,
                    "tags": {"source": "dexpy"},
                    "time": dt.datetime.utcfromtimestamp(gv.st).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "fields": {"cbg": float(gv.value), "direction": int(gv.trend)}
                }
                self.influx_pending.append(point)
            try:
                if self.influx_client.write_points(self.influx_pending):
                    self.influx_pending = []
            except Exception as ex:
                self.logger.error("Error writing to influxdb", exc_info=ex)

        if self.ns_session is not None:
            apiUrl = args.NIGHTSCOUT_URL
            if apiUrl[-1] != "/":
                apiUrl += "/"
            apiUrl += "api/v1/entries/"
            headers = {"Content-Type": "application/json"}
            if args.NIGHTSCOUT_SECRET:
                headers["api-secret"] = args.NIGHTSCOUT_SECRET
            if args.NIGHTSCOUT_TOKEN:
                apiUrl += "?token=" + args.NIGHTSCOUT_TOKEN

            for gv in new_values:
                payload = {"sgv": gv.value, "type": "sgv", "direction": gv.trendAsString(), "date": gv.st * 1000}
                self.ns_pending.append(json.dumps(payload))
            try:
                for pendingEntry in self.ns_pending:
                    self.ns_session.post(apiUrl, headers=headers, data=pendingEntry)
                    self.ns_pending.remove(pendingEntry)
            except:
                self.logger.error("Error writing to nightscout")

        for gv in new_values:
            i = bisect.bisect_right(self.glucose_values, gv)
            self.glucose_values.insert(i + 1, gv)

        if len(self.glucose_values) > 4096:
            self.glucose_values = self.glucose_values[4096-len(self.glucose_values):]

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
    logger = logging.getLogger('DEXPY')
    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    parser = argparse.ArgumentParser()
    parser.add_argument("--CONFIGURATION", required=False, default=None, nargs="?")
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
    parser.add_argument("--INFLUXDB-SSL", required=False, default=False, nargs="?")
    parser.add_argument("--INFLUXDB-SSL-VERIFY", required=False, default=False, nargs="?")
    parser.add_argument("--INFLUXDB-USERNAME", required=False, default="", nargs="?")
    parser.add_argument("--INFLUXDB-PASSWORD", required=False, default="", nargs="?")
    parser.add_argument("--INFLUXDB-DATABASE", required=False, default="", nargs="?")
    parser.add_argument("--INFLUXDB-MEASUREMENT", required=False, default="", nargs="?")
    parser.add_argument("--NIGHTSCOUT-URL", required=False, default=None, nargs="?")
    parser.add_argument("--NIGHTSCOUT-SECRET", required=False, default=None, nargs="?")
    parser.add_argument("--NIGHTSCOUT-TOKEN", required=False, default=None, nargs="?")
    parser.add_argument("--DB-PATH", required=False, default="dexpy.db", nargs="?")
    parser.add_argument("--USB-RECEIVER", required=False, default=True, nargs="?")
    args = parser.parse_args()

    if args.CONFIGURATION is not None:
        with open(args.CONFIGURATION, 'r') as stream:
            js = json.load(stream)

        for js_arg in js:
            args.__dict__[js_arg] = js[js_arg]

    dexpy = DexPy(args)
    dexpy.run()
