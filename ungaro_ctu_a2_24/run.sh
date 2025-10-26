#!/usr/bin/with-contenv bashio

# Récupération de la configuration
adresse_ip=$(bashio::config 'adresse_ip')
port_tcp=$(bashio::config 'port_tcp')
mqtt_host=$(bashio::config 'mqtt_host')
mqtt_port=$(bashio::config 'mqtt_port')
mqtt_user=$(bashio::config 'mqtt_user')
mqtt_password=$(bashio::config 'mqtt_password')
intervalle_maj=$(bashio::config 'intervalle_maj')

bashio::log.info "Démarrage Ungaro CTU A2 24"
bashio::log.info "Chaudière: ${adresse_ip}:${port_tcp}"
bashio::log.info "MQTT: ${mqtt_host}:${mqtt_port}"
bashio::log.info "Intervalle: ${intervalle_maj}s"

# Export des variables pour Python
export ADRESSE_IP="${adresse_ip}"
export PORT_TCP="${port_tcp}"
export MQTT_HOST="${mqtt_host}"
export MQTT_PORT="${mqtt_port}"
export MQTT_USER="${mqtt_user}"
export MQTT_PASSWORD="${mqtt_password}"
export INTERVALLE_MAJ="${intervalle_maj}"

# Lancement du script Python
cd /app
python3 ungaro_monitor.py