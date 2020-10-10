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
  - Update data on the dexcom share server, because the hours long outage on new years eve of 2019 was simply unacceptable. (and it happened again in 2020 -so unexpectedly)

# Setup
* Download dexpy to your (preferably) debian based installation

```
sudo apt install -y git
git clone https://github.com/winemug/dexpy.git
cd dexpy
```

* Edit the configuration:
```
nano dexpy.json
```

Configuration example:
```
{
  "USB_RECEIVER": true,
  "DEXCOM_SHARE_SERVER": "eu",
  "DEXCOM_SHARE_USERNAME": "username",
  "DEXCOM_SHARE_PASSWORD": "password",
  "MQTT_SERVER": "mqtt.myserver.example",
  "MQTT_PORT": 1883,
  "MQTT_SSL": false,
  "MQTT_CLIENTID": "dexpy-mqtt-client",
  "MQTT_TOPIC": "cgm",
  "INFLUXDB_SERVER": "influxdb.myserver.example",
  "INFLUXDB_PORT": 8086,
  "INFLUXDB_SSL": false,
  "INFLUXDB_SSL_VERIFY": false,
  "INFLUXDB_USERNAME": "username",
  "INFLUXDB_PASSWORD": "password",
  "INFLUXDB_DATABASE": "dexpy",
  "INFLUXDB_MEASUREMENT": "bg",
  "NIGHTSCOUT_URL": "https://nightscout.myserver.example",
  "NIGHTSCOUT_SECRET": null,
  "NIGHTSCOUT_TOKEN": "ns-yadayadayada"
}
```

* Run the install script that registers the usb device driver, downloads dependencies and starts dexpy as a systemd service
```
sudo ./install.sh
```

### Reading from Dexcom Receiver via USB
**USB_RECEIVER**: _true_ to enable reading from the receiver, otherwise _false_<br/>

### Reading from Dexcom Share online
**DEXCOM_SHARE_SERVER**: "us" or "eu" based on your location, set to _null_ if you don't store your data in dexcom's cloud.<br/>
**DEXCOM_SHARE_USERNAME**: Username for your dexcom share account.<br/>
**DEXCOM_SHARE_PASSWORD**: Password for your dexcom share account.<br/>

### Sending data to an MQTT server
**MQTT_SERVER**: Hostname for an MQTT server to post received glucose values or set to _null_ if not using mqtt<br/>
**MQTT_PORT**: Port number for the mqtt server<br/>
**MQTT_SSL**: _true_ if you're using ssl, otherwise _false_<br/>
**MQTT_TOPIC**: Full name of the topic to post messages to<br/>

### Writing data to an Influx database
**INFLUXDB_SERVER**: Hostname for your influxdb server or _null_ if not using influxdb<br/>
**INFLUXDB_PORT**: Port for the http interface to your influxdb server<br/>
**INFLUXDB_SSL**: _true_ if you're using ssl, otherwise _false_<br/>
**INFLUXDB_SSL_VERIFY**: _true_ to enable certificate verification, otherwise _false_ (e.g. self-signed certificates)<br/>

### Sending data to a Nightscout instance
**NIGHTSCOUT_URL**: Full url of your nightscout website (only root, no api links etc, i.e. https://mynightscout.azureblabla.local/) _null_ if not using nightscout.<br/>
**NIGHTSCOUT_SECRET**: Password (the 12 character passphrase) used to access nightscout or if you're using a token, set to _null_<br/>
**NIGHTSCOUT_TOKEN**: Enter the token you've generated using nightscout or if you're using the nightscout-secret option, set to _null_.<br/>

Note: If you enable the "Dexcom Share Server" option, dexpy will read cgm data from dexcom's servers (whether it's available on the receiver or not) and publish it to other services you have configured. This is useful if you're using the Dexcom app on a phone to connect to the transmitter but want your data consolidated elsewhere.

## Run with docker (experimental)
* Command line (to be described)
```
docker pull wynmug/dexpy
```
* Using docker-compose (to be described)
```
        dexpy:
                image: wynmug/dexpy
                restart: always
                container_name: dexpy
                environment:
                        - INFLUXDB_SERVER=influxdb
                        - INFLUXDB_PORT=8086
                        - INFLUXDB_USERNAME=username
                        - INFLUXDB_PASSWORD=pwd
                        - INFLUXDB_DATABASE=db
                        - MQTT_SERVER=
                        - MQTT_PORT=
                        - MQTT_SSL=
                        - MQTT_CLIENTID=
                        - MQTT_TOPIC=
```

# Acknowledgements

Dexcom Share protocol is implemented according to the [reverse engineering](https://gist.github.com/StephenBlackWasAlreadyTaken/adb0525344bedade1e25) performed by github user [StephenBlackWasAlreadyTaken](https://gist.github.com/StephenBlackWasAlreadyTaken)

Dexcom Receiver code for communicating with the receiver via USB is borrowed from the [dexctrack](https://github.com/DexcTrack/dexctrack) project, which in turn is based on the [dexcom_reader](https://github.com/openaps/dexcom_reader) project. Further enhanced to support Dexcom G6 receiver backfill.
