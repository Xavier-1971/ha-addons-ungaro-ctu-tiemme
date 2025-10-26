# Home Assistant Add-ons: Ungaro CTU Tiemme

Dépôt d'addons Home Assistant pour les chaudières Ungaro CTU et Tiemme.

## Add-ons disponibles

### Ungaro CTU A2 24

Intégration pour chaudière **Ungaro CTU A2 24** via communication TCP.

#### Fonctionnalités
- **Surveillance d'état** : Monitoring en temps réel de l'état de la chaudière
- **MQTT Discovery** : Intégration automatique dans Home Assistant
- **Noms français** : Interface entièrement en français
- **Configuration simple** : Paramétrage via l'interface HA

#### Capteurs disponibles
- **État Chaudière (Code)** : Code numérique de l'état
- **État Chaudière** : Nom explicite de l'état en français

#### États supportés
- **000** : Arrêt
- **001** : Check Up  
- **030-033** : Allumage (différentes phases)
- **005** : Montée en température
- **006** : Modulation
- **007** : Extinction
- **008** : Sécurité
- **009** : Bloquée
- **010** : Récupération
- **011** : Standby
- **110** : Passage en arrêt
- **255** : Passage en marche

#### Configuration
- **adresse_ip** : Adresse IP de la chaudière (défaut: 192.168.1.16)
- **port_tcp** : Port TCP (défaut: 8899)
- **mqtt_host** : Serveur MQTT (défaut: core-mosquitto)
- **mqtt_port** : Port MQTT (défaut: 1883)
- **mqtt_user** : Utilisateur MQTT (optionnel)
- **mqtt_password** : Mot de passe MQTT (optionnel)
- **intervalle_maj** : Intervalle de mise à jour en secondes (10-300, défaut: 30)

## Installation

1. **Ajoutez ce dépôt** à vos sources d'addons HA :
   ```
   https://github.com/Xavier-1971/ha-addons-ungaro-ctu-tiemme
   ```

2. **Installez** "Ungaro CTU A2 24" depuis le Store

3. **Configurez** les paramètres réseau de votre chaudière

4. **Démarrez** l'addon

## Utilisation

Une fois l'addon démarré, deux capteurs apparaîtront automatiquement dans Home Assistant :
- `sensor.etat_chaudiere_code` : Code numérique
- `sensor.etat_chaudiere` : État en français

Ces capteurs peuvent être utilisés dans vos automatisations, cartes et scripts.

## Version

**1.0.0** - Version initiale avec surveillance d'état de base

## Support

Pour toute question ou problème, ouvrez une issue sur GitHub.