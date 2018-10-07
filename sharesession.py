
import bisect
import datetime
import threading
import requests
import json
import re
import xml.etree.ElementTree as ET
import glucose

# Dexcom Share API credits:
# https://gist.github.com/StephenBlackWasAlreadyTaken/adb0525344bedade1e25

class ShareSession():
    def __init__(self, location, username, password, sessionToken = None, verbose = False, callback = None):
        if location == "us":
            self.address = "share1.dexcom.com"
        elif location == "eu":
            self.address = "shareous1.dexcom.com"
        else:
            raise ValueError("Unknown location type")
        self.username = username
        self.password = password
        self.sessionId = sessionToken
        self.running = False
        self.verbose = verbose is not None
        if callback is None:
            self.callback = self.printCallback
        else:
            self.callback = callback

    def printCallback(self, gv):
        print gv

    def verboseLog(self, message):
        if self.verbose:
            print message

    def startMonitoring(self):
        if self.running:
            return

        self.lastWaitTimeForValidReading = None
        self.lastTimeSynchronization = None
        self.serverTimeDelta = None
        self.requestTimer = None
        self.lastGlucose = None
        self.gvList = []

        self.running = True

        if self.sessionId is not None:
            self.loggedIn = True
        else:
            self.loggedIn = False

        self.verboseLog("started monitoring")
        self.onTimer()

    def stopMonitoring(self):
        if not self.running:
            return
        if self.requestTimer is not None:
            self.requestTimer.cancel()
        self.running = False

    def setNextRequestTimer(self, seconds):
        if self.requestTimer is not None:
            self.requestTimer.cancel()
        self.verboseLog("next request in %d seconds" % seconds)
        self.requestTimer = threading.Timer(seconds, self.onTimer)
        self.requestTimer.start()

    def getWaitTimeForValidReading(self):
        waitTimes = [2, 2, 5, 5, 10, 10, 10, 15, 15, 20, 20, 30, 30, 60, 60, 60, 60, 120]
        lwtIndex = self.lastWaitTimeForValidReading
        if lwtIndex is None:
            lwtIndex = 0
        elif lwtIndex < len(waitTimes) - 1:
            lwtIndex += 1
        self.lastWaitTimeForValidReading = lwtIndex
        return waitTimes[lwtIndex]

    def onTimer(self):
        if not self.loggedIn:
            self.login()
        if not self.loggedIn:
            self.setNextRequestTimer(20)
            return

        self.synchronizeTime()
        self.verboseLog("Requesting glucose value")
        gv = self.getLastGlucoseValue()
        if gv is None:
            self.verboseLog("Received no value")
            self.setNextRequestTimer(self.getWaitTimeForValidReading())
        else:
            if self.lastGlucose is not None and self.lastGlucose.equals(gv):
                self.verboseLog("received the same glucose value as last time")
                self.setNextRequestTimer(self.getWaitTimeForValidReading())
            else:
                self.lastGlucose = gv
                self.callback(gv)

                self.backFillIfNeeded()

                glucoseAge = datetime.datetime.utcnow() - gv.st + self.serverTimeDelta
                self.verboseLog("received new glucose value, with an age of %s, %s" % (glucoseAge, gv))
                waitTime = 310 - glucoseAge.total_seconds()
                self.setNextRequestTimer(max(waitTime, 5))

    def synchronizeTime(self):
        if self.serverTimeDelta is not None \
                and self.lastTimeSynchronization is not None \
                and (datetime.datetime.now() - self.lastTimeSynchronization).total_seconds() < 60*60*2:
            return

        self.verboseLog("requesting server time")
        url = "https://%s/ShareWebServices/Services/General/SystemUtcTime" % self.address
        beforeReq = datetime.datetime.utcnow()
        response = requests.get(url)
        afterReq = datetime.datetime.utcnow()
        if response.status_code != 200:
            self.verboseLog("Failed to get system time from dexcom server")
            self.setNextRequestTimer(60)
            return

        root = ET.fromstring(response.text)
        for child in root:
            if child.tag[-8:] == "DateTime":
                requestTime = afterReq - beforeReq
                localAverageTime = beforeReq + (requestTime / 2)
                serverTime = datetime.datetime.strptime(child.text[:-4], "%Y-%m-%dT%H:%M:%S.%f")
                self.serverTimeDelta = localAverageTime - serverTime
                self.lastTimeSynchronization = datetime.datetime.now()
                self.verboseLog("Server date/time: %s Offset to local time: %s" % (serverTime, self.serverTimeDelta))
                break

    def backFillIfNeeded(self):
        self.gvList.append(self.lastGlucose.st)

        cutOffDate = datetime.datetime.utcnow() - datetime.timedelta(minutes=180)
        cutOffPosition = bisect.bisect_right(self.gvList, cutOffDate)
        if cutOffPosition:
            self.gvList = self.gvList[cutOffPosition:]
        else:
            self.gvList = []

        # 180 minutes => 180/5 = 36 measurements at most, 35 min. if all are received
        if len(self.gvList) >= 35:
            return

        self.verboseLog("Missing measurements within the last 3 hours, attempting to backfill..")

        gvs = self.getMultipleGlucoseValues(1440, 1024)

        if gvs is None:
            return
        self.verboseLog("Received %d glucose values from history" % len(gvs))

        newList = []

        gvCurrent = None
        if len(self.gvList) > 0:
            gvCurrentIndex = 0
            gvCurrent = self.gvList[gvCurrentIndex]

        for i in range(len(gvs)-1, 0, -1):
            gvToBackFill = gvs[i]

            while gvCurrent is not None and gvCurrent < gvToBackFill.st:
                newList.append(gvCurrent.st)
                gvCurrentIndex += 1
                if gvCurrentIndex > len(self.gvList):
                    gvCurrent = None
                    break
                gvCurrent = self.gvList[gvCurrent]

            if gvCurrent is not None and gvCurrent == gvToBackFill.st:
                gvCurrentIndex += 1
                if gvCurrentIndex <= len(self.gvList):
                    gvCurrent = self.gvList[gvCurrent]
            else:
                self.verboseLog("Backfilling glucose value: " + str(gvToBackFill))
                self.callback(gvToBackFill)

            newList.append(gvToBackFill.st)
        
        self.gvList = newList

    def login(self):
        url = "https://%s/ShareWebServices/Services/General/LoginPublisherAccountByName" % self.address
        headers = { "Accept":"application/json",
                    "Content-Type":"application/json",
                    "User-Agent":"Dexcom Share/3.0.2.11 CFNetwork/711.2.23 Darwin/14.0.0" }
        payload = { "accountName":self.username,
                 "password":self.password,
                 "applicationId":"d8665ade-9673-4e27-9ff6-92db4ce13d13" }
         
        self.verboseLog("Attempting to login")
        result = requests.post(url, data = json.dumps(payload) , headers = headers)
        if result.status_code != 200:
            self.verboseLog("Login failed, Http result code %d text: %s" % (result.status_code, result.text))
            self.loggedIn = False
        else:
            self.sessionId = result.text[1:-1]
            self.verboseLog("Login successful, session id: %s" % self.sessionId)
            self.loggedIn = True

    def getMultipleGlucoseValues(self, minutes, maxCount):
        if not self.loggedIn:
            self.login()
        url = "https://%s/ShareWebServices/Services/Publisher/ReadPublisherLatestGlucoseValues" % self.address
        url += "?sessionId=%s&minutes=%d&maxCount=%d" % (self.sessionId, minutes, maxCount)
        headers = { "Accept":"application/json",
                    "User-Agent":"Dexcom Share/3.0.2.11 CFNetwork/711.2.23 Darwin/14.0.0" }
         
        result = requests.post(url, headers = headers)
        gvs = []
        if result.status_code == 200:
            for jsonResult in result.json():
                gvs.append(glucose.GlucoseValue(jsonResult))
            return gvs
        else:
            return None

    def getLastGlucoseValue(self):
        r = self.getMultipleGlucoseValues(1440, 1)
        if r is not None:
            return r[0]
        return None

