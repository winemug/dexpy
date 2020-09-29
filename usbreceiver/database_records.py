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
# The original file has been modified to dump data in a less annoying
# format in BaseDatabaseRecord. Methods system_secs() and display_secs()
# have been added to GenericTimestampedRecord. This is because I needed
# to store the extracted data in numeric format in a database file.
# The existing methods system_time() and display_time() return
# datetime structures which would have consumed more space in the
# database. In several methods, the FORMAT strings have been modified
# to replace 'c' (char) with 'B' (byte). This makes it easier to
# work with the extracted data. There's no longer any need to
# call ord() every time the value is referenced.
# New class, G5UserSettings & G6UserSettings have been added. These
# allows one to read the user configuration settings.
#
#########################################################################
from msgpack.fallback import xrange

import usbreceiver.crc16
import usbreceiver.constants
import struct
import usbreceiver.util
import binascii

from usbreceiver import constants, util

EGV_TESTNUM_MASK = 0x00ffffff

class BaseDatabaseRecord(object):
  FORMAT = None

  @classmethod
  def _CheckFormat(cls):
    if cls.FORMAT is None or not cls.FORMAT:
      raise NotImplementedError("Subclasses of %s need to define FORMAT"
                                % cls.__name__)

  @classmethod
  def _ClassFormat(cls):
    cls._CheckFormat()
    return struct.Struct(cls.FORMAT)

  @classmethod
  def _ClassSize(cls):
    return cls._ClassFormat().size

  @property
  def FMT(self):
    self._CheckFormat()
    return self._ClassFormat()

  @property
  def SIZE(self):
    return self._ClassSize()

  @property
  def crc(self):
    return self.data[-1]

  def __init__(self, data, raw_data):
    self.raw_data = raw_data
    self.data = data
    self.check_crc()

  def check_crc(self):
    local_crc = self.calculate_crc()
    if local_crc != self.crc:
      raise constants.CrcError('Could not parse %s' % self.__class__.__name__)

  def dump(self):
    return ''.join(' %02x' % ord(c) for c in self.raw_data)

  def calculate_crc(self):
    return usbreceiver.crc16.crc16(self.raw_data[:-2])

  @classmethod
  def Create(cls, data, record_counter):
    offset = record_counter * cls._ClassSize()
    raw_data = data[offset:offset + cls._ClassSize()]
    unpacked_data = cls._ClassFormat().unpack(raw_data)
    return cls(unpacked_data, raw_data)


class GenericTimestampedRecord(BaseDatabaseRecord):
  FIELDS = [ ]
  BASE_FIELDS = [ 'system_time', 'display_time' ]

  @property
  def system_time(self):
    return util.ReceiverTimeToTime(self.data[0])

  @property
  def display_time(self):
    return util.ReceiverTimeToTime(self.data[1])

  @property
  def system_secs(self):
    return self.data[0]

  @property
  def display_secs(self):
    return self.data[1]

  def to_dict (self):
    d = dict( )
    for k in self.BASE_FIELDS + self.FIELDS:
      d[k] = getattr(self, k)
      if callable(getattr(d[k], 'isoformat', None)):
        d[k] = d[k].isoformat( )
    return d

class GenericXMLRecord(GenericTimestampedRecord):
  FORMAT = '<II490sH'

  @property
  def xmldata(self):
    data = self.data[2].replace("\x00", "")
    return data


class InsertionRecord(GenericTimestampedRecord):
  FIELDS = ['insertion_time', 'session_state']
  FORMAT = '<3IBH'

  @property
  def insertion_time(self):
    if self.data[2] == 0xFFFFFFFF:
      return self.system_time
    return util.ReceiverTimeToTime(self.data[2])

  @property
  def insertion_secs(self):
    return self.data[2]

  @property
  def session_state(self):
    states = [None, 'REMOVED', 'EXPIRED', 'RESIDUAL_DEVIATION',
              'COUNTS_DEVIATION', 'SECOND_SESSION', 'OFF_TIME_LOSS',
              'STARTED', 'BAD_TRANSMITTER', 'MANUFACTURING_MODE',
              'UNKNOWN1', 'UNKNOWN2', 'UNKNOWN3', 'UNKNOWN4', 'UNKNOWN5',
              'UNKNOWN6', 'UNKNOWN7', 'UNKNOWN8']
    return states[self.data[3]]

  @property
  def state_value(self):
    return self.data[3]

  def __repr__(self):
    return '%s:  state=%s' % (self.display_time, self.session_state)

