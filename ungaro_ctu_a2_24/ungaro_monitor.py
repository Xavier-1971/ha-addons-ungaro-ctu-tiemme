import socket
import time
import json
import os
from datetime import datetime
import logging
import paho.mqtt.client as mqtt

# Configuration du logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Ungaro CTU A2 24")

# Constantes pour la reconnexion MQTT
MAX_RECONNECT_ATTEMPTS = 10
RECONNECT_DELAY_BASE = 2

def charger_etats_chaudiere():
    """Charge les états depuis le fichier JSON"""
    try:
        with open('/app/etats_chaudiere.json', 'r', encoding='utf-8') as f:
            etats_str = json.load(f)
            # Convertir les clés string en int pour compatibilité
            return {int(k): v for k, v in etats_str.items()}
    except Exception as e:
        print(f"Erreur chargement états: {e}")
        return {}

def charger_erreurs_chaudiere():
    """Charge les erreurs depuis le fichier JSON"""
    try:
        with open('/app/erreurs_chaudiere.json', 'r', encoding='utf-8') as f:
            erreurs_str = json.load(f)
            # Convertir les clés string en int pour compatibilité
            return {int(k): v for k, v in erreurs_str.items()}
    except Exception as e:
        print(f"Erreur chargement erreurs: {e}")
        return {}

# Chargement des états et erreurs
ETATS_CHAUDIERE = charger_etats_chaudiere()
ERREURS_CHAUDIERE = charger_erreurs_chaudiere()

# Informations du device
DEVICE_INFO = {
    "identifiers": ["ungaro_ctu_a2_24"],
    "name": "Ungaro CTU A2 24",
    "manufacturer": "Ungaro",
    "model": "CTU A2 24"
}

def envoyer_commande_tcp(adresse, port, commande):
    """Envoie une commande TCP à la chaudière"""
    try:
        with socket.create_connection((adresse, port), timeout=5) as sock:
            # Format: 08 + commande_hex + 0d
            commande_hex = ''.join(f"{ord(c):02x}" for c in commande)
            trame_complete = f"08{commande_hex}0d"
            sock.sendall(bytes.fromhex(trame_complete))
            
            reponse = sock.recv(1024)
            if reponse:
                reponse_str = reponse.decode(errors='ignore').strip('\x08\r\n')
                logger.debug(f"TCP {adresse}:{port} - {commande} -> {reponse_str}")
                return reponse_str
    except Exception as e:
        logger.error(f"Erreur TCP {adresse}:{port}: {e}")
        return None

def analyser_etat_chaudiere(reponse):
    """Analyse la réponse pour extraire l'état de la chaudière"""
    if not reponse:
        return None, None
    
    reponse_clean = reponse.strip('\x08\r\n')
    
    # Format attendu: J30001000000000XXX
    if reponse_clean.startswith('J30001000000000'):
        try:
            code_etat = int(reponse_clean[-3:])
            nom_etat = ETATS_CHAUDIERE.get(code_etat, "Inconnu")
            return code_etat, nom_etat
        except ValueError:
            return None, None
    
    return None, None

def analyser_erreur_chaudiere(reponse):
    """Analyse la réponse pour extraire l'erreur de la chaudière"""
    if not reponse:
        return None, None
    
    reponse_clean = reponse.strip('\x08\r\n')
    
    # Format attendu: J300020000000000XX
    if reponse_clean.startswith('J300020000000000'):
        try:
            code_erreur = int(reponse_clean[-2:])  # 2 derniers caractères
            nom_erreur = ERREURS_CHAUDIERE.get(code_erreur, "Inconnu")
            return code_erreur, nom_erreur
        except ValueError:
            return None, None
    
    return None, None

def analyser_temperature_fumee(reponse):
    """Analyse la réponse pour extraire la température de fumée"""
    if not reponse:
        return None
    
    reponse_clean = reponse.strip('\x08\r\n')
    
    # Format attendu: J30005000000000XXX
    if reponse_clean.startswith('J30005000000000'):
        try:
            temperature = int(reponse_clean[-3:])  # 3 derniers caractères
            return temperature
        except ValueError:
            return None
    
    return None

