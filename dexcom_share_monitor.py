#!/usr/bin/python

import argparse
import signal
import sys
import time
import threading
import requests
import json
import datetime
import re
import xml.etree.ElementTree as ET
import pytz

# Dexcom Share API credits:
# https://gist.github.com/StephenBlackWasAlreadyTaken/adb0525344bedade1e25

def parseDateTime(val):
    res = re.search("Date\((\d*)", val)
    epoch = float(res.group(1)) / 1000
    return datetime.datetime.utcfromtimestamp(epoch)

class DexcomGlucoseValue():
    def __init__(self, jsonResponse):
        self.dt = parseDateTime(jsonResponse["DT"])
        self.wt = parseDateTime(jsonResponse["WT"])
        self.st = parseDateTime(jsonResponse["ST"])
        self.value = float(jsonResponse["Value"])
        self.trend = int(jsonResponse["Trend"])

    def equals(self, other):
        return self.dt == other.dt and self.wt == other.wt and self.st == other.st and self.value == other.value and self.trend == other.trend

    def __str__(self):
        return "DT: %s WT: %s ST: %s Trend: %d Value: %f" % (self.dt, self.wt, self.st, self.trend, self.value)

class DexcomShareSession():
    def __init__(self, address, username, password, sessionToken = None, verbose = None):
        self.address = address
        self.username = username
        self.password = password
        self.sessionId = sessionToken
        self.running = False
        self.verbose = verbose is not None

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
                print gv
                glucoseAge = datetime.datetime.utcnow() - gv.st + self.serverTimeDelta
                self.verboseLog("received new glucose value, with an age of %s" % glucoseAge)
                waitTime = 300 - glucoseAge.total_seconds()
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

    def getLastGlucoseValue(self):
        if not self.loggedIn:
            self.login()

        url = "https://%s/ShareWebServices/Services/Publisher/ReadPublisherLatestGlucoseValues" % self.address
        url += "?sessionId=%s&minutes=1440&maxCount=1" % self.sessionId
        headers = { "Accept":"application/json",
                    "User-Agent":"Dexcom Share/3.0.2.11 CFNetwork/711.2.23 Darwin/14.0.0" }
         
        result = requests.post(url, headers = headers)
        if result.status_code == 200:
            jsonResult = result.json()[0]
            return DexcomGlucoseValue(jsonResult)
        else:
            return None

def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("location", choices=[ "eu", "us" ])
    parser.add_argument("-u", "--username", required = True)
    parser.add_argument("-p", "--password", required = True)
    parser.add_argument("-i", "--sessionid", required = False)
    parser.add_argument("-v", "--verbose", required = False, action='store_true')

    args = parser.parse_args()

    if args.location == "us":
        address = "share1.dexcom.com"
    elif args.location == "eu":
        address = "shareous1.dexcom.com"
    else:
        raise ValueError("Unknown location type")

    session = DexcomShareSession(address, args.username, args.password, args.sessionid, args.verbose)
    session.startMonitoring()
    try:
        raw_input()
    except KeyboardInterrupt:
        pass
    session.stopMonitoring()

if __name__ == '__main__':
    main()