class G5InsertionRecord (InsertionRecord):
  FORMAT = '<3IBI6sH'

  @property
  def number(self):
    return self.data[4]

  @property
  def transmitterPaired (self):
    return self.data[5]     # a 6-byte string

class G5UserSettings (GenericTimestampedRecord):
  # {'RecordLength': '50', 'Name': 'UserSettingData', 'RecordRevision': '5', 'Id': '12'}
  FORMAT = '<4I6sI8HBBIH'   # total length = 50
                            # Values in positions 2,3,5,13,15, 16 are unknown

  @property
  def transmitterPaired (self):
    return self.data[4]     # Transmitter ID is a 6-byte string
  @property
  def highAlert (self):
    return self.data[6]
  @property
  def highRepeat (self):
    return self.data[7]
  @property
  def lowAlert (self):
    return self.data[8]
  @property
  def lowRepeat (self):
    return self.data[9]
  @property
  def riseRate (self):
    return self.data[10]
  @property
  def fallRate (self):
    return self.data[11]
  @property
  def outOfRangeAlert (self):
    return self.data[12]
  @property
  def soundsType (self):
    return self.data[14]

class G6UserSettings (GenericTimestampedRecord):
  # {'RecordLength': '60', 'Name': 'UserSettingData', 'RecordRevision': '6', 'Id': '12'}
  FORMAT = '<4I6sI8HBBHB4s7BH'   # total length = 60
                            # Values in positions 2,3,5,13,15,17 are unknown

  @property
  def transmitterPaired (self):
    return self.data[4]     # Transmitter ID is a 6-byte string
  @property
  def highAlert (self):
    return self.data[6]
  @property
  def highRepeat (self):
    return self.data[7]
  @property
  def lowAlert (self):
    return self.data[8]
  @property
  def lowRepeat (self):
    return self.data[9]
  @property
  def riseRate (self):
    return self.data[10]
  @property
  def fallRate (self):
    return self.data[11]
  @property
  def outOfRangeAlert (self):
    return self.data[12]
  @property
  def soundsType (self):
    return self.data[14]
  @property
  def urgentLowSoonRepeat (self):
    return self.data[16]
  @property
  def sensorCode (self):
    return self.data[18]     # Sensor Code is a 4-byte string
  

class Calibration(GenericTimestampedRecord):
  FORMAT = '<2Iddd3cdb'
  # CAL_FORMAT = '<2Iddd3cdb'
  FIELDS = [ 'slope', 'intercept', 'scale', 'decay', 'numsub', 'raw' ]
  @property
  def raw (self):
    return binascii.hexlify(self.raw_data)
  @property
  def slope  (self):
    return self.data[2]
  @property
  def intercept  (self):
    return self.data[3]
  @property
  def scale (self):
    return self.data[4]
  @property
  def decay (self):
    return self.data[8]
  @property
  def numsub (self):
    return int(self.data[9])

  def __repr__(self):
    return '%s: CAL SET:%s' % (self.display_time, self.raw)

  LEGACY_SIZE = 148
  REV_2_SIZE = 249
  @classmethod
  def _ClassSize(cls):

    return cls.REV_2_SIZE

  @classmethod
  def Create(cls, data, record_counter):
    offset = record_counter * cls._ClassSize()
    cal_size = struct.calcsize(cls.FORMAT)
    raw_data = data[offset:offset + cls._ClassSize()]

    cal_data = data[offset:offset + cal_size]
    unpacked_data = cls._ClassFormat().unpack(cal_data)
    return cls(unpacked_data, raw_data)

  def __init__ (self, data, raw_data):
    self.page_data = raw_data
    self.raw_data = raw_data
    self.data = data
    subsize = struct.calcsize(SubCal.FORMAT)
    offset = self.numsub * subsize
    calsize = struct.calcsize(self.FORMAT)
    caldata = raw_data[:calsize]
    subdata = raw_data[calsize:calsize + offset]
    crcdata = raw_data[calsize+offset:calsize+offset+2]

    subcals = [ ]
    for i in xrange(self.numsub):
      offset = i * subsize
      raw_sub = subdata[offset:offset+subsize]
      sub = SubCal(raw_sub, self.data[1])
      subcals.append(sub)

    self.subcals = subcals

    self.check_crc()
  def to_dict (self):
    res = super(Calibration, self).to_dict( )
    res['subrecords'] = [ sub.to_dict( ) for sub in  self.subcals ]
    return res
  @property
  def crc(self):
    return struct.unpack('H', self.raw_data[-2:])[0]

