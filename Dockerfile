FROM python:2-slim

RUN apt update -y && apt upgrade -y
RUN apt install -y udev ntp

WORKDIR /usr/src/app
RUN pip install --no-cache-dir -r requirements.txt

COPY . . 
RUN mkdir -p /etc/udev/rules.d
RUN cp /usr/src/app/80-dexcom.rules /etc/udev/rules.d/
RUN chmod 755 /usr/src/app/entrypoint.sh

CMD [ "./dexpy-start.sh" ]
