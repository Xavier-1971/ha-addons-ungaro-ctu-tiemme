import socket
import time
import json
import os
from datetime import datetime
import paho.mqtt.client as mqtt

# États de la chaudière Ungaro CTU A2 24
ETATS_CHAUDIERE = {
    0: "Arrêt",
    1: "Check Up", 
    30: "Allumage",
    31: "Allumage",
    32: "Allumage", 
    33: "Allumage",
    5: "Montée en température",
    6: "Modulation",
    7: "Extinction",
    8: "Sécurité",
    9: "Bloquée",
    10: "Récupération",
    11: "Standby",
    110: "Passage en arrêt",
    255: "Passage en marche"
}

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
    if not reponse or not reponse.startswith('J30001000000000'):
        return None, None
    
    try:
        code_etat = int(reponse[-3:])
        nom_etat = ETATS_CHAUDIERE.get(code_etat, f"État inconnu ({code_etat})")
        return code_etat, nom_etat
    except ValueError:
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
    # Récupération des variables d'environnement
    adresse_ip = os.environ.get('ADRESSE_IP', '192.168.1.16')
    port_tcp = int(os.environ.get('PORT_TCP', '8899'))
    mqtt_host = os.environ.get('MQTT_HOST', 'core-mosquitto')
    mqtt_port = int(os.environ.get('MQTT_PORT', '1883'))
    mqtt_user = os.environ.get('MQTT_USER', '')
    mqtt_password = os.environ.get('MQTT_PASSWORD', '')
    intervalle_maj = int(os.environ.get('INTERVALLE_MAJ', '30'))
    
    print(f"Configuration Ungaro CTU A2 24:")
    print(f"  Chaudière: {adresse_ip}:{port_tcp}")
    print(f"  MQTT: {mqtt_host}:{mqtt_port}")
    print(f"  Intervalle: {intervalle_maj}s")
    
    # Configuration client MQTT
    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    except (AttributeError, ImportError):
        try:
            client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
        except (AttributeError, ImportError):
            client = mqtt.Client()
    
    def on_connect(client, userdata, flags, rc, properties=None):
        print(f"MQTT connecté: code {rc}")
        if rc == 0:
            print("Connexion MQTT réussie")
            # Configuration MQTT Discovery après connexion
            configurer_mqtt_discovery(client)
        else:
            print(f"Échec connexion MQTT: {rc}")
    
    def on_publish(client, userdata, mid):
        print(f"Message publié: {mid}")
    
    client.on_connect = on_connect
    client.on_publish = on_publish
    
    # Authentification MQTT si nécessaire
    if mqtt_user and mqtt_password:
        client.username_pw_set(mqtt_user, mqtt_password)
    
    # Connexion MQTT
    try:
        client.connect(mqtt_host, mqtt_port, 60)
    except Exception as e:
        print(f"Erreur connexion MQTT: {e}")
        try:
            client.connect('localhost', mqtt_port, 60)
        except Exception as e2:
            print(f"Erreur connexion localhost: {e2}")
            return
    
    client.loop_start()
    time.sleep(5)  # Attendre plus longtemps pour la connexion
    
    print("Démarrage surveillance Ungaro CTU A2 24...")
    
    # Boucle principale
    try:
        while True:
            # Interroger l'état de la chaudière
            reponse = envoyer_commande_tcp(adresse_ip, port_tcp, "I30001000000000000")
            
            if reponse:
                code_etat, nom_etat = analyser_etat_chaudiere(reponse)
                
                if code_etat is not None:
                    # Publier les états
                    client.publish("ungaro/etat/code", str(code_etat), retain=True)
                    client.publish("ungaro/etat/nom", nom_etat, retain=True)
                    print(f"État chaudière: {code_etat} - {nom_etat}")
                else:
                    print("Réponse invalide de la chaudière")
            else:
                print("Pas de réponse de la chaudière")
            
            # Attendre avant la prochaine interrogation
            time.sleep(intervalle_maj)
            
    except KeyboardInterrupt:
        print("Arrêt demandé")
    finally:
        client.loop_stop()
        client.disconnect()

if __name__ == "__main__":
    main()