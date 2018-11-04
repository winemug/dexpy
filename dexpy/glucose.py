import datetime
import json
import re

def parseDateTime(val):
    res = re.search("Date\\((\\d*)", val)
    epoch = float(res.group(1)) / 1000
    return datetime.datetime.utcfromtimestamp(epoch)

class GlucoseValue():
    def __init__(self, dt, wt, st, value, trend):
        self.dt = dt
        self.wt = wt
        self.st = st
        self.value = value
        self.trend = trend
        self.trackingId = None

    @staticmethod
    def fromJson(jsonResponse, timeoffset):
        dt = parseDateTime(jsonResponse["DT"]) + timeoffset
        wt = parseDateTime(jsonResponse["WT"]) + timeoffset
        st = parseDateTime(jsonResponse["ST"]) + timeoffset
        value = float(jsonResponse["Value"])
        trend = int(jsonResponse["Trend"])
        return GlucoseValue(dt, wt, st, value, trend)

    def equals(self, other):
        secondDifference = abs((self.st - other.st).total_seconds())
        if secondDifference >= 240:
            return False
        if self.trend != other.trend:
            return False
        if int(round(self.value)) != int(round(other.value)):
            return False

        return True

    def __str__(self):
        return "DT: %s WT: %s ST: %s Trend: %d Value: %f" % (self.dt, self.wt, self.st, self.trend, self.value)