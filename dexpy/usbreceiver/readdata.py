#########################################################################
# This source file is from the openaps/dexcom_reader project. 
#
#    https://github.com/openaps/dexcom_reader
#
# It is under an MIT licence described in the 3 paragraphs below:
#
#########################################################################
#
#    Permission is hereby granted, free of charge, to any person obtaining a
#    copy of this software and associated documentation files (the "Software"),
#    to deal in the Software without restriction, including without limitation
#    the rights to use, copy, modify, merge, publish, distribute, sublicense,
#    and/or sell copies of the Software, and to permit persons to whom the
#    Software is furnished to do so, subject to the following conditions:
#
#    The above copyright notice and this permission notice shall be included
#    in all copies or substantial portions of the Software.
#
#    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
#    OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
#    THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR
#    OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
#    ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
#    OTHER DEALINGS IN THE SOFTWARE.
#
#########################################################################
#
# Modifications by Steve Erlenborn:
#   - Added try ... except to FindDevice().
#   - Added GetDeviceType() method to identify the generation of the
#     Dexcom device. Returns 'g4', 'g5', 'g6', or the firmware version
#     number.
#   - Added a retry in Connect(). If the retry also fails, and the
#     OS is unix based, suggest steps to fix permission problems.
#   - Added ReadAllManufacturingData()
#   - Added USER_SETTING_DATA for G5 & G6.
#
#########################################################################

import crc16
import constants
import database_records
import datetime
import serial
import sys
import time
import packetwriter
import struct
import re
import util
import xml.etree.ElementTree as ET
import platform

# Some services are only to be invoked on unix-based OSs
if sys.platform == "linux" or sys.platform == "linux2" or sys.platform == "darwin":
    import grp
    import pwd
    import os


class ReadPacket(object):

  def __init__(self, command, data):
    self._command = command
    self._data = data

  @property
  def command(self):
    return self._command

  @property
  def data(self):
    return self._data


