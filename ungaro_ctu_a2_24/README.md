# Ungaro CTU A2 24

Addon Home Assistant pour l'intégration de la chaudière **Ungaro CTU A2 24** via communication TCP.

## Fonctionnalités

- **Surveillance complète** : Monitoring en temps réel de tous les paramètres
- **Contrôle à distance** : Marche/arrêt, réglage consigne, RAZ erreurs
- **MQTT Discovery** : Intégration automatique dans Home Assistant
- **Noms français** : Interface entièrement en français
- **Configuration simple** : Paramétrage via l'interface HA
- **États personnalisables** : Fichiers de configuration modifiables

## Capteurs disponibles

### État et Erreurs
- **État Chaudière (Code)** : Code numérique de l'état
- **État Chaudière** : Nom explicite de l'état en français
- **Erreur Chaudière (Code)** : Code numérique de l'erreur
- **Erreur Chaudière** : Description de l'erreur en français

### Températures
- **Température Fumée** : Température des fumées (°C)
- **Température Eau** : Température de l'eau (°C)
- **Température Consigne Eau** : Consigne de température (°C)

### Autres Paramètres
- **Puissance Combustion** : Niveau de puissance (0-9)
- **Pression Eau** : Pression du circuit eau (bar)

## Contrôles disponibles

### Commandes
- **Mise en Marche** : Démarrage de la chaudière
- **Arrêt** : Arrêt de la chaudière
- **RAZ Code Erreur** : Remise à zéro des codes d'erreur

### Réglages
- **Réglage Consigne Eau** : Modification de la température de consigne (45-75°C)

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

Une fois l'addon démarré, les entités suivantes apparaîtront automatiquement dans Home Assistant :

### Capteurs
- `sensor.etat_chaudiere_code` et `sensor.etat_chaudiere`
- `sensor.erreur_chaudiere_code` et `sensor.erreur_chaudiere`
- `sensor.temperature_fumee`
- `sensor.temperature_eau`
- `sensor.temperature_consigne_eau`
- `sensor.puissance_combustion`
- `sensor.pression_eau`

### Contrôles
- `number.reglage_consigne_eau` : Réglage 45-75°C
- `button.mise_en_marche` : Démarrage
- `button.arret` : Arrêt
- `button.raz_code_erreur` : Reset erreurs

Toutes ces entités peuvent être utilisées dans vos automatisations, cartes et scripts.

## Personnalisation des états et erreurs

### États de la chaudière
Les états sont définis dans le fichier `etats_chaudiere.json` :
```json
{
  "000": "Eteinte",
  "001": "Controle Interne",
  "042": "Nouvel état découvert"
}
```

### Erreurs de la chaudière
Les erreurs sont définies dans le fichier `erreurs_chaudiere.json` :
```json
{
  "0": "Non",
  "1": "Sonde température fumée",
  "19": "Nouvelle erreur découverte"
}
```

Pour modifier ces fichiers :
1. Accédez au conteneur de l'addon
2. Modifiez `/app/etats_chaudiere.json` ou `/app/erreurs_chaudiere.json`
3. Redémarrez l'addon

## Protocole TCP

### Lecture des données
- **État** : `I30001000000000000` → `J30001000000000XXX`
- **Erreur** : `I30002000000000000` → `J300020000000000XX`
- **Température fumée** : `I30005000000000000` → `J30005000000000XXX`
- **Puissance combustion** : `I30011000000000000` → `J30011000000000XXX`
- **Température eau** : `I30017000000000000` → `J30017000000000XXX`
- **Pression eau** : `I30020000000000000` → `J30020000000001XXX`
- **Consigne eau** : `A20180000000000000` → `B20180000000000XXX`

### Commandes de contrôle
- **Mise en marche** : `J30253000000000001` → `I30253000000000000`
- **Arrêt** : `J30254000000000001` → `I30254000000000000`
- **RAZ erreur** : `J30255000000000001` → `I30255000000000000`
- **Réglage consigne** : `B20180000000000XXX` → `A20180000000000XXX`

- **Port par défaut** : 8899

## Version

**3.1.0** - Suite complète de capteurs et contrôles
- Monitoring complet : état, erreurs, températures, pression, puissance
- Contrôles : marche/arrêt, réglage consigne, RAZ erreurs
- États et erreurs personnalisables via fichiers JSON
