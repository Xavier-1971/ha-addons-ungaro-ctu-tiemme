import socket
import time
import json
import os
from datetime import datetime
import paho.mqtt.client as mqtt

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
    print("DEBUT FONCTION MAIN", flush=True)
    try:
        print("Récupération variables d'environnement...", flush=True)
        # Récupération des variables d'environnement
        adresse_ip = os.environ.get('ADRESSE_IP', '192.168.1.16')
        port_tcp = int(os.environ.get('PORT_TCP', '8899'))
        mqtt_host = os.environ.get('MQTT_HOST', 'core-mosquitto')
        mqtt_port = int(os.environ.get('MQTT_PORT', '1883'))
        mqtt_user = os.environ.get('MQTT_USER', '')
        mqtt_password = os.environ.get('MQTT_PASSWORD', '')
        intervalle_maj = int(os.environ.get('INTERVALLE_MAJ', '30'))
        
        print(f"Configuration: {adresse_ip}:{port_tcp} -> {mqtt_host}:{mqtt_port}", flush=True)
    except Exception as e:
        print(f"Erreur configuration: {e}", flush=True)
        return
    
    # Configuration client MQTT
    print("Création client MQTT...", flush=True)
    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
        print("Client MQTT créé", flush=True)
    except Exception as e:
        print(f"Erreur création client MQTT: {e}", flush=True)
        return
    
    print("Configuration callbacks...", flush=True)
    
    def on_connect(client, userdata, flags, rc, properties=None):
        print(f"Callback on_connect: rc={rc}", flush=True)
        if rc == 0:
            print("MQTT connecté", flush=True)
            configurer_mqtt_discovery(client)
        else:
            print(f"Erreur MQTT: {rc}", flush=True)
    
    def on_publish(client, userdata, mid, reason_code=None, properties=None):
        pass  # Silencieux
    
    client.on_connect = on_connect
    client.on_publish = on_publish
    print("Callbacks configurés", flush=True)
    
    # Authentification MQTT si nécessaire
    print("Configuration authentification MQTT...", flush=True)
    if mqtt_user and mqtt_password:
        print(f"Configuration auth MQTT: {mqtt_user}", flush=True)
        client.username_pw_set(mqtt_user, mqtt_password)
    else:
        print("Pas d'authentification MQTT", flush=True)
    
    # Test de connexion TCP à la chaudière d'abord
    print(f"Test connexion TCP à la chaudière {adresse_ip}:{port_tcp}...", flush=True)
    test_reponse = envoyer_commande_tcp(adresse_ip, port_tcp, "I30001000000000000")
    if test_reponse:
        print(f"Connexion chaudière OK: {test_reponse}", flush=True)
    else:
        print("ATTENTION: Impossible de se connecter à la chaudière", flush=True)
    
    # Connexion MQTT
    print(f"Tentative connexion MQTT à {mqtt_host}:{mqtt_port}...", flush=True)
    try:
        client.connect(mqtt_host, mqtt_port, 60)
        print("Connexion MQTT initialisée", flush=True)
    except Exception as e:
        print(f"ERREUR connexion MQTT: {e}", flush=True)
        print("Tentative avec localhost...", flush=True)
        try:
            client.connect('localhost', mqtt_port, 60)
            print("Connexion localhost initialisée", flush=True)
        except Exception as e2:
            print(f"ERREUR connexion localhost: {e2}", flush=True)
            print("Continuons sans MQTT pour le debug...", flush=True)
            # Ne pas retourner, continuer pour tester la chaudière
    
    print("Démarrage loop MQTT...", flush=True)
    client.loop_start()
    print("Attente connexion...", flush=True)
    time.sleep(2)
    
    print("Surveillance démarrée", flush=True)
    
    # Boucle principale
    print("Début boucle principale", flush=True)
    try:
        compteur = 0
        while True:
            compteur += 1
            print(f"Cycle {compteur}", flush=True)
            
            reponse = envoyer_commande_tcp(adresse_ip, port_tcp, "I30001000000000000")
            
            if reponse:
                code_etat, nom_etat = analyser_etat_chaudiere(reponse)
                
                if code_etat is not None:
                    print(f"État: {code_etat} - {nom_etat}", flush=True)
                    client.publish("ungaro/etat/code", str(code_etat), retain=True)
                    client.publish("ungaro/etat/nom", nom_etat, retain=True)
                else:
                    print("Réponse invalide", flush=True)
            else:
                print("Pas de réponse TCP", flush=True)
            
            print(f"Attente {intervalle_maj}s...", flush=True)
            time.sleep(intervalle_maj)
            
    except KeyboardInterrupt:
        print("Arrêt demandé par l'utilisateur", flush=True)
    except Exception as e:
        print(f"ERREUR dans la boucle principale: {e}", flush=True)
        import traceback
        traceback.print_exc()
    finally:
        print("Nettoyage final...", flush=True)
        try:
            client.loop_stop()
            client.disconnect()
        except:
            pass

if __name__ == "__main__":
    print("LANCEMENT MAIN", flush=True)
    try:
        main()
    except Exception as e:
        print(f"Erreur: {e}", flush=True)
        import traceback
        traceback.print_exc()
        time.sleep(10)