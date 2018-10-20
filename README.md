# dexpy
This is a docker container for reading cgm data from dexcom g5/g6 receivers and Android/iPhone applications in realtime (or close to it). The readings, as they arrive, can then be used in other applications such as artificial pancreas systems and various monitoring tools.

## Purpose

To breathe life into the dexcom receiver.

## Background

...

## Features

- Implemented:
  - Reads sensor data from dexcom share server and the dexcom receiver
  - Automatic back-fills data retained on the sensor
  - Publishes the glucose readings to an MQTT server for further integration to other applications
- Not yet working:
  - Update data on the dexcom share server with receiver readings

## Installation

...tbd..

## Sample Uses

...tbd..

## Acknowledgements

Dexcom Share protocol is implemented according to the [reverse engineering](https://gist.github.com/StephenBlackWasAlreadyTaken/adb0525344bedade1e25) performed by github user [StephenBlackWasAlreadyTaken](https://gist.github.com/StephenBlackWasAlreadyTaken)

Dexcom Receiver code for communicating with the receiver via USB is borrowed from the [dexctrack](https://github.com/DexcTrack/dexctrack) project, which in turn is based on the [dexcom_reader](https://github.com/openaps/dexcom_reader) project. Further enhanced to support Dexcom G6 receiver backfill.