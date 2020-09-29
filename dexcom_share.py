import logging
import bisect
import datetime
import threading
import requests
import json
import xml.etree.ElementTree as ET
from glucose import GlucoseValue

# Dexcom Share API credits:
# https://gist.github.com/StephenBlackWasAlreadyTaken/adb0525344bedade1e25

class DexcomShareSession():
    def __init__(self, location, username, password, callback):
        self.logger = logging.getLogger('DEXPY')

        if location == "us":
            self.address = "share2.dexcom.com"
        elif location == "eu":
            self.address = "shareous1.dexcom.com"
        else:
            raise ValueError("Unknown location type")
        self.username = username
        self.password = password
        self.sessionId = None
        self.requestTimer = None
        self.callback = callback
        self.lock = threading.RLock()
        self.initialBackfillExecuted = False

    def startMonitoring(self):
        if self.requestTimer is not None:
            return

        self.lastWaitTimeForValidReading = None
        self.lastTimeSynchronization = None
        self.serverTimeDelta = None
        self.lastGlucose = None
        self.gvList = []

        if self.sessionId is not None:
            self.loggedIn = True
        else:
            self.loggedIn = False

        self.session = requests.Session()
        self.logger.info("started dexcom share client")
        self.setNextRequestTimer()

    def stopMonitoring(self):
        with self.lock:
            if self.requestTimer is not None:
                self.requestTimer.cancel()
                self.requestTimer = None

    def setNextRequestTimer(self, seconds = 0.1):
        if self.requestTimer is not None:
            self.requestTimer.cancel()
        self.logger.debug("next request in %d seconds" % seconds)
        self.requestTimer = threading.Timer(seconds, self.onTimer)
        self.requestTimer.start()

    def getWaitTimeForValidReading(self):
        waitTimes = [2, 2, 5, 5, 10, 10, 30, 30, 60]
        lwtIndex = self.lastWaitTimeForValidReading
        if lwtIndex is None:
            lwtIndex = 0
        elif lwtIndex < len(waitTimes) - 1:
            lwtIndex += 1
        else:
            self.loggedIn = False
            lwtIndex = 0
        self.lastWaitTimeForValidReading = lwtIndex
        return waitTimes[lwtIndex]

    def onTimer(self):
        with self.lock:
            if not self.loggedIn:
                self.login()
            if not self.loggedIn:
                self.setNextRequestTimer(20)
                return

            self.synchronizeTime()

            self.logger.debug("Requesting glucose value")
            gv = self.getLastGlucoseValue()
            if gv is None:
                self.logger.warning("Received no glucose value")
                self.setNextRequestTimer(self.getWaitTimeForValidReading())
            else:
                if self.lastGlucose is not None and self.lastGlucose.equals(gv):
                    self.logger.debug("received the same glucose value as last time")
                    self.setNextRequestTimer(self.getWaitTimeForValidReading())
                else:
                    self.lastGlucose = gv
                    self.callback(gv)

                    self.backFillIfNeeded()

                    glucoseAge = datetime.datetime.utcnow() - gv.st + self.serverTimeDelta
                    self.logger.info("received new glucose value, with an age of %s, %s" % (glucoseAge, gv))
                    waitTime = 310 - glucoseAge.total_seconds()
                    self.lastWaitTimeForValidReading = None
                    self.setNextRequestTimer(max(waitTime, 5))

    def synchronizeTime(self):
        if self.serverTimeDelta is not None \
                and self.lastTimeSynchronization is not None \
                and (datetime.datetime.utcnow() - self.lastTimeSynchronization).total_seconds() < 60*60*2:
            return

        self.logger.debug("requesting server time")
        failed = False
        try:
            url = "https://%s/ShareWebServices/Services/General/SystemUtcTime" % self.address
            response = self.session.get(url)
        except:
            failed = True

        if failed or response.status_code != 200:
            self.logger.warning("Failed to get system time from dexcom server")
            self.setNextRequestTimer(60)
            return

        root = ET.fromstring(response.text)
        for child in root:
            if child.tag[-8:] == "DateTime":
                serverTime = datetime.datetime.strptime(child.text[:-4], "%Y-%m-%dT%H:%M:%S.%f")
                utcTime = datetime.datetime.utcnow()
                diffSeconds = (utcTime - serverTime).total_seconds()
                #roundedDifference = int(round(diffSeconds / 1800)*1800)
                self.serverTimeDelta = datetime.timedelta(seconds = diffSeconds)
                self.lastTimeSynchronization = datetime.datetime.utcnow()
                self.logger.debug("Server date/time: %s Offset to local time: %s" % (serverTime, self.serverTimeDelta))
                break

    def backFillIfNeeded(self):
        self.gvList.append(self.lastGlucose.st)

        cutOffDate = datetime.datetime.utcnow() - datetime.timedelta(hours = 3)
        cutOffPosition = bisect.bisect_right(self.gvList, cutOffDate)
        if cutOffPosition:
            self.gvList = self.gvList[cutOffPosition:]
        else:
            self.gvList = []

        if self.initialBackfillExecuted and len(self.gvList) >= 36:
            return

        if self.initialBackfillExecuted:
            self.logger.info("Missing measurements within the last 3 hours, attempting to backfill..")
            gvs = self.getMultipleGlucoseValues(180, 40)
        else:
            self.logger.info("Executing initial backfill with the last 24 hours of data..")
            gvs = self.getMultipleGlucoseValues(1440, 300)

        if gvs is None:
            return

        self.initialBackfillExecuted = True
        self.logger.debug("Received %d glucose values from history" % len(gvs))

        newList = []

        gvCurrent = None
        if len(self.gvList) > 0:
            gvCurrentIndex = 0
            gvCurrent = self.gvList[gvCurrentIndex]

        for i in range(len(gvs)-1, 0, -1):
            gvToBackFill = gvs[i]

            while gvCurrent is not None and gvCurrent < gvToBackFill.st:
                newList.append(gvCurrent)
                gvCurrentIndex += 1
                if gvCurrentIndex > len(self.gvList):
                    gvCurrent = None
                    break
                gvCurrent = self.gvList[gvCurrentIndex]

            if gvCurrent is not None and gvCurrent == gvToBackFill.st:
                gvCurrentIndex += 1
                if gvCurrentIndex <= len(self.gvList):
                    gvCurrent = self.gvList[gvCurrentIndex]
            else:
                self.logger.debug("Backfilling glucose value: " + str(gvToBackFill))
                self.callback(gvToBackFill)

            newList.append(gvToBackFill.st)

        self.gvList = newList

    def login(self):
        url = "https://%s/ShareWebServices/Services/General/LoginPublisherAccountByName" % self.address
        headers = { "Accept": "application/json",
                    "Content-Type": "application/json",
                    "User-Agent": "Dexcom Share/3.0.2.11 CFNetwork/711.2.23 Darwin/14.0.0"}
        payload = { "accountName": self.username,
                 "password": self.password,
                 "applicationId": "d8665ade-9673-4e27-9ff6-92db4ce13d13" }

        self.logger.debug("Attempting to login")
        failed = False
        try:
            result = self.session.post(url, data = json.dumps(payload) , headers = headers)
        except:
            failed = True
        if failed or result.status_code != 200:
            self.logger.error("Login failed")
            self.loggedIn = False
        else:
            self.sessionId = result.text[1:-1]
            self.logger.info("Login successful, session id: %s" % self.sessionId)
            self.loggedIn = True

    def getMultipleGlucoseValues(self, minutes, maxCount):
        if not self.loggedIn:
            self.login()
        url = "https://%s/ShareWebServices/Services/Publisher/ReadPublisherLatestGlucoseValues" % self.address
        url += "?sessionId=%s&minutes=%d&maxCount=%d" % (self.sessionId, minutes, maxCount)
        headers = { "Accept":"application/json",
                    "User-Agent":"Dexcom Share/3.0.2.11 CFNetwork/711.2.23 Darwin/14.0.0" }
        failed = False
        try:
            result = self.session.post(url, headers = headers)
        except:
            failed = True
        gvs = []
        if not failed and result.status_code == 200:
            for jsonResult in result.json():
                gvs.append(GlucoseValue.fromJson(jsonResult, self.serverTimeDelta))
            return gvs
        else:
            return None

    def getLastGlucoseValue(self):
        r = self.getMultipleGlucoseValues(1440, 1)
        if r is not None and len(r) > 0:
            return r[0]
        return None

