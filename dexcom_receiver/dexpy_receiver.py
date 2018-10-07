from database_records import constants
from readdata import Dexcom
from datetime import datetime, timedelta
import threading

class ReceiverSession():
    def __init__(self, callback):
        port = Dexcom.FindDevice()
        self.device = Dexcom(port)
        self.callback = callback

    def startMonitoring(self):
        self.dumpAllData()
        self.timer = threading.Timer(20.0, self.getLatestGlucoseValue)

    def stopMonitoring(self):
        self.timer.stop()

    def getLatestGlucoseValue(self):
        records = self.device.iter_records('EGV_DATA')
        count = 0
        for rec in records:
            dtx = rec.system_time + self.td
            arrow = rec.full_trend & constants.EGV_TREND_ARROW_MASK
            self.callback(dtx, arrow, rec.glucose)
            count += 1
            if count == 36:
                break

        self.timer = threading.Timer(20.0, self.getLatestGlucoseValue)

    def getUtcOffsetForSystemTime(self):
        deviceTime = self.device.ReadSystemTime()
        hostTime = datetime.utcnow()
        self.td = hostTime - deviceTime

    def dumpAllData(self):
        self.getUtcOffsetForSystemTime()

        for rec in self.device.ReadRecords('EGV_DATA'):
            if not rec.display_only:
                dtx = rec.system_time + self.td
                arrow = rec.full_trend & constants.EGV_TREND_ARROW_MASK
                self.callback(dtx, arrow, rec.glucose)

        self.timer.start()
    


