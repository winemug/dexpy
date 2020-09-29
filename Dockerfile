FROM python:3

RUN apt update -y && apt upgrade -y
RUN apt install -y udev ntp

WORKDIR /usr/src/app
RUN python3 -m pip install pip setuptools --upgrade
RUN python3 -m pip install --no-cache-dir -r requirements.txt

COPY . . 
RUN mkdir -p /etc/udev/rules.d
RUN cp /usr/src/app/80-dexcom.rules /etc/udev/rules.d/
RUN chmod 755 /usr/src/app/entrypoint.sh

CMD [ "./docker-entrypoint.sh" ]
