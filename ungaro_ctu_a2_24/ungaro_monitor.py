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
        
        # États initiaux
        client.publish("ungaro/etat/code", "0", retain=True)
        client.publish("ungaro/etat/nom", "Eteinte", retain=True)
        client.publish("ungaro/erreur/code", "0", retain=True)
        client.publish("ungaro/erreur/nom", "Non", retain=True)
        
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
        # S'abonner au topic homeassistant/status pour détecter les redémarrages HA
        client.subscribe("homeassistant/status")
        logger.info("Abonnement au topic homeassistant/status")
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