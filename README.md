# Flipr Pool Control pour Home Assistant (v5.7.3)

[![license](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
![HACS](https://img.shields.io/badge/HACS-Custom-orange)
![Version](https://img.shields.io/badge/version-5.7.3-blue)

Intégration universelle et complète pour Home Assistant dédiée aux analyseurs de piscine et spas **Flipr** (AnalysR, Start, Start Max) et aux boîtiers de contrôle de pompe **Flipr Hub / Control**.

Elle combine les données du **Cloud GoFlipr** et du **Bluetooth Low Energy (BLE) local** avec fusion automatique en temps réel, calculs chimiques avancés (LSI, HOCl, Doses pH/Chlore/TAC), gestion intelligente du Hub et un **panneau latéral natif dédié**.

---

## 🚀 Nouveau : Panneau Latéral Intégré (v5.7.0)

Dès l'installation de l'intégration, un nouvel onglet **« Flipr Pool Control »** apparaît automatiquement dans la barre latérale gauche de votre Home Assistant :
- 📱 **Double Vue Officielle Flipr** : Bascule instantanée entre la vue **Analyse** (jauges pH/Redox, météo, statut eau) et la vue **Contrôle** (gestion pompe, historiques 7 jours, prévisions météo).
- 💡 **Volet Conseils d'Entretien & Traitements** : Recommandations précises de dosages (pH+, pH-, Chlore choc, Chlore entretien), équilibre de l'eau (LSI/Langelier), et optimisation des heures de filtration.
- ⚡ **Pilotage interactif** : Marche/Arrêt de la filtration directement depuis le panneau.

---

## 🎨 Cartes de Dashboard Lovelace (Dossier `examples`)

Dans le répertoire `examples/` de cette intégration, vous trouverez des exemples prêts à l'emploi pour recréer l'interface de l'application officielle Flipr directement dans votre Dashboard Home Assistant !

- **`flipr_official_app_analyse.yaml`** : Une carte détaillée type jauge affichant vos couleurs cibles pour le pH et le Chlore, les températures et des conseils d'entretien dynamiques.
- **`flipr_official_app_controle.yaml`** : Une carte reprenant le même design mais axée sur le pilotage manuel de la pompe via le Flipr Hub.

**Note :** Le code de ces cartes utilise `custom:button-card`. Pour l'utiliser, il vous suffit de copier/coller le code YAML dans votre tableau de bord. La carte s'adaptera automatiquement au nom de votre entité Flipr (grâce à un préfixe dynamique).

---

## ✨ Les 6 Catégories d'Entités (v5.6.0)

Toutes les entités créées dans Home Assistant sont automatiquement organisées et rangées selon 6 thématiques claires :

### 1. 💧 Mesures Instantanées de la Piscine
- 🌡️ **Température de l'eau** (°C)
- ⚗️ **pH** (Valeur numérique)
- 🟢 **Statut pH** (*OK / KO* + message explicatif)
- ⚡ **Potentiel Redox** (mV)
- 🧪 **Désinfectant (Chlore)** (mg/L)
- 🔴 **Statut Chlore** (*OK / KO* + message explicatif)
- 💧 **Conductivité** (µS/cm)
- 🌊 **État de l'eau** (*ex: Parfait, Légèrement trouble...*)
- 🕒 **Dernière mesure** (Horodatage de la prise de valeur)

### 2. 🌤️ Météo & Conditions Extérieures
- 🌡️ **Température de l'air** (°C)
- 📈 **Température de l'air (+1h)** (°C)
- ☀️ **Indice UV** (Arrondi propre à 1-2 décimales)
- ☁️ **Couverture nuageuse** (%)
- 🌦️ **Météo actuelle** (*ex: clear-day, cloudy...*)

### 3. 🔮 Prévisions Météo
- 💨 **Vitesse du vent** (km/h)
- 🌧️ **Probabilité de pluie** (%)
- 🔺 **Température air Max (Aujourd'hui)** (°C)
- 🔻 **Température air Min (Aujourd'hui)** (°C)

### 4. 📈 Prévisions de Température de l'Eau
- 🌊 **Température eau prévue (+1h)** (°C)
- 📅 **Température eau prévue (Demain)** (°C)

### 5. 📜 Moyennes & Calculs Chimie
- 📊 **Moyennes récentes** : pH moyen, Redox moyen, Température eau moyenne
- ⚖️ **Indice LSI** (Langelier Saturation Index) — *Équilibre de l'eau*
- 🏷️ **Statut de l'eau (LSI)** — *corrosive, équilibrée, entartrante*
- 📐 **pH d'Équilibre** ($pH_s$)
- 🧪 **Chlore Libre Estimé** (mg/L)
- 🦠 **Chlore Actif (HOCl)** (mg/L - Forme biocide active)
- 💊 **Doses de correction calculées** :
  - **Dose pH-** (Bisulfate de sodium en g)
  - **Dose pH+** (Carbonate de sodium en g)
  - **Dose TAC+ (Bicarbonate)** (Alca-Plus / Bicarbonate de sodium en g)
  - **Dose Chlore Entretien** (g)
  - **Dose Chlore Choc** (g)
- ⏱️ **Durée de filtration recommandée** (heures) & **Conseil Filtration**
- 🏊 **Volume de la piscine** (Litres / m³)

### 6. ⚙️ Appareil & Statut Matériel
- 🔋 **Niveau de Batterie** (%)
- 🛠️ **Étalonnage des sondes requis** (Binary Sensor : ON si calibration nécessaire)
- 💳 **Abonnement Flipr** (Binary Sensor : ON si valide)
- 📱 **Modèle Flipr** (*AnalysR, Start, Start Max...*)
- 🔢 **Version du Firmware**
- 📶 **Statut réseau Sigfox** (*Active / Inactive*)
- 🔄 **Compteur de redémarrages** (*Resets Counter*)
- ☁️ **Dernier contact Cloud** (Horodatage UTC)
- 🚨 **Dernière Alerte**
- 🔀 **Source des données** (*Cloud API* ou *Bluetooth BLE*)
- 📡 **Signal BLE & Statut BLE** (RSSI en dBm)
- ℹ️ **Version de l'intégration** (`5.6.0`)

---

## 🔌 Contrôle du Hub & Gestion de la Pompe

Pour les utilisateurs équipés du boîtier **Flipr Hub / Control** :
- ⚙️ **Découverte Automatique (Améliorée)** : Le système scanne tous vos modules et teste silencieusement l'API pour découvrir avec 100% de fiabilité le Hub de contrôle (contournement des identifiants trompeurs de l'API Flipr).
- 🔲 **Switch Pompe** (`switch.flipr_xxx_pump_filtration`) : Allume et éteint la pompe de filtration (Marche Forcée). Bascule automatiquement le Hub en mode Manuel avant la commande.
- 🎛️ **Sélecteur de Mode** (`select.flipr_xxx_mode_filtration`) : Permet de choisir entre **Auto**, **Manuel** et **Planning**.

---

## 📡 Architecture Hybride Cloud + BLE

- ☁️ **Cloud** : Polling périodique de l'API GoFlipr.
- 📡 **Bluetooth BLE** : Polling local passif/actif via le composant Bluetooth natif de Home Assistant.
- 🔀 **Fusion Automatique** : L'intégration compare en permanence la fraîcheur des données et affiche toujours la mesure la plus récente.

---

## 🛠️ Service de Diagnostic

Un service personnalisé est disponible dans Home Assistant sous **Outils de développement > Services** :
- **`flipr_pool.dump_hub_debug`** : Exécute un diagnostic complet de votre compte Flipr et génère le fichier `/config/flipr_hub_debug.json` pour analyser la communication avec votre Hub.

---

## 📦 Installation

### Via HACS (Recommandé)
1. Ouvrez **HACS** dans Home Assistant.
2. Cliquez sur **⋮ > Dépôts personnalisés**.
3. Ajoutez l'URL : `https://github.com/SocrateMobile/Flipr_Pool`
4. Catégorie : **Intégration**
5. Téléchargez et redémarrez Home Assistant.

---

## 📜 Historique des Versions (Changelog)

### v5.6.0 — Correctif majeur Hub
- 🔧 **Refonte complète de la chaîne Hub** : 
  - Le `hub_id` découvert est désormais **persisté** dans les options de l'intégration (plus besoin de redécouvrir à chaque redémarrage).
  - Suppression de la double normalisation des données Hub qui causait la perte des clés `behavior` et `stateEquipment`.
  - Parsing robuste qui accepte TOUTES les variantes de clés possibles (`behavior`/`Mode`/`mode`, `stateEquipment`/`Status`/`State`).
  - Logging détaillé pour diagnostic en cas de problème.

### v5.4.4
- 🛠️ **Nouvelle Action (Service)** : Ajout de l'action `flipr_pool.dump_entities` qui permet d'exporter la liste de toutes vos entités Flipr dans un fichier `flipr_card_list.json` pour vous aider à les copier/coller plus facilement lors de la configuration de votre carte Lovelace !

### v5.4.3
- 🛠️ **Correctif d'état de Pompe (unknown)** : L'API Flipr a secrètement modifié ses clés de données (`behavior` au lieu de `Mode`, et `stateEquipment` au lieu de `Status`). Le parsing a été mis à jour, les interrupteurs ne reviennent plus à "off" après 2 secondes !

### v5.4.2
- 🎯 **Super Découverte Automatique du Hub** : Remplacement de la détection hasardeuse par type d'appareil par un véritable "Ping" silencieux de l'API Flipr (évite les erreurs où Flipr masque le type du Hub). La pompe est désormais garantie de fonctionner !

### v5.4.0 & v5.4.1
- 🛡️ **Fix Rate-limit (429)** : Ajout d'une pause dynamique dans l'outil de diagnostic du Hub (`dump_hub_debug`) pour éviter les blocages API Flipr.
- 🎨 **Cartes Lovelace** : Intégration de cartes Dashboard premium (type application officielle) avec adaptation automatique au nom de l'entité et couleurs de cibles. Documentation et fichiers disponibles dans `examples/`.

### v5.3.0
- 🎯 **Auto-détection du Hub** via `ModuleType_Id = 3` (Flipr Control / Hub).
- 🔄 **Fiabilisation de la pompe** : fallback d'URLs et passage préalable en mode manuel.
- ⚙️ **Capteurs matériels supplémentaires** : Statut Sigfox, Compteur de Reboots, Dernier contact Cloud.

### v5.1.2 & v5.1.3
- 💊 **Dose TAC+ (Bicarbonate de Sodium)** : Calcul de la dose recommandée pour remonter l'alcalinité à 120 mg/L (12°f).
- 🌍 **Internationalisation à 100%** : Traduction complète dans 7 langues (*Français, Anglais, Espagnol, Italien, Allemand, Néerlandais, Portugais*).

### v5.1.0 & v5.1.1
- 🗂️ **Organisation en 6 Thèmes** : Rangement de toutes les entités du dashboard.
- 🌤️ **Données météo & prévisions** : Températures min/max, vitesse du vent, probabilité de pluie, couverture nuageuse.
- ☀️ **Correction d'arrondi UV** : Indice UV propre à 1-2 décimales.

### v5.0.0 à v5.0.2
- 🛠️ Refonte globale du client API GoFlipr et correction des appels OAuth2.
- 📡 Correction du client BLE `bleak-retry-connector`.

---

## 🤝 Remerciements & Crédits

Un immense merci aux créateurs et pionniers des premières intégrations Flipr pour la communauté Home Assistant, dont le travail a grandement inspiré ce projet :
- **`flipr`** par **@cnico** : Pour la première intégration Cloud et la découverte de l'API GoFlipr.
- **`flipr_local`** par **@Adrien40** : Pour le travail d'ingénierie inverse du protocole Bluetooth Low Energy (BLE) et l'analyse des caractéristiques GATT du Flipr.

---

## 📄 Licence

MIT License — Voir le fichier [LICENSE](LICENSE) pour plus de détails.
