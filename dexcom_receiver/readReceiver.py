###############################################################################
#    Copyright 2018 Steve Erlenborn
###############################################################################
#    This file is part of DexcTrack.
#
#    DexcTrack is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    DexcTrack is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
###############################################################################

import datetime
import sys
import time
import sqlite3
import threading
import serial
#------------------------------
import readdata
import database_records


class readReceiverBase(readdata.Dexcom):
    _lock = threading.Lock()

    # We don't want to try to re-open a port which has already been opened,
    # so we include an optional 'port' argument, which can
    # be used to specify an existing, open port.
    def __init__(self, portname, port=None):
        self._port_name = portname
        readdata.Dexcom.__init__(self, portname, port)
        #print 'readReceiverBase() __init__ running. _port =', self._port, ', _port_name =', self._port_name, ', port =', port

    def GetSerialNumber(self):
        #print 'readReceiverBase() GetSerialNumber running'
        self._lock.acquire()
        try:
            #print 'readReceiverBase.GetSerialNumber() : self._port_name =', self._port_name
            if not self._port_name:
                dport = self.FindDevice()
                self._port_name = dport

            sernum = None
            if self._port_name:
                sernum = self.ReadManufacturingData().get('SerialNumber')
            self._lock.release()
            return sernum

        except Exception as e:
            #print 'GetSerialNumber() : Exception =', e
            self.Disconnect()
            self._port_name = None
            self._lock.release()
            return None


    def DownloadToDb(self, dbPath):
        self._lock.acquire()
        if self._port_name is not None:
            #now = datetime.datetime.now()
            #print 'readReceiver.py : DownloadToDb() : Reading device at', str(now)

            #for uev_rec in self.ReadRecords('USER_EVENT_DATA'):
                #print 'raw_data =',' '.join(' %02x' % ord(c) for c in uev_rec.raw_data)

            #for cal_rec in self.ReadRecords('CAL_SET'):
                #print 'raw_data =',' '.join(' %02x' % ord(c) for c in cal_rec.raw_data)

            #for ins_rec in self.ReadRecords('INSERTION_TIME'):
                #print 'raw_data =',' '.join(' %02x' % ord(c) for c in ins_rec.raw_data)

            #--------------------------------------------------------------------------------
            conn = sqlite3.connect(dbPath)
            try:
                curs = conn.cursor()

                # The PARSER_MAP for G4 doesn't include USER_SETTING_DATA, so restrict use of it to newer releases
                if (self.rr_version == 'g5') or (self.rr_version == 'g6'):
                    curs.execute('CREATE TABLE IF NOT EXISTS UserSettings( sysSeconds INT, dispSeconds INT, transmitter STR, high INT, low INT, rise INT, fall INT, outOfRange INT);')
                    insert_usr_sql = '''INSERT OR IGNORE INTO UserSettings( sysSeconds, dispSeconds, transmitter, high, low, rise, fall, outOfRange) VALUES (?, ?, ?, ?, ?, ?, ?, ?);'''

                    respList = self.ReadRecords('USER_SETTING_DATA')
                    for usr_rec in respList:
                        curs.execute(insert_usr_sql, (usr_rec.system_secs, usr_rec.display_secs, usr_rec.transmitterPaired, usr_rec.highAlert, usr_rec.lowAlert, usr_rec.riseRate, usr_rec.fallRate, usr_rec.outOfRangeAlert))


                curs.execute('CREATE TABLE IF NOT EXISTS EgvRecord( sysSeconds INT PRIMARY KEY, dispSeconds INT, full_glucose INT, glucose INT, testNum INT, trend INT);')
                insert_egv_sql = '''INSERT OR IGNORE INTO EgvRecord( sysSeconds, dispSeconds, full_glucose, glucose, testNum, trend) VALUES (?, ?, ?, ?, ?, ?);'''

                respList = self.ReadRecords('EGV_DATA')
                #printJustOne = True
                for cgm_rec in respList:
                    #if printJustOne:
                        #print 'EGV_DATA : raw_data =', ' '.join(' %02x' % ord(c) for c in cgm_rec.raw_data)
                        #printJustOne = False
                    curs.execute(insert_egv_sql, (cgm_rec.system_secs, cgm_rec.display_secs, cgm_rec.full_glucose, cgm_rec.glucose, cgm_rec.testNum, cgm_rec.full_trend))

                curs.execute('CREATE TABLE IF NOT EXISTS UserEvent( sysSeconds INT PRIMARY KEY, dispSeconds INT, meterSeconds INT, type INT, subtype INT, value INT, xoffset REAL, yoffset REAL);')
                insert_evt_sql = '''INSERT OR IGNORE INTO UserEvent( sysSeconds, dispSeconds, meterSeconds, type, subtype, value, xoffset, yoffset) VALUES (?, ?, ?, ?, ?, ?, ?, ?);'''

                respList = self.ReadRecords('USER_EVENT_DATA')
                for evt_rec in respList:
                    #print 'raw_data =',' '.join(' %02x' % ord(c) for c in evt_rec.raw_data)
                    #print 'UserEvent(', evt_rec.system_secs, ',', evt_rec.display_secs, ', ', evt_rec.meter_secs, ', ', evt_rec.event_type, ', ', evt_rec.event_sub_type, ',', evt_rec.event_value
                    curs.execute(insert_evt_sql, (evt_rec.system_secs, evt_rec.display_secs, evt_rec.meter_secs, evt_rec.int_type, evt_rec.int_sub_type, evt_rec.int_value, 0.0, 0.0))

                curs.execute('CREATE TABLE IF NOT EXISTS Config( id INT PRIMARY KEY CHECK (id = 0), displayLow REAL, displayHigh REAL, legendX REAL, legendY REAL, glUnits STR);')
                insert_cfg_sql = '''INSERT OR IGNORE INTO Config( id, displayLow, displayHigh, legendX, legendY, glUnits) VALUES (0, ?, ?, ?, ?, ?);'''
                # If no instance exists, set default values 75 & 200. Otherwise, do nothing.
                curs.execute(insert_cfg_sql, (75.0, 200.0, 0.01, 0.99, 'mg/dL'))

                respList = self.ReadGlucoseUnit()
                #print 'self.ReadGlucoseUnit() =', respList
                if respList is not None:
                    update_cfg_sql = '''UPDATE Config SET glUnits = ? WHERE id = ?;'''
                    curs.execute(update_cfg_sql, ('%s'%respList, 0))

                curs.execute('CREATE TABLE IF NOT EXISTS SensorInsert( sysSeconds INT PRIMARY KEY, dispSeconds INT, insertSeconds INT, state INT, number INT, transmitter STR);')
                insert_ins_sql = '''INSERT OR IGNORE INTO SensorInsert( sysSeconds, dispSeconds, insertSeconds, state, number, transmitter) VALUES (?, ?, ?, ?, ?, ?);'''

                respList = self.ReadRecords('INSERTION_TIME')
                for ins_rec in respList:
                    if (self.rr_version == 'g5') or (self.rr_version == 'g6'):
                        curs.execute(insert_ins_sql, (ins_rec.system_secs, ins_rec.display_secs, ins_rec.insertion_secs, ins_rec.state_value, ins_rec.number, ins_rec.transmitterPaired))
                    else:
                        curs.execute(insert_ins_sql, (ins_rec.system_secs, ins_rec.display_secs, ins_rec.insertion_secs, ins_rec.state_value, 0, ''))

                del respList
                curs.close()
                conn.commit()
            except Exception as e:
                print 'DownloadToDb() : Rolling back SQL changes due to exception =', e
                curs.close()
                conn.rollback()
            conn.close()
        self._lock.release()
        return

