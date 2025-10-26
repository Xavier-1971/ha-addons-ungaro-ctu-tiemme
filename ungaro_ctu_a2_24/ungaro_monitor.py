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
    try:
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
    except Exception as e:
        print(f"ERREUR lors de la récupération de la configuration: {e}")
        return
    
    # Configuration client MQTT (comme dans l'ancien code)
    print("Création client MQTT...")
    try:
        # Nouvelle API VERSION2 (recommandée)
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        print("Client MQTT VERSION2 créé")
    except (AttributeError, ImportError):
        try:
            client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
            print("Client MQTT VERSION1 créé")
        except (AttributeError, ImportError):
            client = mqtt.Client()
            print("Client MQTT legacy créé")
    
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
        print(f"Configuration auth MQTT: {mqtt_user}")
        client.username_pw_set(mqtt_user, mqtt_password)
    else:
        print("Pas d'authentification MQTT")
    
    # Test de connexion TCP à la chaudière d'abord
    print(f"Test connexion TCP à la chaudière {adresse_ip}:{port_tcp}...")
    test_reponse = envoyer_commande_tcp(adresse_ip, port_tcp, "I30001000000000000")
    if test_reponse:
        print(f"Connexion chaudière OK: {test_reponse}")
    else:
        print("ATTENTION: Impossible de se connecter à la chaudière")
    
    # Connexion MQTT
    print(f"Tentative connexion MQTT à {mqtt_host}:{mqtt_port}...")
    try:
        client.connect(mqtt_host, mqtt_port, 60)
        print("Connexion MQTT initialisée")
    except Exception as e:
        print(f"ERREUR connexion MQTT: {e}")
        print("Tentative avec localhost...")
        try:
            client.connect('localhost', mqtt_port, 60)
            print("Connexion localhost initialisée")
        except Exception as e2:
            print(f"ERREUR connexion localhost: {e2}")
            print("Continuons sans MQTT pour le debug...")
            # Ne pas retourner, continuer pour tester la chaudière
    
    client.loop_start()
    time.sleep(5)  # Attendre plus longtemps pour la connexion
    
    print("Démarrage surveillance Ungaro CTU A2 24...")
    
    # Boucle principale
    print("Démarrage de la boucle principale...")
    try:
        compteur = 0
        while True:
            compteur += 1
            print(f"\n--- Cycle {compteur} ---")
            
            # Interroger l'état de la chaudière
            print(f"Interrogation chaudière {adresse_ip}:{port_tcp}...")
            reponse = envoyer_commande_tcp(adresse_ip, port_tcp, "I30001000000000000")
            
            if reponse:
                print(f"Réponse reçue: {reponse}")
                code_etat, nom_etat = analyser_etat_chaudiere(reponse)
                
                if code_etat is not None:
                    print(f"État analysé: {code_etat} - {nom_etat}")
                    # Publier les états seulement si MQTT fonctionne
                    try:
                        client.publish("ungaro/etat/code", str(code_etat), retain=True)
                        client.publish("ungaro/etat/nom", nom_etat, retain=True)
                        print(f"État publié sur MQTT")
                    except Exception as e:
                        print(f"Erreur publication MQTT: {e}")
                else:
                    print("ERREUR: Réponse invalide de la chaudière")
            else:
                print("ERREUR: Pas de réponse de la chaudière")
            
            print(f"Attente {intervalle_maj}s avant prochain cycle...")
            time.sleep(intervalle_maj)
            
    except KeyboardInterrupt:
        print("Arrêt demandé par l'utilisateur")
    except Exception as e:
        print(f"ERREUR dans la boucle principale: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("Nettoyage final...")
        try:
            client.loop_stop()
            client.disconnect()
        except:
            pass

if __name__ == "__main__":
    try:
        print("=== Démarrage Ungaro Monitor ===")
        main()
    except Exception as e:
        print(f"ERREUR FATALE: {e}")
        import traceback
        traceback.print_exc()
        print("Le script va s'arrêter...")
        time.sleep(10)  # Laisser le temps de voir l'erreur