#!/bin/bash
python ./dexpy \
        -dsl $DEXCOM_SHARE_LISTEN \
        -dsu $DEXCOM_SHARE_UPDATE \
        -dssl $DEXCOM_SHARE_SERVER_LOCATION \
        -dsu $DEXCOM_SHARE_USERNAME \
        -dsp $DEXCOM_SHARE_PASSWORD \
        -drl $DEXCOM_RECEIVER_LISTEN \
        -me $MQTT_ENABLED \
        -ms $MQTT_SERVER \
        -mp $MQTT_PORT \
        -mci $MQTT_CLIENT_ID \
        -mt $MQTT_TOPIC \
        -mssl $MQTT_SSL \
        -msslca $MQTT_SSL_CA
        -verbose $DEXPY_VERBOSE