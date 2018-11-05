
from usbreceiver.database_records import constants
from usbreceiver.readdata import Dexcom
from datetime import datetime, timedelta
from glucose import GlucoseValue
import threading
import logging
import bisect

class DexcomReceiverSession():
    def __init__(self, callback):
        self.callback = callback
        self.device = None
        self.timer = None
        self.lock = threading.RLock()

    def startMonitoring(self):
        self.lastGVReceived = None
        self.onTimer()

    def onTimer(self):
        with self.lock:
            if not self.ensureUsbConnected():
                self.setTimer(15)
            elif self.readGlucoseValues():
                self.setTimer(30)
            else:
                self.setTimer(10)

    def ensureUsbConnected(self):
        try:
            if self.device is None:
                port = Dexcom.FindDevice()
                if port is None:
                    logging.warn("Dexcom receiver not found")
                    return False
                else:
                    self.device = Dexcom(port)
            self.systemTimeOffset = self.getUtcOffsetForSystemTime()
            return True
        except Exception as e:
            logging.warn("Error reading from usb device\n" + str(e))
            self.device = None
            self.systemTimeOffset = None
            return False

    def setTimer(self, seconds):
        self.timer = threading.Timer(seconds, self.onTimer)
        logging.debug("timer set to %d seconds" % seconds)
        self.timer.start()

    def stopMonitoring(self):
        with self.lock:
            self.timer.cancel()

    def readGlucoseValues(self):
        try:
            cutOffDate = datetime.utcnow() - timedelta(hours = 3)
            records = self.device.iter_records('EGV_DATA')
            newValueReceived = False

            for rec in records:
                if not rec.display_only:
                    gv = self.recordToGV(rec)
                    if self.lastGVReceived is None or self.lastGVReceived.st != gv.st:
                        self.lastGVReceived = gv
                        newValueReceived = True
                    self.callback(gv)
                    break

            if newValueReceived:
                for rec in records:
                    if not rec.display_only:
                        gv = self.recordToGV(rec)
                        if gv.st >= cutOffDate:
                            self.callback(gv)
                        else:
                            break

                for rec in self.device.iter_records('BACKFILLED_EGV'):
                    if not rec.display_only:
                        gv = self.recordToGV(rec)
                        if gv.st >= cutOffDate:
                            self.callback(gv)
                        else:
                            break

            return newValueReceived
        except Exception as e:
            logging.warn("Error reading from usb device\n" + str(e))
            return False

    def getUtcOffsetForSystemTime(self):
        deviceTime = self.device.ReadSystemTime()
        utcTime = datetime.utcnow()
        diffSeconds = (utcTime - deviceTime).total_seconds()
        #roundedDifference = int(round(diffSeconds / 1800)*1800)
        return timedelta(seconds = diffSeconds)

    def recordToGV(self, record):
        st = record.meter_time + self.systemTimeOffset
        direction = record.full_trend & constants.EGV_TREND_ARROW_MASK
        return GlucoseValue(None, None, st, record.glucose, direction)
        