def analyser_puissance_combustion(reponse):
    """Analyse la réponse pour extraire la puissance de combustion"""
    if not reponse:
        return None
    
    reponse_clean = reponse.strip('\x08\r\n')
    
    # Format attendu: J30011000000000XXX
    if reponse_clean.startswith('J30011000000000'):
        try:
            puissance = int(reponse_clean[-3:])  # 3 derniers caractères
            return puissance
        except ValueError:
            return None
    
    return None

def analyser_temperature_eau(reponse):
    """Analyse la réponse pour extraire la température de l'eau"""
    if not reponse:
        return None
    
    reponse_clean = reponse.strip('\x08\r\n')
    
    # Format attendu: J30017000000000XXX
    if reponse_clean.startswith('J30017000000000'):
        try:
            temperature = int(reponse_clean[-3:])  # 3 derniers caractères
            return temperature
        except ValueError:
            return None
    
    return None

def analyser_temperature_exterieure_chaudiere(reponse):
    """Analyse la réponse pour extraire la température extérieure mesurée par la chaudière"""
    if not reponse:
        return None
    
    reponse_clean = reponse.strip('\x08\r\n')
    
    # Format attendu: I30044000000-00002 (négatif) ou I30044000000000015 (positif)
    if reponse_clean.startswith('I30044000000'):
        try:
            # Extraire tout après "I30044000000" (12 caractères)
            temp_str = reponse_clean[12:]
            temperature = int(temp_str)  # int() gère automatiquement le signe -
            return temperature
        except ValueError:
            return None
    
    return None

def analyser_pression_eau(reponse):
    """Analyse la réponse pour extraire la pression de l'eau"""
    if not reponse:
        return None
    
    reponse_clean = reponse.strip('\x08\r\n')
    
    # Format attendu: J3002000000000XXXX (1 chiffre entier + 3 chiffres décimaux)
    if reponse_clean.startswith('J3002000000000'):
        try:
            valeur_complete = reponse_clean[-4:]  # 4 derniers caractères
            partie_entiere = int(valeur_complete[0])  # Premier chiffre
            partie_decimale = int(valeur_complete[1:])  # 3 derniers chiffres
            # Reconstitution: partie_entière.partie_décimale
            return partie_entiere + (partie_decimale / 1000.0)
        except (ValueError, IndexError):
            return None
    
    return None

def analyser_temperature_consigne_eau(reponse):
    """Analyse la réponse pour extraire la température de consigne de l'eau"""
    if not reponse:
        return None
    
    reponse_clean = reponse.strip('\x08\r\n')
    
    # Format attendu: B20180000000000XXX
    if reponse_clean.startswith('B20180000000000'):
        try:
            temperature = int(reponse_clean[-3:])  # 3 derniers caractères
            return temperature
        except ValueError:
            return None
    
    return None

