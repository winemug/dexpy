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

import usbreceiver.constants
import datetime
import os
import platform
import plistlib
import re
import subprocess
import sys

from usbreceiver import constants

if sys.platform == 'win32':
    import serial.tools.list_ports
    #from _winreg import *


def ReceiverTimeToTime(rtime):
  return constants.DEXCOM_EPOCH + rtime


def linux_find_usbserial(vendor, product):
  DEV_REGEX = re.compile('^tty(USB|ACM)[0-9]+$')
  for usb_dev_root in os.listdir('/sys/bus/usb/devices'):
    device_name = os.path.join('/sys/bus/usb/devices', usb_dev_root)
    if not os.path.exists(os.path.join(device_name, 'idVendor')):
      continue
    idv = open(os.path.join(device_name, 'idVendor')).read().strip()
    if idv != vendor:
      continue
    idp = open(os.path.join(device_name, 'idProduct')).read().strip()
    if idp != product:
      continue
    for root, dirs, files in os.walk(device_name):
      for option in dirs + files:
        if DEV_REGEX.match(option):
          return os.path.join('/dev', option)


def osx_find_usbserial(vendor, product):
  def recur(v):
    if hasattr(v, '__iter__') and 'idVendor' in v and 'idProduct' in v:
      if v['idVendor'] == vendor and v['idProduct'] == product:
        tmp = v
        while True:
          if 'IODialinDevice' not in tmp and 'IORegistryEntryChildren' in tmp:
            tmp = tmp['IORegistryEntryChildren']
          elif 'IODialinDevice' in tmp:
            return tmp['IODialinDevice']
          else:
            break

    if type(v) == list:
      for x in v:
        out = recur(x)
        if out is not None:
          return out
    elif type(v) == dict or issubclass(type(v), dict):
      for x in v.values():
        out = recur(x)
        if out is not None:
          return out

  sp = subprocess.Popen(['/usr/sbin/ioreg', '-k', 'IODialinDevice',
                         '-r', '-t', '-l', '-a', '-x'],
                        stdout=subprocess.PIPE,
                        stdin=subprocess.PIPE, stderr=subprocess.PIPE)
  stdout, _ = sp.communicate()
  plist = plistlib.readPlistFromString(stdout.decode())
  return recur(plist)


def thisIsWine():
    # if sys.platform == 'win32':
    #     try:
    #         registry = ConnectRegistry(None, HKEY_LOCAL_MACHINE)
    #         if registry is not None:
    #             try:
    #                 winekey = OpenKey(registry, 'Software\Wine')
    #                 if winekey is not None:
    #                     return True
    #                 else:
    #                     return False
    #             except Exception as e:
    #                 #print 'OpenKey failed. Exception =', e
    #                 return False
    #         else:
    #             return False
    #
    #     except Exception as f:
    #         #print 'ConnectRegistry failed. Exception =', f
    #         return False
    # else:
    return False


def win_find_usbserial(vendor, product):
    if thisIsWine():
        # When running under WINE, we have no access to real USB information, such
        # as the Vendor & Product ID values. Also, serial.tools.list_ports.comports()
        # returns nothing. The real port under Linux (or OSX?) is mapped to a windows
        # serial port at \dosdevices\COMxx, but we don't know which one. Normally,
        # COM1 - COM32 are automatically mapped to /dev/ttyS0 - /dev/ttyS31.
        # If the Dexcom device is plugged in, it will be mapped to COM33 or greater.
        # We have no way of identifying which port >= COM33 is the right one, so
        # we'll just guess the first available one.
        return "\\\\.\\com33"
    else:
        for cport in serial.tools.list_ports.comports():
            if (cport.vid == vendor) and (cport.pid == product):
                # found a port which matches vendor and product IDs
                if cport.device is not None:
                    return cport.device
        return None



def find_usbserial(vendor, product):
  """Find the tty device for a given usbserial devices identifiers.

  Args:
     vendor: (int) something like 0x0000
     product: (int) something like 0x0000

  Returns:
     String, like /dev/ttyACM0 or /dev/tty.usb...
  """
  if platform.system() == 'Linux':
    vendor, product = [('%04x' % (x)).strip() for x in (vendor, product)]
    return linux_find_usbserial(vendor, product)
  elif platform.system() == 'Darwin':
    return osx_find_usbserial(vendor, product)
  elif platform.system() == 'Windows':
    return win_find_usbserial(vendor, product)
  else:
    raise NotImplementedError('Cannot find serial ports on %s'
                              % platform.system())
