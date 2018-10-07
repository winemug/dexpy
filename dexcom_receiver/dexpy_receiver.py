import database_records
from readdata import Dexcom

class ReceiverSession():
    def __init__(self):
        port = Dexcom.FindDevice()
        self.device = Dexcom(port)

    def getLatestGlucoseValue(self):
        records = self.device.GetLastRecords('EGV_DATA')
        for rec in records:
            print rec