def publier_mqtt_discovery(client):
    """Publie la configuration MQTT Discovery"""
    
    # Capteur état numérique
    config_etat_num = {
        "name": "État Chaudière (Code)",
        "state_topic": "ungaro/etat/code",
        "unique_id": "ungaro_etat_code",
        "icon": "mdi:fire",
        "device": DEVICE_INFO
    }
    
    # Capteur état textuel
    config_etat_nom = {
        "name": "État Chaudière",
        "state_topic": "ungaro/etat/nom", 
        "unique_id": "ungaro_etat_nom",
        "icon": "mdi:information",
        "device": DEVICE_INFO
    }
    
    # Capteur erreur numérique
    config_erreur_num = {
        "name": "Erreur Chaudière (Code)",
        "state_topic": "ungaro/erreur/code",
        "unique_id": "ungaro_erreur_code",
        "icon": "mdi:alert-circle",
        "device": DEVICE_INFO
    }
    
    # Capteur erreur textuel
    config_erreur_nom = {
        "name": "Erreur Chaudière",
        "state_topic": "ungaro/erreur/nom", 
        "unique_id": "ungaro_erreur_nom",
        "icon": "mdi:alert-circle-outline",
        "device": DEVICE_INFO
    }
    
    # Capteur température fumée
    config_temp_fumee = {
        "name": "Température Fumée",
        "state_topic": "ungaro/temperature/fumee",
        "unique_id": "ungaro_temperature_fumee",
        "unit_of_measurement": "°C",
        "device_class": "temperature",
        "icon": "mdi:thermometer",
        "device": DEVICE_INFO
    }
    
    # Capteur puissance combustion
    config_puissance = {
        "name": "Puissance Combustion",
        "state_topic": "ungaro/puissance/combustion",
        "unique_id": "ungaro_puissance_combustion",
        "icon": "mdi:fire",
        "device": DEVICE_INFO
    }
    
    # Capteur température eau
    config_temp_eau = {
        "name": "Température Eau",
        "state_topic": "ungaro/temperature/eau",
        "unique_id": "ungaro_temperature_eau",
        "unit_of_measurement": "°C",
        "device_class": "temperature",
        "icon": "mdi:water-thermometer",
        "device": DEVICE_INFO
    }
    
    # Capteur température extérieure chaudière
    config_temp_ext_chaudiere = {
        "name": "Température Extérieure Chaudière",
        "state_topic": "ungaro/temperature/exterieure_chaudiere",
        "unique_id": "ungaro_temperature_exterieure_chaudiere",
        "unit_of_measurement": "°C",
        "device_class": "temperature",
        "icon": "mdi:thermometer-probe",
        "device": DEVICE_INFO
    }
    
    # Capteur pression eau
    config_pression_eau = {
        "name": "Pression Eau",
        "state_topic": "ungaro/pression/eau",
        "unique_id": "ungaro_pression_eau",
        "unit_of_measurement": "bar",
        "device_class": "pressure",
        "icon": "mdi:gauge",
        "device": DEVICE_INFO
    }
    
    # Capteur température consigne eau
    config_temp_consigne_eau = {
        "name": "Température Consigne Eau",
        "state_topic": "ungaro/temperature/consigne_eau",
        "unique_id": "ungaro_temperature_consigne_eau",
        "unit_of_measurement": "°C",
        "device_class": "temperature",
        "icon": "mdi:thermometer-lines",
        "device": DEVICE_INFO
    }
    
    # Contrôle température consigne eau (number)
    config_control_temp_consigne = {
        "name": "Réglage Consigne Eau",
        "command_topic": "ungaro/temperature/consigne_eau/set",
        "state_topic": "ungaro/temperature/consigne_eau",
        "unique_id": "ungaro_control_temperature_consigne_eau",
        "unit_of_measurement": "°C",
        "device_class": "temperature",
        "icon": "mdi:thermometer-plus",
        "min": 45,
        "max": 75,
        "step": 1,
        "device": DEVICE_INFO
    }
    
    # Bouton mise en marche
    config_bouton_marche = {
        "name": "Mise en Marche",
        "command_topic": "ungaro/commande/marche",
        "unique_id": "ungaro_bouton_marche",
        "icon": "mdi:play",
        "device": DEVICE_INFO
    }
    
    # Bouton arrêt
    config_bouton_arret = {
        "name": "Arrêt",
        "command_topic": "ungaro/commande/arret",
        "unique_id": "ungaro_bouton_arret",
        "icon": "mdi:stop",
        "device": DEVICE_INFO
    }
    
    # Bouton RAZ erreur
    config_bouton_raz = {
        "name": "RAZ Code Erreur",
        "command_topic": "ungaro/commande/raz_erreur",
        "unique_id": "ungaro_bouton_raz_erreur",
        "icon": "mdi:alert-remove",
        "device": DEVICE_INFO
    }
    
    try:
        # Publication des configurations
        client.publish("homeassistant/sensor/ungaro_etat_code/config", 
                      json.dumps(config_etat_num), retain=True)
        client.publish("homeassistant/sensor/ungaro_etat_nom/config", 
                      json.dumps(config_etat_nom), retain=True)
        client.publish("homeassistant/sensor/ungaro_erreur_code/config", 
                      json.dumps(config_erreur_num), retain=True)
        client.publish("homeassistant/sensor/ungaro_erreur_nom/config", 
                      json.dumps(config_erreur_nom), retain=True)
        client.publish("homeassistant/sensor/ungaro_temperature_fumee/config", 
                      json.dumps(config_temp_fumee), retain=True)
        client.publish("homeassistant/sensor/ungaro_puissance_combustion/config", 
                      json.dumps(config_puissance), retain=True)
        client.publish("homeassistant/sensor/ungaro_temperature_eau/config", 
                      json.dumps(config_temp_eau), retain=True)
        client.publish("homeassistant/sensor/ungaro_pression_eau/config", 
                      json.dumps(config_pression_eau), retain=True)
        client.publish("homeassistant/sensor/ungaro_temperature_consigne_eau/config", 
                      json.dumps(config_temp_consigne_eau), retain=True)
        client.publish("homeassistant/sensor/ungaro_temperature_exterieure_chaudiere/config", 
                      json.dumps(config_temp_ext_chaudiere), retain=True)
        client.publish("homeassistant/number/ungaro_control_temperature_consigne_eau/config", 
                      json.dumps(config_control_temp_consigne), retain=True)
        client.publish("homeassistant/button/ungaro_bouton_marche/config", 
                      json.dumps(config_bouton_marche), retain=True)
        client.publish("homeassistant/button/ungaro_bouton_arret/config", 
                      json.dumps(config_bouton_arret), retain=True)
        client.publish("homeassistant/button/ungaro_bouton_raz_erreur/config", 
                      json.dumps(config_bouton_raz), retain=True)
        
        # États initiaux
        client.publish("ungaro/etat/code", "0", retain=True)
        client.publish("ungaro/etat/nom", "Eteinte", retain=True)
        client.publish("ungaro/erreur/code", "0", retain=True)
        client.publish("ungaro/erreur/nom", "Non", retain=True)
        client.publish("ungaro/temperature/fumee", "0", retain=True)
        client.publish("ungaro/puissance/combustion", "0", retain=True)
        client.publish("ungaro/temperature/eau", "0", retain=True)
        client.publish("ungaro/pression/eau", "0", retain=True)
        client.publish("ungaro/temperature/consigne_eau", "0", retain=True)
        client.publish("ungaro/temperature/exterieure_chaudiere", "0", retain=True)
        
        logger.info("MQTT Discovery configuré")
        
    except Exception as e:
        logger.error(f"Erreur configuration MQTT Discovery: {e}")