class Dexcom(object):
  G4_PARSER_MAP = {
    'USER_EVENT_DATA': database_records.EventRecord,
    'METER_DATA': database_records.MeterRecord,
    'CAL_SET': database_records.Calibration,
    'INSERTION_TIME': database_records.InsertionRecord,
    'EGV_DATA': database_records.EGVRecord,
    'SENSOR_DATA': database_records.SensorRecord,
  }

  G5_PARSER_MAP = {
    'USER_EVENT_DATA': database_records.EventRecord,
    'METER_DATA': database_records.G5MeterRecord,
    'CAL_SET': database_records.Calibration,
    'INSERTION_TIME': database_records.G5InsertionRecord,
    'EGV_DATA': database_records.G5EGVRecord,
    'SENSOR_DATA': database_records.SensorRecord,
    'USER_SETTING_DATA': database_records.G5UserSettings }

  G6_PARSER_MAP = {
    'USER_EVENT_DATA': database_records.EventRecord,
    'METER_DATA': database_records.G5MeterRecord,
    'CAL_SET': database_records.Calibration,
    'INSERTION_TIME': database_records.G5InsertionRecord,
    'EGV_DATA': database_records.G5EGVRecord,
    'SENSOR_DATA': database_records.SensorRecord,
    'USER_SETTING_DATA': database_records.G6UserSettings,
    'BACKFILLED_EGV': database_records.G5EGVRecord }

  @staticmethod
  def FindDevice():
    try:
        return util.find_usbserial(constants.DEXCOM_G4_USB_VENDOR,
                                   constants.DEXCOM_G4_USB_PRODUCT)
    except:
        return None
  def GetDeviceType(self):
    try:
        device = self.FindDevice()
        if not device:
          sys.stderr.write('Could not find Dexcom G4|G5|G6 Receiver!\n')
          return None
        else:
          fw_ver = self.GetFirmwareHeader().get('FirmwareVersion')
          if fw_ver.startswith("4."):   # Not sure about G4 firmware versions
            self.PARSER_MAP = self.G4_PARSER_MAP
            return 'g4'
          elif fw_ver.startswith("5.0."): # 5.0.1.043 = G5 Receiver Firmware
            self.PARSER_MAP = self.G5_PARSER_MAP
            return 'g5'
          elif fw_ver.startswith("5."):   # 5.1.1.022 = G6 Receiver Firmware
            self.PARSER_MAP = self.G6_PARSER_MAP
            return 'g6'
          else: # unrecognized firmware version
              return fw_ver
    except Exception as e:
        print 'GetDeviceType() : Exception =', e
        return None

  @classmethod
  def LocateAndDownload(cls):
    device = cls.FindDevice()
    if not device:
      sys.stderr.write('Could not find Dexcom G4|G5|G6 Receiver!\n')
      sys.exit(1)
    else:
      dex = cls(device)
      # Uncomment two lines below to show the size of each record type
      #for item in dex.DataPartitions():
          #print item.attrib
      print 'Firmware.ProductId =', dex.GetFirmwareHeader().get('ProductId')
      print ('Found %s S/N: %s'
             % (dex.GetFirmwareHeader().get('ProductName'),
                dex.ReadManufacturingData().get('SerialNumber')))
      print 'Transmitter paired: %s' % dex.ReadTransmitterId()
      print 'Battery Status: %s (%d%%)' % (dex.ReadBatteryState(),
                                           dex.ReadBatteryLevel())
      print 'Record count:'
      print '- Meter records: %d' % (len(dex.ReadRecords('METER_DATA')))
      print '- CGM records: %d' % (len(dex.ReadRecords('EGV_DATA')))
      print ('- CGM commitable records: %d'
             % (len([not x.display_only for x in dex.ReadRecords('EGV_DATA')])))
      print '- Event records: %d' % (len(dex.ReadRecords('USER_EVENT_DATA')))
      print '- Insertion records: %d' % (len(dex.ReadRecords('INSERTION_TIME')))
      print '- Calibration records: %d' % (len(dex.ReadRecords('CAL_SET')))

      # Uncomment out any record types you want to display

      #print '\nEGV_DATA\n======================================================'
      #maxrec = 300
      #for egv_rec in dex.ReadRecords('EGV_DATA'):
          #print 'raw_data =', ' '.join(' %02x' % ord(c) for c in egv_rec.raw_data)
          #maxrec -= 1
          #if maxrec <= 0:
              #break
      #print '\nUSER_EVENT_DATA\n======================================================'
      #maxrec = 300
      #for evt_rec in dex.ReadRecords('USER_EVENT_DATA'):
          #print 'raw_data =', ' '.join(' %02x' % ord(c) for c in evt_rec.raw_data)
          #maxrec -= 1
          #if maxrec <= 0:
              #break
      #print 'SENSOR_DATA\n======================================================'
      #for sen_rec in dex.ReadRecords('SENSOR_DATA'):
          #print 'raw_data =', ' '.join(' %02x' % ord(c) for c in sen_rec.raw_data)
      #print '\nINSERTION_TIME\n======================================================'
      #for ins_rec in dex.ReadRecords('INSERTION_TIME'):
          #print 'raw_data =', ' '.join(' %02x' % ord(c) for c in ins_rec.raw_data)
      #print '\nMETER_DATA\n======================================================'
      #for met_rec in dex.ReadRecords('METER_DATA'):
          #print 'raw_data =', ' '.join(' %02x' % ord(c) for c in met_rec.raw_data)
      #print '\nMANUFACTURING_DATA\n======================================================'
      #mfg_data = dex.ReadAllManufacturingData()
      #print 'char data =', mfg_data

      # Not sure if the G4 has USER_SETTING_DATA, so we'll retrieve the
      # device type and restrict the following code to G5 or G6 cases.
      myDevType = dex.GetDeviceType()
      if (myDevType == 'g5') or (myDevType == 'g6') :
          print '- User Setting Records: %d' % (len(dex.ReadRecords('USER_SETTING_DATA')))

          #################################################################################
          # Every time you modify any user configuration parameter, a new USER_SETTING_DATA
          # record gets generated, so there can be a large number of these.
          #################################################################################
          #print 'USER_SETTING_DATA\n======================================================'
          #for sen_rec in dex.ReadRecords('USER_SETTING_DATA'):
              #print 'raw_data =', ' '.join(' %02x' % ord(c) for c in sen_rec.raw_data)
              #print 'transmitterPaired =', sen_rec.transmitterPaired
              #print 'highAlert =', sen_rec.highAlert
              #print 'highRepeat =', sen_rec.highRepeat
              #print 'lowAlert =', sen_rec.lowAlert
              #print 'lowRepeat =', sen_rec.lowRepeat
              #print 'riseRate =', sen_rec.riseRate
              #print 'fallRate =', sen_rec.fallRate
              #print 'outOfRangeAlert =', sen_rec.outOfRangeAlert
              #print 'soundsType =', sen_rec.soundsType
              #if myDevType == 'g6' :
                  #print 'urgentLowSoonRepeat =', sen_rec.urgentLowSoonRepeat
                  #print 'sensorCode =', sen_rec.sensorCode
                  #print ''

  def __init__(self, port_path, port=None):
    self._port_name = port_path
    self._port = port
    self.GetDeviceType()

  def Connect(self):
    try:
        if self._port is None:
            self._port = serial.Serial(port=self._port_name, baudrate=115200)
    except serial.SerialException:
        try:
            if self._port is None:
                #print 'First attempt failed'
                if sys.platform == "linux" or sys.platform == "linux2" or sys.platform == "darwin":
                    # Trying to access the port file may help make it visible.
                    # For example, on Linux, running 'ls <self._port_name>' helps make
                    # a subsequent serial port access work.
                    stat_info = os.stat(self._port_name)
                time.sleep(15)
                self._port = serial.Serial(port=self._port_name, baudrate=115200)

        except serial.SerialException:
            print 'Read/Write permissions missing for', self._port_name
            if sys.platform == "linux" or sys.platform == "linux2" or sys.platform == "darwin":
                stat_info = os.stat(self._port_name)
                port_gid = stat_info.st_gid
                port_group = grp.getgrgid(port_gid)[0]
                username = pwd.getpwuid(os.getuid())[0]
                print '\nFor a persistent solution (recommended), run ...'
                if sys.platform == "darwin":
                    print '\n   sudo dseditgroup -o edit -a', username, '-t user', port_group
                else:
                    # On Mint, Ubuntu, etc.
                    print '\n   sudo addgroup', username, port_group
                    print '\n   sudo -', username
                    print '\n         OR'
                    # On Fedora, Red Hat, etc.
                    print '\n   sudo usermod -a -G', port_group, username
                    print '\n   su -', username
                print '\nFor a short term solution, run ...'
                print '\n   sudo chmod 666', self._port_name,'\n'
    if self._port is not None:
        try:
            self.clear()
        except Exception as e:
            pass

        try:
            self.flush()
        except Exception as e:
            pass

  def Disconnect(self):
    if self._port is not None:
      # If the user disconnects the USB cable while in the middle
      # of a Write/Read operation, we can end up with junk in the
      # serial port buffers. After reconnecting the cable, this
      # junk can cause a lock-up on that port. So, clear and
      # flush the port during this Disconnect operation to prevent
      # a possible future lock-up. Note: the clear() and flush()
      # operations can throw exceptions when there is nothing to
      # be cleaned up, so we use try ... except to ignore those.
      try:
          self.clear()
      except Exception as e:
          #print 'Disconnect() : Exception =', e
          pass

      try:
          self.flush()
      except Exception as e:
          #print 'Disconnect() : Exception =', e
          pass
      self._port.close()
    self._port = None

  @property
  def port(self):
    if self._port is None:
      self.Connect()
    return self._port

  def write(self, *args, **kwargs):
    return self.port.write(*args, **kwargs)

  def read(self, *args, **kwargs):
    return self.port.read(*args, **kwargs)

  def readpacket(self, timeout=None):
    total_read = 4
    initial_read = self.read(total_read)
    all_data = initial_read
    if ord(initial_read[0]) == 1:
      command = initial_read[3]
      data_number = struct.unpack('<H', initial_read[1:3])[0]
      if data_number > 6:
        toread = abs(data_number-6)
        second_read = self.read(toread)
        all_data += second_read
        total_read += toread
        out = second_read
      else:
        out =  ''
      suffix = self.read(2)
      sent_crc = struct.unpack('<H', suffix)[0]
      local_crc = crc16.crc16(all_data, 0, total_read)
      if sent_crc != local_crc:
        raise constants.CrcError("readpacket Failed CRC check")
      num1 = total_read + 2
      return ReadPacket(command, out)
    else:
      raise constants.Error('Error reading packet header!')

  def Ping(self):
    self.WriteCommand(constants.PING)
    packet = self.readpacket()
    return ord(packet.command) == constants.ACK

  def WritePacket(self, packet):
    if not packet:
      raise constants.Error('Need a packet to send')
    packetlen = len(packet)
    if packetlen < 6 or packetlen > 1590:
      raise constants.Error('Invalid packet length')
    self.flush()
    self.write(packet)

  def WriteCommand(self, command_id, *args, **kwargs):
    p = packetwriter.PacketWriter()
    p.ComposePacket(command_id, *args, **kwargs)
    self.WritePacket(p.PacketString())

  def GenericReadCommand(self, command_id):
    self.WriteCommand(command_id)
    return self.readpacket()

  def ReadTransmitterId(self):
    return self.GenericReadCommand(constants.READ_TRANSMITTER_ID).data

  def ReadLanguage(self):
    lang = self.GenericReadCommand(constants.READ_LANGUAGE).data
    return constants.LANGUAGES[struct.unpack('H', lang)[0]]

  def ReadBatteryLevel(self):
    level = self.GenericReadCommand(constants.READ_BATTERY_LEVEL).data
    return struct.unpack('I', level)[0]

  def ReadBatteryState(self):
    state = self.GenericReadCommand(constants.READ_BATTERY_STATE).data
    return constants.BATTERY_STATES[ord(state)]

  def ReadRTC(self):
    rtc = self.GenericReadCommand(constants.READ_RTC).data
    return util.ReceiverTimeToTime(struct.unpack('I', rtc)[0])

  def ReadSystemTime(self):
    rtc = self.GenericReadCommand(constants.READ_SYSTEM_TIME).data
    return util.ReceiverTimeToTime(struct.unpack('I', rtc)[0])

  def ReadSystemTimeOffset(self):
    raw = self.GenericReadCommand(constants.READ_SYSTEM_TIME_OFFSET).data
    return datetime.timedelta(seconds=struct.unpack('i', raw)[0])

  def ReadDisplayTimeOffset(self):
    raw = self.GenericReadCommand(constants.READ_DISPLAY_TIME_OFFSET).data
    return datetime.timedelta(seconds=struct.unpack('i', raw)[0])

  def WriteDisplayTimeOffset(self, offset=None):
    payload = struct.pack('i', offset)
    self.WriteCommand(constants.WRITE_DISPLAY_TIME_OFFSET, payload)
    packet = self.readpacket()
    return dict(ACK=ord(packet.command) == constants.ACK)


  def ReadDisplayTime(self):
    return self.ReadSystemTime() + self.ReadDisplayTimeOffset()

  def ReadGlucoseUnit(self):
    UNIT_TYPE = (None, 'mg/dL', 'mmol/L')
    gu = self.GenericReadCommand(constants.READ_GLUCOSE_UNIT).data
    return UNIT_TYPE[ord(gu[0])]

  def ReadClockMode(self):
    CLOCK_MODE = (24, 12)
    cm = self.GenericReadCommand(constants.READ_CLOCK_MODE).data
    return CLOCK_MODE[ord(cm[0])]

  def ReadDeviceMode(self):
    # ???
    return self.GenericReadCommand(constants.READ_DEVICE_MODE).data

  def ReadBlindedMode(self):
    MODES = { 0: False }
    raw = self.GenericReadCommand(constants.READ_BLINDED_MODE).data
    mode = MODES.get(bytearray(raw)[0], True)
    return mode

  def ReadHardwareBoardId(self):
    return self.GenericReadCommand(constants.READ_HARDWARE_BOARD_ID).data

  def ReadEnableSetupWizardFlag (self):
    # ???
    return self.GenericReadCommand(constants.READ_ENABLE_SETUP_WIZARD_FLAG).data

  def ReadSetupWizardState (self):
    # ???
    return self.GenericReadCommand(constants.READ_SETUP_WIZARD_STATE).data

  def WriteChargerCurrentSetting (self, status):
    MAP = ( 'Off', 'Power100mA', 'Power500mA', 'PowerMax', 'PowerSuspended' )
    payload = str(bytearray([MAP.index(status)]))
    self.WriteCommand(constants.WRITE_CHARGER_CURRENT_SETTING, payload)
    packet = self.readpacket()
    raw = bytearray(packet.data)
    return dict(ACK=ord(packet.command) == constants.ACK, raw=list(raw))

  def ReadChargerCurrentSetting (self):
    MAP = ( 'Off', 'Power100mA', 'Power500mA', 'PowerMax', 'PowerSuspended' )
    raw = bytearray(self.GenericReadCommand(constants.READ_CHARGER_CURRENT_SETTING).data)
    return MAP[raw[0]]


  # ManufacturingParameters: SerialNumber, HardwarePartNumber, HardwareRevision, DateTimeCreated, HardwareId
  def ReadManufacturingData(self):
    data = self.ReadRecords('MANUFACTURING_DATA')[0].xmldata
    return ET.fromstring(data)

  def ReadAllManufacturingData(self):
    data = self.ReadRecords('MANUFACTURING_DATA')[0].xmldata
    return data

  def flush(self):
    self.port.flush()

  def clear(self):
    self.port.flushInput()
    self.port.flushOutput()

  def GetFirmwareHeader(self):
    i = self.GenericReadCommand(constants.READ_FIRMWARE_HEADER)
    return ET.fromstring(i.data)

  # FirmwareSettingsParameters: FirmwareImageId
  def GetFirmwareSettings(self):
    i = self.GenericReadCommand(constants.READ_FIRMWARE_SETTINGS)
    return ET.fromstring(i.data)

  def DataPartitions(self):
    i = self.GenericReadCommand(constants.READ_DATABASE_PARTITION_INFO)
    return ET.fromstring(i.data)

  def ReadDatabasePageRange(self, record_type):
    record_type_index = constants.RECORD_TYPES.index(record_type)
    self.WriteCommand(constants.READ_DATABASE_PAGE_RANGE,
                      chr(record_type_index))
    packet = self.readpacket()
    return struct.unpack('II', packet.data)

  def ReadDatabasePage(self, record_type, page):
    record_type_index = constants.RECORD_TYPES.index(record_type)
    self.WriteCommand(constants.READ_DATABASE_PAGES,
                      (chr(record_type_index), struct.pack('I', page), chr(1)))
    packet = self.readpacket()
    assert ord(packet.command) == 1
    # first index (uint), numrec (uint), record_type (byte), revision (byte),
    # page# (uint), r1 (uint), r2 (uint), r3 (uint), ushort (Crc)
    header_format = '<2IcB4IH'
    header_data_len = struct.calcsize(header_format)
    header = struct.unpack_from(header_format, packet.data)
    header_crc = crc16.crc16(packet.data[:header_data_len-2])
    assert header_crc == header[-1]
    assert ord(header[2]) == record_type_index
    assert header[4] == page
    packet_data = packet.data[header_data_len:]

    return self.ParsePage(header, packet_data)

  def GenericRecordYielder(self, header, data, record_type):
    for x in xrange(header[1]):
      yield record_type.Create(data, x)

  def ParsePage(self, header, data):
    record_type = constants.RECORD_TYPES[ord(header[2])]
    revision = int(header[3])
    generic_parser_map = self.PARSER_MAP
    if revision < 2 and record_type == 'CAL_SET':
      generic_parser_map.update(CAL_SET=database_records.LegacyCalibration)
    xml_parsed = ['PC_SOFTWARE_PARAMETER', 'MANUFACTURING_DATA']
    if record_type in generic_parser_map:
      return self.GenericRecordYielder(header, data,
                                       generic_parser_map[record_type])
    elif record_type in xml_parsed:
      return [database_records.GenericXMLRecord.Create(data, 0)]
    else:
      raise NotImplementedError('Parsing of %s has not yet been implemented'
                                % record_type)

  def GetLastRecords(self, record_type):
    assert record_type in constants.RECORD_TYPES
    page_range = self.ReadDatabasePageRange(record_type)
    start, end = page_range
    records = list(self.ReadDatabasePage(record_type, end))
    records.reverse( )
    return records

  def iter_records (self, record_type):
    assert record_type in constants.RECORD_TYPES
    page_range = self.ReadDatabasePageRange(record_type)
    start, end = page_range
    if start != end or not end:
      end += 1
    for x in reversed(xrange(start, end)):
      records = list(self.ReadDatabasePage(record_type, x))
      records.reverse( )
      for record in records:
        yield record
  
  def ReadRecords(self, record_type):
    records = []
    assert record_type in constants.RECORD_TYPES
    page_range = self.ReadDatabasePageRange(record_type)
    start, end = page_range
    if start != end or not end:
      end += 1
    for x in range(start, end):
      records.extend(self.ReadDatabasePage(record_type, x))
    return records