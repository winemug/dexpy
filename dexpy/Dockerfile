FROM python:2-slim

RUN apt update -y && apt upgrade -y
RUN apt install

WORKDIR /usr/src/app

COPY . . 
RUN pip install --no-cache-dir -r requirements.txt

CMD [ "bash", "./entrypoint.sh" ]