# Variables globales pour gérer l'état MQTT
mqtt_connected = False
client = None

# Callbacks MQTT
def on_connect(client, userdata, flags, rc):
    global mqtt_connected
    if rc == 0:
        logger.info("Connecté au broker MQTT")
        mqtt_connected = True
        # S'abonner aux topics nécessaires
        client.subscribe("homeassistant/status")
        client.subscribe("ungaro/temperature/consigne_eau/set")
        client.subscribe("ungaro/commande/marche")
        client.subscribe("ungaro/commande/arret")
        client.subscribe("ungaro/commande/raz_erreur")
        logger.info("Abonnement aux topics de contrôle")
        # Publier la configuration Discovery
        publier_mqtt_discovery(client)
    else:
        logger.error(f"Échec de connexion MQTT, code retour: {rc}")
        mqtt_connected = False

def on_disconnect(client, userdata, rc):
    global mqtt_connected
    mqtt_connected = False
    if rc != 0:
        logger.warning("Déconnecté du broker MQTT. Tentative de reconnexion...")
        reconnect_to_mqtt()

def on_message(client, userdata, msg):
    logger.debug(f"Message reçu: {msg.topic} {str(msg.payload)}")
    if msg.topic == "homeassistant/status" and msg.payload.decode() == "online":
        # Renvoyer le message MQTT discovery
        publier_mqtt_discovery(client)
        logger.info("Redémarrage HA détecté. Message MQTT Discovery renvoyé.")
    elif msg.topic == "ungaro/temperature/consigne_eau/set":
        # Commande de réglage de la température de consigne
        try:
            nouvelle_consigne = int(float(msg.payload.decode()))
            if 45 <= nouvelle_consigne <= 75:
                adresse_ip = os.environ.get('ADRESSE_IP', '192.168.1.16')
                port_tcp = int(os.environ.get('PORT_TCP', '8899'))
                
                # Formatage de la commande avec la nouvelle consigne
                commande = f"B20180000000000{nouvelle_consigne:03d}"
                reponse = envoyer_commande_tcp(adresse_ip, port_tcp, commande)
                
                if reponse and reponse.startswith('A20180000000000'):
                    logger.info(f"Consigne eau modifiée: {nouvelle_consigne}°C")
                    # Publier la nouvelle valeur
                    client.publish("ungaro/temperature/consigne_eau", str(nouvelle_consigne), retain=True)
                else:
                    logger.error(f"Erreur modification consigne eau: {reponse}")
            else:
                logger.warning(f"Consigne hors limites: {nouvelle_consigne}°C (45-75°C)")
        except ValueError:
            logger.error(f"Valeur consigne invalide: {msg.payload.decode()}")
    elif msg.topic == "ungaro/commande/marche":
        # Commande de mise en marche
        adresse_ip = os.environ.get('ADRESSE_IP', '192.168.1.16')
        port_tcp = int(os.environ.get('PORT_TCP', '8899'))
        
        reponse = envoyer_commande_tcp(adresse_ip, port_tcp, "J30253000000000001")
        
        if reponse and reponse.startswith('I30253000000000'):
            logger.info("Chaudière mise en marche")
        else:
            logger.error(f"Erreur mise en marche: {reponse}")
    elif msg.topic == "ungaro/commande/arret":
        # Commande d'arrêt
        adresse_ip = os.environ.get('ADRESSE_IP', '192.168.1.16')
        port_tcp = int(os.environ.get('PORT_TCP', '8899'))
        
        reponse = envoyer_commande_tcp(adresse_ip, port_tcp, "J30254000000000001")
        
        if reponse and reponse.startswith('I30254000000000'):
            logger.info("Chaudière arrêtée")
        else:
            logger.error(f"Erreur arrêt: {reponse}")
    elif msg.topic == "ungaro/commande/raz_erreur":
        # Commande de RAZ code erreur
        adresse_ip = os.environ.get('ADRESSE_IP', '192.168.1.16')
        port_tcp = int(os.environ.get('PORT_TCP', '8899'))
        
        reponse = envoyer_commande_tcp(adresse_ip, port_tcp, "J30255000000000001")
        
        if reponse and reponse.startswith('I30255000000000'):
            logger.info("RAZ code erreur effectuée")
        else:
            logger.error(f"Erreur RAZ code erreur: {reponse}")

