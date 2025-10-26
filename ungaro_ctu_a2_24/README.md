# Ungaro CTU A2 24

Addon Home Assistant pour l'intégration de la chaudière **Ungaro CTU A2 24** via communication TCP.

## Fonctionnalités

- **Surveillance d'état** : Monitoring en temps réel de l'état de la chaudière
- **MQTT Discovery** : Intégration automatique dans Home Assistant
- **Noms français** : Interface entièrement en français
- **Configuration simple** : Paramétrage via l'interface HA
- **États personnalisables** : Fichier de configuration modifiable

## Capteurs disponibles

### État Chaudière
- **État Chaudière (Code)** : Code numérique de l'état
- **État Chaudière** : Nom explicite de l'état en français

### États supportés
- **000** : Eteinte
- **001** : Controle Interne
- **030-033** : Allumage (différentes phases)
- **005** : Montée en température
- **006** : Modulation
- **007** : Extinction
- **008** : Mode sécurité
- **009** : Bloquage
- **010** : Récupération
- **011** : Standby
- **Autres** : Inconnu

## Configuration

- **adresse_ip** : Adresse IP de la chaudière (défaut: 192.168.1.16)
- **port_tcp** : Port TCP (défaut: 8899)
- **mqtt_host** : Serveur MQTT (défaut: core-mosquitto)
- **mqtt_port** : Port MQTT (défaut: 1883)
- **mqtt_user** : Utilisateur MQTT (optionnel)
- **mqtt_password** : Mot de passe MQTT (optionnel)
- **intervalle_maj** : Intervalle de mise à jour en secondes (10-300, défaut: 30)

## Installation

1. Ajoutez ce dépôt à vos sources d'addons HA :
   `https://github.com/Xavier-1971/ha-addons-ungaro-ctu-tiemme`
2. Installez "Ungaro CTU A2 24"
3. Configurez les paramètres réseau
4. Démarrez l'addon

## Utilisation

Une fois l'addon démarré, deux capteurs apparaîtront automatiquement dans Home Assistant :
- `sensor.etat_chaudiere_code` : Code numérique
- `sensor.etat_chaudiere` : État en français

Ces capteurs peuvent être utilisés dans vos automatisations, cartes et scripts.

## Personnalisation des états

Les états de la chaudière sont définis dans le fichier `etats_chaudiere.json`. Pour ajouter de nouveaux états :

1. Accédez au conteneur de l'addon
2. Modifiez `/app/etats_chaudiere.json`
3. Redémarrez l'addon

Exemple :
```json
{
  "000": "Eteinte",
  "042": "Nouvel état découvert"
}
```

## Protocole TCP

- **Commande envoyée** : `I30001000000000000`
- **Réponse attendue** : `J30001000000000XXX` (XXX = code état)
- **Port par défaut** : 8899

## Version

**1.0.4** - États personnalisables via fichier JSON