class LegacyCalibration (Calibration):
  @classmethod
  def _ClassSize(cls):

    return cls.LEGACY_SIZE


class SubCal (GenericTimestampedRecord):
  FORMAT = '<IIIIc'
  BASE_FIELDS = [ ]
  FIELDS = [ 'entered', 'meter',  'sensor', 'applied', ]
  def __init__ (self, raw_data, displayOffset=None):
    self.raw_data = raw_data
    self.data = self._ClassFormat().unpack(raw_data)
    self.displayOffset = displayOffset
  @property
  def entered  (self):
    return util.ReceiverTimeToTime(self.data[0])
  @property
  def meter  (self):
    return int(self.data[1])
  @property
  def sensor  (self):
    return int(self.data[2])
  @property
  def applied  (self):
    return util.ReceiverTimeToTime(self.data[3])

class MeterRecord(GenericTimestampedRecord):
  #  0 = system_time = uint (4 bytes)
  #  1 = display_time = uint (4 bytes)
  #  2 = meter_glucose = ushort (2 bytes)
  #  3 = meter_time = uint (4 bytes)
  #  4 = crc = unsigned short (2 bytes)
  FORMAT = '<2IHIH'
  FIELDS = ['meter_glucose', 'meter_time' ]

  @property
  def meter_glucose(self):
    return self.data[2]

  @property
  def meter_time(self):
    return util.ReceiverTimeToTime(self.data[3])

  def __repr__(self):
    return '%s: Meter BG:%s' % (self.display_time, self.meter_glucose)

class G5MeterRecord (GenericTimestampedRecord):
  #  0 = system_time = uint (4 bytes)
  #  1 = display_time = uint (4 bytes)
  #  2 = meter_glucose = ushort (2 bytes)
  #  3 = ? = unsigned char (1 byte) 
  #  4 = meter_time = uint (4 bytes)
  #  5 = ?  = uint (4 bytes)    frequently == -1
  #  6 = crc = unsigned short (2 bytes)
  FORMAT = '<2IHBIIH'
  FIELDS = ['meter_glucose', 'meter_unknown1', 'meter_time', 'meter_unknown2' ]


class EventRecord(GenericTimestampedRecord):
  # sys_time,display_time,glucose,meter_time,crc
  FORMAT = '<2I2B2IH'
  FIELDS = ['event_type', 'event_sub_type', 'event_value' ]

  @property
  def event_type(self):
    event_types = [None, 'CARBS', 'INSULIN', 'HEALTH', 'EXCERCISE',
                    'MAX_VALUE']
    return event_types[self.data[2]]

  @property
  def event_sub_type(self):
    subtypes = {'HEALTH': [None, 'ILLNESS', 'STRESS', 'HIGH_SYMPTOMS',
                            'LOW_SYMTOMS', 'CYCLE', 'ALCOHOL'],
                'EXCERCISE': [None, 'LIGHT', 'MEDIUM', 'HEAVY',
                              'MAX_VALUE']}
    if self.event_type in subtypes:
      return subtypes[self.event_type][self.data[3]]

  @property
  def display_time(self):
    return util.ReceiverTimeToTime(self.data[4])

  @property
  def event_value(self):
    value = self.data[5]
    if self.event_type == 'INSULIN':
      value = value / 100.0
    return value

  @property
  def int_type (self):
    return self.data[2]

  @property
  def int_sub_type (self):
    return self.data[3]

  @property
  def meter_secs (self):    # seconds since BASE_TIME
    return self.data[4]

  @property
  def int_value (self):
    return self.data[5]

  def __repr__(self):
    return '%s:  event_type=%s sub_type=%s value=%s' % (self.display_time, self.event_type,
                                    self.event_sub_type, self.event_value)