def on_log(client, userdata, level, buf):
    logger.debug(buf)

def reconnect_to_mqtt():
    global mqtt_connected
    attempt = 1
    while attempt <= MAX_RECONNECT_ATTEMPTS:
        try:
            logger.info(f"Tentative de reconnexion MQTT ({attempt}/{MAX_RECONNECT_ATTEMPTS})...")
            client.reconnect()
            # Si la reconnexion réussit, se réabonner aux topics nécessaires
            client.subscribe("homeassistant/status")
            client.subscribe("ungaro/temperature/consigne_eau/set")
            client.subscribe("ungaro/commande/marche")
            client.subscribe("ungaro/commande/arret")
            client.subscribe("ungaro/commande/raz_erreur")
            logger.info("Reconnexion réussie, réabonnement aux topics.")
            mqtt_connected = True
            break  
        except Exception as e:
            logger.error(f"Échec de reconnexion MQTT: {str(e)}")
        
        # Calcul du délai avec backoff exponentiel
        reconnect_delay = RECONNECT_DELAY_BASE * (2 ** (attempt - 1))
        logger.info(f"Attente {reconnect_delay} secondes avant la prochaine tentative...")
        time.sleep(reconnect_delay)
        attempt += 1
    
    if attempt > MAX_RECONNECT_ATTEMPTS:
        logger.error("Nombre maximum de tentatives de reconnexion dépassé. Abandon.")
        mqtt_connected = False