#-------------------------------------------------------------------------
class readReceiver(readReceiverBase):
    # The G4 version of this class uses the default PARSER_MAP
    # but python requires us to put something in our class declaration,
    # so we declare a class variable 'rr_version'.
    rr_version = 'g4'

    def __init__(self, portname, port=None):
        #print 'readReceiver() __init__ running'
        super(readReceiver, self).__init__(portname, port)

    #def __del__(self):
        #print 'readReceiver() __del__ running'
        # If readReceiverBase.__del__() gets added ...
        #super(readReceiver, self).__del__()

#-------------------------------------------------------------------------
class readReceiverG5(readReceiverBase):
    rr_version = 'g5'
    PARSER_MAP = {
        'USER_EVENT_DATA': database_records.EventRecord,
        'METER_DATA': database_records.G5MeterRecord,
        'CAL_SET': database_records.Calibration,
        'INSERTION_TIME': database_records.G5InsertionRecord,
        'EGV_DATA': database_records.G5EGVRecord,
        'SENSOR_DATA': database_records.SensorRecord,
        'USER_SETTING_DATA': database_records.G5UserSettings,
    }

    def __init__(self, portname, port=None):
        #print 'readReceiverG5() __init__ running'
        super(readReceiverG5, self).__init__(portname, port)

    #def __del__(self):
        #print 'readReceiverG5() __del__ running'
        # If readReceiverBase.__del__() gets added ...
        #super(readReceiverG5, self).__del__()

#-------------------------------------------------------------------------
class readReceiverG6(readReceiverBase):
    # G6 uses the same format as G5 for Meter Data, Insertion, and EGV data
    rr_version = 'g6'
    PARSER_MAP = {
        'USER_EVENT_DATA': database_records.EventRecord,
        'METER_DATA': database_records.G5MeterRecord,
        'CAL_SET': database_records.Calibration,
        'INSERTION_TIME': database_records.G5InsertionRecord,
        'EGV_DATA': database_records.G5EGVRecord,
        'SENSOR_DATA': database_records.SensorRecord,
        'USER_SETTING_DATA': database_records.G6UserSettings,
    }

    def __init__(self, portname, port=None):
        #print 'readReceiverG6() __init__ running'
        super(readReceiverG6, self).__init__(portname, port)

    #def __del__(self):
        #print 'readReceiverG6() __del__ running'
        # If readReceiverBase.__del__() gets added ...
        #super(readReceiverG6, self).__del__()

#-------------------------------------------------------------------------


if __name__ == '__main__':
    mdport = readReceiverBase.FindDevice()
    if mdport:
        readSerialInstance = readReceiver(mdport)
        serialNum = readSerialInstance.GetSerialNumber()
        print 'serialNum =', serialNum
        mDevType = readSerialInstance.GetDeviceType()

        if mDevType == 'g4':
            mReadDataInstance = readSerialInstance
        elif mDevType == 'g5':
            mReadDataInstance = readReceiverG5(mdport)
        elif mDevType == 'g6':
            mReadDataInstance = readReceiverG6(mdport)
        else:
            exit

        if mReadDataInstance:
            print 'Device version =', mReadDataInstance.rr_version
            mReadDataInstance.LocateAndDownload()