class SensorRecord(GenericTimestampedRecord):
  # uint, uint, uint, uint, ushort
  # (system_seconds, display_seconds, unfiltered, filtered, rssi, crc)
  FORMAT = '<2IIIhH'
  # (unfiltered, filtered, rssi)
  FIELDS = ['unfiltered', 'filtered', 'rssi']
  @property
  def unfiltered(self):
    return self.data[2]

  @property
  def filtered(self):
    return self.data[3]

  @property
  def rssi(self):
    return self.data[4]


class EGVRecord(GenericTimestampedRecord):
  #  0 = system_time = uint (4 bytes)
  #  1 = display_time = uint (4 bytes)
  #  2 = glucose = ushort (2 bytes)
  #  3 = trend_arrow = unsigned char (1 byte), low 4 bits are significant
  #  4 = crc = unsigned short (2 bytes)
  # uint, uint, ushort, byte, ushort
  # (system_seconds, display_seconds, glucose, trend_arrow, crc)
  FIELDS = ['glucose', 'trend_arrow']
  FORMAT = '<2IHcH'

  @property
  def full_glucose(self):
    return self.data[2]

  @property
  def full_trend(self):
    return self.data[3]

  @property
  def display_only(self):
    return bool(self.full_glucose & constants.EGV_DISPLAY_ONLY_MASK)

  @property
  def glucose(self):
    return self.full_glucose & constants.EGV_VALUE_MASK

  @property
  def glucose_special_meaning(self):
    if self.glucose in constants.SPECIAL_GLUCOSE_VALUES:
      return constants.SPECIAL_GLUCOSE_VALUES[self.glucose]

  @property
  def is_special(self):
    return self.glucose_special_meaning is not None

  @property
  def testNum(self):
    return self.data[5] & EGV_TESTNUM_MASK

  @property
  def trend_arrow(self):
    arrow_value = self.full_trend & constants.EGV_TREND_ARROW_MASK
    return constants.TREND_ARROW_VALUES[arrow_value]

  def __repr__(self):
    if self.is_special:
      return '%s: %s' % (self.display_time, self.glucose_special_meaning)
    else:
      # 'DO:True' indicates a Sensor Not Calibrated or a user-entered calibration event
      return '%s: CGM BG:%u (%s) DO:%s' % (self.display_time, self.glucose,
                                           self.trend_arrow, self.display_only)


class G5EGVRecord (EGVRecord):
  #  0 = systemTime = integer (4 bytes)
  #  1 = displayTime = integer (4 bytes)
  #  2 = glucose value = ushort (2 bytes)
  #  3 = meterTime = integer (4 bytes)
  #  4 = unknown = unsigned char (1 byte)
  #  5 = testNum = unsigned short (4 bytes) generally increases with each record, but
  #                          sometimes has out-of-order '7fffffff' value instead
  #  6 = trend = unsigned char (1 byte) low 4 bits are significant
  #  7 = unknown = unsigned char (1 byte)
  #  8 = unknown = unsigned short (2 bytes) seems to always hold '00 00'
  #  9 = crc = unsigned short (2 bytes)
  FORMAT = '<2IHIBIBBHH'
  @property
  def full_trend(self):
    return self.data[6]

  @property
  def meter_time(self):
    return util.ReceiverTimeToTime(self.data[3])