def main():
    global client, mqtt_connected
    
    try:
        # Récupération des variables d'environnement
        adresse_ip = os.environ.get('ADRESSE_IP', '192.168.1.16')
        port_tcp = int(os.environ.get('PORT_TCP', '8899'))
        mqtt_host = os.environ.get('MQTT_HOST', 'core-mosquitto')
        mqtt_port = int(os.environ.get('MQTT_PORT', '1883'))
        mqtt_user = os.environ.get('MQTT_USER', '')
        mqtt_password = os.environ.get('MQTT_PASSWORD', '')
        intervalle_maj = int(os.environ.get('INTERVALLE_MAJ', '30'))
        
        # Affichage de la configuration
        logger.info('Configuration en cours d\'utilisation:')
        logger.info(f'Adresse chaudière: {adresse_ip}:{port_tcp}')
        logger.info(f'Broker MQTT: {mqtt_host}:{mqtt_port}')
        logger.info(f'Utilisateur MQTT: {mqtt_user}')
        logger.info(f'Intervalle de publication: {intervalle_maj}s')
        
    except Exception as e:
        logger.error(f"Erreur configuration: {e}")
        return
    
    # Test initial de la chaudière
    test_reponse = envoyer_commande_tcp(adresse_ip, port_tcp, "I30001000000000000")
    if not test_reponse:
        logger.error("Chaudière inaccessible - vérifiez l'adresse IP et le port")
        return
    
    # Création et configuration du client MQTT
    client = mqtt.Client()
    
    # Définition des callbacks
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_log = on_log
    client.on_message = on_message
    
    # Configuration de l'authentification MQTT
    if mqtt_user and mqtt_password:
        client.username_pw_set(mqtt_user, mqtt_password)
    
    # Démarrage de la boucle MQTT
    client.loop_start()
    logger.info("Connexion au broker MQTT")
    client.connect(mqtt_host, mqtt_port)
    
    # Attendre que MQTT soit connecté avant de continuer
    while not client.is_connected():
        time.sleep(1)
        logger.info("Vérification de la connexion MQTT...")
    
    logger.info("Surveillance démarrée")
    
    # Boucle principale
    try:
        while True:
            # Interroger l'état de la chaudière
            reponse_etat = envoyer_commande_tcp(adresse_ip, port_tcp, "I30001000000000000")
            
            if reponse_etat:
                code_etat, nom_etat = analyser_etat_chaudiere(reponse_etat)
                
                if code_etat is not None:
                    logger.info(f"État chaudière: {code_etat} - {nom_etat}")
                    
                    # Publier seulement si MQTT est connecté
                    if mqtt_connected:
                        try:
                            client.publish("ungaro/etat/code", str(code_etat), retain=True)
                            client.publish("ungaro/etat/nom", nom_etat, retain=True)
                        except Exception as e:
                            logger.error(f"Erreur publication MQTT état: {e}")
            
            # Petite pause entre les requêtes
            time.sleep(1)
            
            # Interroger les erreurs de la chaudière
            reponse_erreur = envoyer_commande_tcp(adresse_ip, port_tcp, "I30002000000000000")
            
            if reponse_erreur:
                code_erreur, nom_erreur = analyser_erreur_chaudiere(reponse_erreur)
                
                if code_erreur is not None:
                    if code_erreur != 0:  # Afficher seulement si erreur
                        logger.warning(f"Erreur chaudière: {code_erreur} - {nom_erreur}")
                    
                    # Publier seulement si MQTT est connecté
                    if mqtt_connected:
                        try:
                            client.publish("ungaro/erreur/code", str(code_erreur), retain=True)
                            client.publish("ungaro/erreur/nom", nom_erreur, retain=True)
                        except Exception as e:
                            logger.error(f"Erreur publication MQTT erreur: {e}")
            
            # Petite pause entre les requêtes
            time.sleep(1)
            
            # Interroger la température de fumée
            reponse_temp = envoyer_commande_tcp(adresse_ip, port_tcp, "I30005000000000000")
            
            if reponse_temp:
                temperature_fumee = analyser_temperature_fumee(reponse_temp)
                
                if temperature_fumee is not None:
                    logger.info(f"Température fumée: {temperature_fumee}°C")
                    
                    # Publier seulement si MQTT est connecté
                    if mqtt_connected:
                        try:
                            client.publish("ungaro/temperature/fumee", str(temperature_fumee), retain=True)
                        except Exception as e:
                            logger.error(f"Erreur publication MQTT température: {e}")
            
            # Petite pause entre les requêtes
            time.sleep(1)
            
            # Interroger la puissance de combustion
            reponse_puissance = envoyer_commande_tcp(adresse_ip, port_tcp, "I30011000000000000")
            
            if reponse_puissance:
                puissance_combustion = analyser_puissance_combustion(reponse_puissance)
                
                if puissance_combustion is not None:
                    logger.info(f"Puissance combustion: {puissance_combustion}")
                    
                    # Publier seulement si MQTT est connecté
                    if mqtt_connected:
                        try:
                            client.publish("ungaro/puissance/combustion", str(puissance_combustion), retain=True)
                        except Exception as e:
                            logger.error(f"Erreur publication MQTT puissance: {e}")
            
            # Petite pause entre les requêtes
            time.sleep(1)
            
            # Interroger la température de l'eau
            reponse_temp_eau = envoyer_commande_tcp(adresse_ip, port_tcp, "I30017000000000000")
            
            if reponse_temp_eau:
                temperature_eau = analyser_temperature_eau(reponse_temp_eau)
                
                if temperature_eau is not None:
                    logger.info(f"Température eau: {temperature_eau}°C")
                    
                    # Publier seulement si MQTT est connecté
                    if mqtt_connected:
                        try:
                            client.publish("ungaro/temperature/eau", str(temperature_eau), retain=True)
                        except Exception as e:
                            logger.error(f"Erreur publication MQTT température eau: {e}")
            
            # Petite pause entre les requêtes
            time.sleep(1)
            
            # Interroger la pression de l'eau
            reponse_pression_eau = envoyer_commande_tcp(adresse_ip, port_tcp, "I30020000000000000")
            
            if reponse_pression_eau:
                pression_eau = analyser_pression_eau(reponse_pression_eau)
                
                if pression_eau is not None:
                    logger.info(f"Pression eau: {pression_eau} bar")
                    
                    # Publier seulement si MQTT est connecté
                    if mqtt_connected:
                        try:
                            client.publish("ungaro/pression/eau", str(pression_eau), retain=True)
                        except Exception as e:
                            logger.error(f"Erreur publication MQTT pression eau: {e}")
            
            # Petite pause entre les requêtes
            time.sleep(1)
            
            # Interroger la température de consigne de l'eau
            reponse_temp_consigne = envoyer_commande_tcp(adresse_ip, port_tcp, "A20180000000000000")
            
            if reponse_temp_consigne:
                temperature_consigne_eau = analyser_temperature_consigne_eau(reponse_temp_consigne)
                
                if temperature_consigne_eau is not None:
                    logger.info(f"Température consigne eau: {temperature_consigne_eau}°C")
                    
                    # Publier seulement si MQTT est connecté
                    if mqtt_connected:
                        try:
                            client.publish("ungaro/temperature/consigne_eau", str(temperature_consigne_eau), retain=True)
                        except Exception as e:
                            logger.error(f"Erreur publication MQTT température consigne eau: {e}")
            
            # Petite pause entre les requêtes
            time.sleep(1)
            
            # Interroger la température extérieure mesurée par la chaudière
            reponse_temp_ext_chaudiere = envoyer_commande_tcp(adresse_ip, port_tcp, "J30044000000000000")
            
            if reponse_temp_ext_chaudiere:
                temperature_exterieure_chaudiere = analyser_temperature_exterieure_chaudiere(reponse_temp_ext_chaudiere)
                
                if temperature_exterieure_chaudiere is not None:
                    logger.info(f"Température extérieure chaudière: {temperature_exterieure_chaudiere}°C")
                    
                    # Publier seulement si MQTT est connecté
                    if mqtt_connected:
                        try:
                            client.publish("ungaro/temperature/exterieure_chaudiere", str(temperature_exterieure_chaudiere), retain=True)
                        except Exception as e:
                            logger.error(f"Erreur publication MQTT température extérieure chaudière: {e}")
            
            time.sleep(intervalle_maj)
            
    except KeyboardInterrupt:
        logger.info("Arrêt demandé")
    except Exception as e:
        logger.error(f"Erreur: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if client:
            client.loop_stop()
            client.disconnect()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Arrêt demandé")
    except Exception as e:
        logger.error(f"Erreur fatale: {e}")
        import traceback
        traceback.print_exc()