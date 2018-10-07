# dexpy
A set of tools for reading cgm data from dexcom g5/g6 receivers and Android/iPhone applications in realtime (or close to it). The readings, as they arrive, can then be used in other applications such as artificial pancreas systems and various monitoring tools.

## Features
- Reads sensor data as soon as it's available
- Automatic back-fill of up to 24h of data
- Sample client for sending realtime glucose values to an MQTT server

## Dexpy Share
Connects to dexcom servers via internet using user's dexcom share account and reports glucose readings.

## Dexpy Receiver
Connects to the dexcom receiver via USB port and reports glucose readings.
