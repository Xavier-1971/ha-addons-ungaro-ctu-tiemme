ARG BUILD_FROM
FROM $BUILD_FROM

# Installation Python et dépendances
RUN apk add --no-cache python3 py3-pip
RUN pip3 install --break-system-packages paho-mqtt

# Copie des fichiers
WORKDIR /app
COPY run.sh /app/run.sh
COPY ungaro_monitor.py /app/ungaro_monitor.py
COPY etats_chaudiere.json /app/etats_chaudiere.json

# Permissions
RUN chmod a+x /app/run.sh

CMD [ "/app/run.sh" ]