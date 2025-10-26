import asyncio
import socket
import json
import os
from datetime import datetime
import logging

# Gestion des versions MQTT comme dans les addons officiels
mqtt_version = 'old'
try:
    from asyncio_mqtt import Client as MQTTClient
except ImportError:
    try:
        from aiomqtt import Client as MQTTClient
        mqtt_version = 'new'
    except ImportError:
        # Fallback vers paho-mqtt classique
        import paho.mqtt.client as mqtt
        MQTTClient = None
        mqtt_version = 'paho'

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

async def envoyer_commande_tcp(adresse, port, commande):
    """Envoie une commande TCP à la chaudière de manière asynchrone"""
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(adresse, port), timeout=5
        )
        
        # Format: 08 + commande_hex + 0d
        commande_hex = ''.join(f"{ord(c):02x}" for c in commande)
        trame_complete = f"08{commande_hex}0d"
        
        writer.write(bytes.fromhex(trame_complete))
        await writer.drain()
        
        reponse = await asyncio.wait_for(reader.read(1024), timeout=5)
        writer.close()
        await writer.wait_closed()
        
        if reponse:
            reponse_str = reponse.decode(errors='ignore').strip('\x08\r\n')
            logger.info(f"TCP {adresse}:{port} - {commande} -> {reponse_str}")
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

async def configurer_mqtt_discovery(client):
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
    
    try:
        # Publication des configurations
        await client.publish("homeassistant/sensor/ungaro_etat_code/config", 
                           json.dumps(config_etat_num), retain=True)
        await client.publish("homeassistant/sensor/ungaro_etat_nom/config", 
                           json.dumps(config_etat_nom), retain=True)
        
        # États initiaux
        await client.publish("ungaro/etat/code", "0", retain=True)
        await client.publish("ungaro/etat/nom", "Eteinte", retain=True)
        
        logger.info("MQTT Discovery configuré")
        
    except Exception as e:
        logger.error(f"Erreur configuration MQTT Discovery: {e}")

async def publier_etat_mqtt(client, code_etat, nom_etat):
    """Publie l'état sur MQTT de manière asynchrone"""
    try:
        await client.publish("ungaro/etat/code", str(code_etat), retain=True)
        await client.publish("ungaro/etat/nom", nom_etat, retain=True)
    except Exception as e:
        logger.error(f"Erreur publication MQTT: {e}")

async def surveiller_chaudiere(adresse_ip, port_tcp, intervalle_maj):
    """Boucle de surveillance de la chaudière"""
    while True:
        try:
            reponse = await envoyer_commande_tcp(adresse_ip, port_tcp, "I30001000000000000")
            
            if reponse:
                code_etat, nom_etat = analyser_etat_chaudiere(reponse)
                if code_etat is not None:
                    logger.info(f"État: {code_etat} - {nom_etat}")
                    return code_etat, nom_etat
                else:
                    logger.warning("Réponse chaudière invalide")
            else:
                logger.error("Chaudière non accessible")
                
        except Exception as e:
            logger.error(f"Erreur surveillance: {e}")
            
        await asyncio.sleep(intervalle_maj)

async def main():
    try:
        # Récupération des variables d'environnement
        adresse_ip = os.environ.get('ADRESSE_IP', '192.168.1.16')
        port_tcp = int(os.environ.get('PORT_TCP', '8899'))
        mqtt_host = os.environ.get('MQTT_HOST', 'core-mosquitto')
        mqtt_port = int(os.environ.get('MQTT_PORT', '1883'))
        mqtt_user = os.environ.get('MQTT_USER', '')
        mqtt_password = os.environ.get('MQTT_PASSWORD', '')
        intervalle_maj = int(os.environ.get('INTERVALLE_MAJ', '30'))
        
        logger.info(f"Ungaro CTU A2 24 - Surveillance {adresse_ip}:{port_tcp}")
        logger.info(f"Version MQTT: {mqtt_version}")
        
    except Exception as e:
        logger.error(f"Erreur configuration: {e}")
        return
    
    # Test initial de la chaudière
    test_reponse = await envoyer_commande_tcp(adresse_ip, port_tcp, "I30001000000000000")
    if not test_reponse:
        logger.error("Chaudière inaccessible - vérifiez l'adresse IP et le port")
        return
    
    # Gestion MQTT selon la version disponible
    if MQTTClient:
        # Utilisation d'asyncio-mqtt ou aiomqtt
        try:
            async with MQTTClient(hostname=mqtt_host, port=mqtt_port, 
                                username=mqtt_user if mqtt_user else None,
                                password=mqtt_password if mqtt_password else None) as client:
                
                logger.info("MQTT connecté avec asyncio")
                await configurer_mqtt_discovery(client)
                
                # Boucle principale
                while True:
                    reponse = await envoyer_commande_tcp(adresse_ip, port_tcp, "I30001000000000000")
                    
                    if reponse:
                        code_etat, nom_etat = analyser_etat_chaudiere(reponse)
                        if code_etat is not None:
                            logger.info(f"État: {code_etat} - {nom_etat}")
                            await publier_etat_mqtt(client, code_etat, nom_etat)
                    
                    await asyncio.sleep(intervalle_maj)
                    
        except Exception as e:
            logger.error(f"Erreur MQTT asyncio: {e}")
            # Fallback: surveillance sans MQTT
            await surveiller_chaudiere(adresse_ip, port_tcp, intervalle_maj)
    else:
        # Pas de client MQTT asyncio disponible
        logger.warning("Fonctionnement sans MQTT - bibliothèque asyncio-mqtt non disponible")
        await surveiller_chaudiere(adresse_ip, port_tcp, intervalle_maj)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Arrêt demandé")
    except Exception as e:
        logger.error(f"Erreur fatale: {e}")
        import traceback
        traceback.print_exc()