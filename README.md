# dexpy
## Why
Many dexcom users get the official receiver as part of their standard kit. It is a neat little device that connects to the transmitter via bluetooth low energy and displays readings as they arrive. Unfortunately it lacks the connectivity options of the 21st century; there is no wireless, no bluetooth, no 2G/3G/4G, no nothing. On top of this, it is very sluggish to operate, has a very low quality display & touch screen and is extremely frustrating (to me personally) to unlock.

Dexcom provides alternatively smartphone software, for only a limited number of "compatible" brands, which can do the same things that the receiver can and in addition use the smartphone environment to connect to online services for sharing data, analytics etc. There is however a big limitation of the dexcom provided smartphone software: You can only connect one smartphone to read the data from the CGM transmitter. That means increasing coverage for your CGM is not really an option by using multiple phones and the dexcom software.

This limitation however does not apply when using the receiver, the smartphone and the receiver can both read data at the same time.

## What
The purpose of this software is to make the receiver more useful by giving the users the option to connect and integrate it into other systems. It also provides an option to read data additionally from dexcom's own servers, if you happen to use the smartphone option, so you can consolidate data coming from two receivers in a single place.

## How
In order to transfer the readings in real-time, you need to connect the receiver via usb to a computer where you run this software. It could be for example a raspberry pi (small and mobile) or just any computer in a fixed spot (say, livingroom?).

# Features
##  It can:
  - .. read sensor data directly from the dexcom receiver
  - .. read sensor data online from the dexcom share server (sharing must be enabled with the official dexcom app)
  - .. publish sensor data to a Nightscout instance
  - .. publish sensor data to an MQTT server
  - .. publish sensor data to an InfluxDB server
  - .. automatically transmit back-fill data as it becomes available
##  It cannot:
  - Update data on the dexcom share server with receiver readings
##  It will not:
  - Update data on the dexcom share server, because the hours long outage on new years eve of 2019 was simply unacceptable.

# Setup
## Installation
dexpy software is provided as a docker container and a docker-compose script is attached for convenience. <tba>

## Configuration
<tba>

# Acknowledgements

Dexcom Share protocol is implemented according to the [reverse engineering](https://gist.github.com/StephenBlackWasAlreadyTaken/adb0525344bedade1e25) performed by github user [StephenBlackWasAlreadyTaken](https://gist.github.com/StephenBlackWasAlreadyTaken)

Dexcom Receiver code for communicating with the receiver via USB is borrowed from the [dexctrack](https://github.com/DexcTrack/dexctrack) project, which in turn is based on the [dexcom_reader](https://github.com/openaps/dexcom_reader) project. Further enhanced to support Dexcom G6 receiver backfill.
