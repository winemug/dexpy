import datetime
import logging
import re

NightscoutTrendStrings = ['None', 'DoubleUp', 'SingleUp', 'FortyFiveUp', 'Flat', 'FortyFiveDown', 'SingleDown', 'DoubleDown', 'NotComputable', 'OutOfRange']

def parseDateTime(val):
    res = re.search("Date\\((\\d*)", val)
    return float(res.group(1)) / 1000


class GlucoseValue():
    def __init__(self, dt, wt, st, value, trend):
        self.logger = logging.getLogger('DEXPY')

        self.dt = dt
        self.wt = wt
        self.st = st
        self.value = value
        self.trend = trend

    def trendAsString(self):
        return NightscoutTrendStrings[self.trend]

    @staticmethod
    def fromJson(jsonResponse, timeoffset):
        dt = parseDateTime(jsonResponse["DT"]) + timeoffset
        wt = parseDateTime(jsonResponse["WT"]) + timeoffset
        st = parseDateTime(jsonResponse["ST"]) + timeoffset
        value = float(jsonResponse["Value"])
        trend = int(jsonResponse["Trend"])
        return GlucoseValue(dt, wt, st, value, trend)

    def __eq__(self, other):
        return self.same_ts(other) and self.same_val(other)

    def __ne__(self, other):
        return not self.__eq__(other)

    def __gt__(self, other):
        return self.__ne__(other) and self.st > other.st

    def __lt__(self, other):
        return self.__ne__(other) and self.st < other.st

    def __ge__(self, other):
        return self.__eq__(other) or self.st > other.st

    def __le__(self, other):
        return self.__eq__(other) or self.st < other.st

    def same_ts(self, other):
        seconds_diff = self.st - other.st
        return abs(seconds_diff) < 240

    def same_val(self, other):
        return int(round(self.value)) == int(round(other.value))

    def equals(self, other):
        secondDifference = abs((self.st - other.st))
        if secondDifference >= 240:
            return False
        if self.trend != other.trend:
            return False
        if int(round(self.value)) != int(round(other.value)):
            return False

        return True

    def __str__(self):
        return "DT: %s WT: %s ST: %s Trend: %s Value: %f" % (self.dt, self.wt, self.st, self.trendAsString(), self.value)