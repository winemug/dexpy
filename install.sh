#!/bin/bash
apt install -y udev python3
python3 -m pip install -r requirements.txt --upgrade
mkdir -p /etc/udev/rules.d
cp 80-dexcom.rules /etc/udev/rules.d/
echo "
[Unit]
Description=Dexpy
After=network.target

[Service]
EnvironmentFile=-$(pwd)/dexpy.env
ExecStart=$(pwd)/dexpy-start.sh
WorkingDirectory=$(pwd)
StandardOutput=inherit
StandardError=inherit
TimeoutStopSec=30
Restart=on-abort
User=$(logname)

[Install]
WantedBy=multi-user.target" > dexpy.service
cp dexpy.service /etc/systemd/system/
chmod 755 dexpy-start.sh
systemctl enable dexpy.service
systemctl start dexpy.service
