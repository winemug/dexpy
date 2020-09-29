#!/bin/bash
apt update
apt install -y udev python3 python3-pip python3-venv
python3 -m venv venv
./venv/bin/python3 -m pip install pip setuptools --upgrade
./venv/bin/python3 -m pip install -r requirements.txt --upgrade
mkdir -p /etc/udev/rules.d
cp 80-dexcom.rules /etc/udev/rules.d/
echo "
[Unit]
Description=Dexpy
After=network.target

[Service]
ExecStart=$(pwd)/venv/bin/python3 dexpy.py --CONFIGURATION dexpy.json
WorkingDirectory=$(pwd)
StandardOutput=inherit
StandardError=inherit
TimeoutStopSec=30
Restart=on-abort
User=$(logname)

[Install]
WantedBy=multi-user.target" > dexpy.service
cp dexpy.service /etc/systemd/system/
systemctl enable dexpy.service
systemctl start dexpy.service
