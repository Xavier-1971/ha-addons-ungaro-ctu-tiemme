import socket
import time
import json
import os
from datetime import datetime
import paho.mqtt.client as mqtt
import warnings

# Supprimer les warnings de dépréciation MQTT
warnings.filterwarnings("ignore", category=DeprecationWarning)

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

# Chargement des états
ETATS_CHAUDIERE = charger_etats_chaudiere()

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
                print(f"[{datetime.now()}] Commande: {commande} -> Réponse: {reponse_str}")
                return reponse_str
    except Exception as e:
        print(f"Erreur TCP: {e}")
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

def configurer_mqtt_discovery(client):
    """Configure MQTT Discovery pour le capteur d'état"""
    
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
    
    # Publication des configurations
    print("Publication config MQTT Discovery...")
    result1 = client.publish("homeassistant/sensor/ungaro_etat_code/config", json.dumps(config_etat_num), retain=True)
    result2 = client.publish("homeassistant/sensor/ungaro_etat_nom/config", json.dumps(config_etat_nom), retain=True)
    print(f"Config publiée - Code: {result1.rc}, Nom: {result2.rc}")
    
    # États initiaux
    print("Publication états initiaux...")
    client.publish("ungaro/etat/code", "0", retain=True)
    client.publish("ungaro/etat/nom", "Arrêt", retain=True)
    
    print("MQTT Discovery configuré pour Ungaro CTU A2 24")
    print(f"Device ID: {DEVICE_INFO['identifiers'][0]}")
    print(f"Topics: homeassistant/sensor/ungaro_etat_code/config")
    print(f"        homeassistant/sensor/ungaro_etat_nom/config")

def main():
    try:
        # Récupération des variables d'environnement
        adresse_ip = os.environ.get('ADRESSE_IP', '192.168.1.16')
        port_tcp = int(os.environ.get('PORT_TCP', '8899'))
        mqtt_host = os.environ.get('MQTT_HOST', 'core-mosquitto')
        mqtt_port = int(os.environ.get('MQTT_PORT', '1883'))
        mqtt_user = os.environ.get('MQTT_USER', '')
        mqtt_password = os.environ.get('MQTT_PASSWORD', '')
        intervalle_maj = int(os.environ.get('INTERVALLE_MAJ', '30'))
        
        print(f"Ungaro CTU A2 24 - Surveillance {adresse_ip}:{port_tcp}")
    except Exception as e:
        print(f"Erreur configuration: {e}")
        return
    
    # Configuration client MQTT avec reconnexion automatique
    try:
        client = mqtt.Client()
        client.reconnect_delay_set(min_delay=1, max_delay=60)
    except Exception as e:
        print(f"Erreur création client MQTT: {e}")
        return
    
    # Variables globales pour gérer l'état MQTT
    mqtt_connected = False
    
    def on_connect(client, userdata, flags, rc, properties=None):
        nonlocal mqtt_connected
        if rc == 0:
            print("MQTT connecté - Configuration découverte...")
            mqtt_connected = True
            configurer_mqtt_discovery(client)
        else:
            print(f"Erreur connexion MQTT: {rc}")
            mqtt_connected = False
    
    def on_disconnect(client, userdata, rc):
        nonlocal mqtt_connected
        mqtt_connected = False
        if rc != 0:
            print("Connexion MQTT perdue - reconnexion automatique...")
    
    def on_publish(client, userdata, mid, reason_code=None, properties=None):
        pass  # Silencieux
    
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_publish = on_publish
    
    # Authentification MQTT si nécessaire
    if mqtt_user and mqtt_password:
        client.username_pw_set(mqtt_user, mqtt_password)
    
    # Test de connexion TCP à la chaudière
    test_reponse = envoyer_commande_tcp(adresse_ip, port_tcp, "I30001000000000000")
    if not test_reponse:
        print("ERREUR: Chaudière inaccessible - vérifiez l'adresse IP et le port")
        return
    
    # Connexion MQTT avec fallback
    try:
        client.connect(mqtt_host, mqtt_port, 60)
    except Exception as e:
        print(f"Erreur connexion MQTT {mqtt_host}: {e}")
        try:
            client.connect('localhost', mqtt_port, 60)
            print("Connecté à MQTT via localhost")
        except Exception as e2:
            print(f"Erreur connexion localhost: {e2}")
            print("Fonctionnement sans MQTT - les états ne seront pas publiés")
    
    # Démarrage de la boucle MQTT en arrière-plan
    client.loop_start()
    time.sleep(2)  # Attendre la connexion initiale
    
    print("Surveillance démarrée - Intervalle: {}s".format(intervalle_maj))
    
    # Boucle principale
    try:
        while True:
            reponse = envoyer_commande_tcp(adresse_ip, port_tcp, "I30001000000000000")
            
            if reponse:
                code_etat, nom_etat = analyser_etat_chaudiere(reponse)
                
                if code_etat is not None:
                    print(f"État chaudière: {code_etat} - {nom_etat}")
                    
                    # Publier seulement si MQTT est connecté
                    if mqtt_connected:
                        try:
                            client.publish("ungaro/etat/code", str(code_etat), retain=True)
                            client.publish("ungaro/etat/nom", nom_etat, retain=True)
                        except Exception as e:
                            print(f"Erreur publication MQTT: {e}")
                else:
                    print("Réponse chaudière invalide")
            else:
                print("Chaudière non accessible")
            
            time.sleep(intervalle_maj)
            
    except KeyboardInterrupt:
        print("Arrêt demandé")
    except Exception as e:
        print(f"Erreur: {e}")
        import traceback
        traceback.print_exc()
    finally:
        try:
            client.loop_stop()
            client.disconnect()
        except:
            pass

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Erreur fatale: {e}")
        import traceback
        traceback.print_exc()
        time.sleep(10)