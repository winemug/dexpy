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

### Raspbian / Debian
sudo apt install -y udev ntp git python-pip
git clone https://github.com/winemug/dexpy.git
sudo mkdir -p /etc/udev/rules.d
cd dexpy/dexpy
cp 80-dexcom.rules /etc/udev/rules.d/
chmod 755 dexpy.py
./dexpy.py 
python ./dexpy.py \
        --DEXCOM-SHARE-SERVER us \
        --DEXCOM-SHARE-USERNAME myusername \
        --DEXCOM-SHARE-PASSWORD mypassword \
        --LOG-LEVEL INFO

for other parameters check out the Configuration section below.

### Docker
dexpy software is provided as a docker container and a docker-compose script is attached for convenience. <tba>

## Parameters
DEXCOM-SHARE-SERVER: Enter "us" or "eu" based on your location, leave blank if you don't want to store your data in dexcom's cloud.
DEXCOM-SHARE-USERNAME: Enter username for your dexcom share account or leave blank if you're not using it.
DEXCOM-SHARE-PASSWORD: Enter password for your dexcom share account or leave blank if you're not using it.

MQTT-SERVER: Enter the hostname for an MQTT server to post received glucose values or leave blank for not using mqtt
MQTT-PORT: Enter the port number for the mqtt server
MQTT-SSL: "True" if you're using ssl, otherwise "False"
MQTT-TOPIC: Full name of the topic to post messages to

INFLUXDB-SERVER: Enter the hostname for your influxdb server
INFLUXDB-PORT: Enter the port for the http interface to your influxdb server
INFLUXDB-SSL: "True" if you're using ssl, otherwise "False"

NIGHTSCOUT-URL: Enter the full url of your nightscout website (only root, no api links etc, i.e. https://mynightscout.azureblabla.local/) leave blank if not using nightscout.
NIGHTSCOUT-SECRET: Enter the password used to access nightscout or if you're using a token, leave blank.
NIGHTSCOUT-TOKEN: Enter the token you've generated using nightscout or if you're using the nightscout-secret option, leave blank.

Note: If you enable the "Dexcom Share Server" option, dexpy will also read cgm data off the dexcom's servers and publish it to other services you have configured. This is useful if you're using the Dexcom app on a phone to connect to the transmitter but want your data consolidated elsewhere.

# Acknowledgements

Dexcom Share protocol is implemented according to the [reverse engineering](https://gist.github.com/StephenBlackWasAlreadyTaken/adb0525344bedade1e25) performed by github user [StephenBlackWasAlreadyTaken](https://gist.github.com/StephenBlackWasAlreadyTaken)

Dexcom Receiver code for communicating with the receiver via USB is borrowed from the [dexctrack](https://github.com/DexcTrack/dexctrack) project, which in turn is based on the [dexcom_reader](https://github.com/openaps/dexcom_reader) project. Further enhanced to support Dexcom G6 receiver backfill.
