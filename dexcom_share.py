import logging
import threading
import requests
import json
from glucose import GlucoseValue
import time


# Dexcom Share API credits:
# https://gist.github.com/StephenBlackWasAlreadyTaken/adb0525344bedade1e25

class DexcomShareSession():
    def __init__(self, location, username, password, callback):
        self.logger = logging.getLogger('DEXPY')
        self.callback = callback

        if location == "us":
            self.address = "share2.dexcom.com"
        elif location == "eu":
            self.address = "shareous1.dexcom.com"
        else:
            raise ValueError("Unknown location type")

        self.username = username
        self.password = password
        self.session = None
        self.dexcom_session_id = None

        self.lock = threading.RLock()
        self.timer = None
        self.initial_backfill_executed = False
        self.gvs = []

    def start_monitoring(self):
        self.session = requests.Session()
        self.logger.info("started dexcom share client")
        self.on_timer()

    def stop_monitoring(self):
        with self.lock:
            if self.timer is not None:
                self.timer.cancel()
                self.timer = None

        self.session.close()

    def on_timer(self):
        with self.lock:
            request_wait = self.perform_request()
            self.logger.debug("next request in %d seconds" % request_wait)
            self.timer = threading.Timer(request_wait, self.on_timer)
            self.timer.setDaemon(True)
            self.timer.start()

    def perform_request(self) -> float:
        if self.dexcom_session_id is None:
            self.login()

        if self.dexcom_session_id is None:
            return 30

        self.logger.debug("Requesting glucose value")
        gv = self.get_last_gv()
        if gv is None:
            self.logger.warning("Received no glucose value")
        else:
            if len(self.gvs) == 0 or self.gvs[-1].__ne__(gv):
                self.gvs.append(gv)
                self.callback([gv])
        self.backfill()
        if gv is None:
            return 60

        time_since = time.time() - gv.st
        g6_phase = time_since % 300
        if time_since < 330:
            return 330 - time_since
        elif g6_phase < 90:
            return 15
        else:
            return 330 - g6_phase

    def backfill(self):
        cut_off = time.time() - 3 * 60 * 60 - 5 * 60
        self.gvs = [gv for gv in self.gvs if gv.st > cut_off]

        if self.initial_backfill_executed and len(self.gvs) >= 36:
            return

        if self.initial_backfill_executed:
            self.logger.info("Missing measurements within the last 3 hours, attempting to backfill..")
            gvs = self.get_gvs(180, 40)
        else:
            self.logger.info("Executing initial backfill with the last 24 hours of data..")
            gvs = self.get_gvs(1440, 300)

        if gvs is None:
            self.logger.warning("No data received")
            return

        self.initial_backfill_executed = True
        self.logger.debug("Received %d glucose values from history" % len(gvs))
        self.callback(gvs)
        self.gvs = gvs

    def login(self):
        url = "https://%s/ShareWebServices/Services/General/LoginPublisherAccountByName" % self.address
        headers = {"Accept": "application/json",
                   "Content-Type": "application/json",
                   "User-Agent": "Dexcom Share/3.0.2.11 CFNetwork/711.2.23 Darwin/14.0.0"}
        payload = {"accountName": self.username,
                   "password": self.password,
                   "applicationId": "d8665ade-9673-4e27-9ff6-92db4ce13d13"}

        self.logger.debug("Attempting to login")
        result = None
        try:
            result = self.session.post(url, data=json.dumps(payload), headers=headers)
        except Exception as e:
            self.logger.error(e)

        if result is None or result.status_code != 200:
            self.recreate_session()
            self.logger.error("Login failed")
        else:
            self.dexcom_session_id = result.text[1:-1]
            self.logger.info("Login successful, session id: %s" % self.dexcom_session_id)

    def recreate_session(self):
        try:
            self.session.close()
        except Exception as ex:
            self.logger.warning("Error while closing session", exc_info=ex)
        self.session = requests.Session()

    def get_gvs(self, minutes, maxCount):
        url = "https://%s/ShareWebServices/Services/Publisher/ReadPublisherLatestGlucoseValues" % self.address
        url += "?sessionId=%s&minutes=%d&maxCount=%d" % (self.dexcom_session_id, minutes, maxCount)
        headers = {"Accept": "application/json",
                   "User-Agent": "Dexcom Share/3.0.2.11 CFNetwork/711.2.23 Darwin/14.0.0"}
        result = None
        try:
            result = self.session.post(url, headers=headers)
        except Exception as ex:
            self.logger.error(exc_info=ex)

        gvs = []
        if result is not None and result.status_code == 200:
            for jsonResult in result.json():
                gvs.append(GlucoseValue.from_json(jsonResult))
            return gvs
        else:
            self.recreate_session()
            return None

    def get_last_gv(self):
        r = self.get_gvs(1440, 1)
        if r is not None and len(r) > 0:
            return r[0]
        return None
