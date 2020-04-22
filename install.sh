#!/bin/bash
apt get install -y udev python-pip
pip install --no-cache-dir -r requirements.txt
mkdir -p /etc/udev/rules.d
cp 80-dexcom.rules /etc/udev/rules.d/
echo "
[Unit]
Description=Dexpy
echo After=network.target

[Service]
ExecStart=($pwd)entrypoint.sh
WorkingDirectory=($pwd)
StandardOutput=inherit
StandardError=inherit
TimeoutStopSec=30
Restart=on-abort
User=($logname)

[Install]
WantedBy=multi-user.target" > dexpy.service
cp dexpy.service /etc/systemd/system/
systemctl enable dexpy.service
systemctl start dexpy.service
