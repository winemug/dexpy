import datetime
import json
import re

def parseDateTime(val):
    res = re.search("Date\\((\\d*)", val)
    epoch = float(res.group(1)) / 1000
    return datetime.datetime.utcfromtimestamp(epoch)

class GlucoseValue():
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