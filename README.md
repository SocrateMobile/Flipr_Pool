# 🏊 Flipr Pool Control for Home Assistant (v3.0.0)

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![version](https://img.shields.io/badge/version-3.0.0-blue.svg)](https://github.com/SocrateMobile/flipr_pool/releases)
[![license](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

Intégration personnalisée pour les analyseurs de piscine **Flipr**. Récupère les mesures en temps réel via le **Cloud** et/ou le **Bluetooth local (BLE)**, calcule les doses de traitement et la filtration optimale.

---

## ✨ Caractéristiques

### Mesures
| Capteur | Source |
|---------|--------|
| 🌡️ Température eau / air | Cloud + BLE |
| ⚗️ pH + statut | Cloud + BLE |
| ⚡ Redox (ORP) | Cloud + BLE |
| 🧪 Chlore + statut | Cloud + BLE |
| 🔋 Batterie | Cloud + BLE |
| 💧 Conductivité | Cloud + BLE |
| ☀️ Indice UV | Cloud |

### Calculs automatiques (v2.0+)
- **Doses de correction** : pH− (bisulfate), pH+ (carbonate), Chlore entretien, Chlore choc
- **Durée de pompe optimale** basée sur la température et la qualité de l'eau
- **Conseils de filtration** contextuels

### Chimie avancée (v2.0+)
- **Indice LSI** (Langelier Saturation Index) — équilibre corrosif/entartrant
- **pH d'équilibre** calculé
- **Chlore libre estimé** (à partir du Redox et du pH)
- **Chlore actif HOCl** (forme biocide efficace)

### 🆕 Double Coordinateur Cloud + BLE (v3.0.0)
- ☁️ **Cloud** : API GoFlipr, interrogé toutes les **15 minutes**
- 📡 **BLE** : Bluetooth local, interrogé toutes les **60 minutes** (économie batterie)
- 🔀 **Fusion automatique** : les entités affichent toujours la donnée **la plus récente**
- 🔌 **Switch ON/OFF** pour activer/désactiver le Bluetooth depuis le dashboard
- 📊 Capteur **"Source Active"** : indique `cloud` ou `bluetooth`
- 📶 Capteur **"BLE Signal"** : RSSI en dBm pour diagnostiquer la portée
- 🔍 **Scan BLE automatique** dans les options : détecte les Flipr à portée avec modèle et numéro de série
- 🔎 **Découverte automatique des appareils** du compte Cloud (Flipr + Hub) lors de l'installation
- ✅ Supporte le **Flipr Classique** (notification GATT) et le **Start Max** (connexion 35s)

---

## 📦 Installation

### Via HACS (recommandé)
1. Ouvrez HACS dans Home Assistant
2. Cliquez sur **⋮ > Dépôts personnalisés**
3. Ajoutez : `https://github.com/SocrateMobile/flipr_pool`
4. Catégorie : **Intégration**
5. Recherchez **Flipr Pool Control** et installez
6. Redémarrez Home Assistant

### Manuellement
1. Copiez le dossier `custom_components/flipr_pool/` dans votre répertoire `config/custom_components/`
2. Redémarrez Home Assistant
3. **Paramètres > Appareils et Services > Ajouter une intégration > Flipr Pool Control**

---

## ⚙️ Configuration

### Étape 1 — Connexion au compte
Entrez votre **email** et **mot de passe** Flipr. L'intégration se connecte automatiquement à l'API GoFlipr.

### Étape 2 — Sélection de l'appareil
L'intégration liste automatiquement **tous les appareils** (Flipr et Hub) liés à votre compte. Sélectionnez celui à surveiller.

> Si la découverte automatique échoue, un formulaire de saisie manuelle du numéro de série apparaît.

### Options (après installation)

Via le bouton **Configurer** sur la carte de l'intégration :

| Option | Description |
|--------|-------------|
| Longueur / Largeur / Profondeur | Dimensions de la piscine en mètres |
| TAC | Alcalinité totale (ppm) |
| TH | Dureté (ppm) |
| CYA | Stabilisant / acide cyanurique (ppm) |
| TDS | Sels dissous (ppm) |
| BLE activé | Active le coordinateur Bluetooth local |
| Adresse BLE | Adresse MAC du Flipr BLE |
| Scanner BLE | Lance un scan BLE pour détecter les Flipr à portée |

---

## 📡 Configuration Bluetooth (BLE)

### Prérequis
- Un contrôleur Bluetooth sur le serveur Home Assistant (Raspberry Pi, clé USB BLE...)
- Le Flipr doit être à portée Bluetooth (~10m en intérieur)

### Activer le BLE

**Méthode 1 — Via les Options :**
1. **Configurer** > Cocher **"Scanner les appareils BLE"**
2. Sélectionner votre Flipr dans la liste (avec modèle, série, MAC et RSSI)
3. L'adresse MAC et le mode BLE sont automatiquement configurés

**Méthode 2 — Via le Switch :**
Basculer le switch **"Flipr Mode Bluetooth (BLE)"** dans votre dashboard.

### Modèles supportés

| Modèle | Nom BLE | Méthode |
|--------|---------|---------|
| **Classique** | `Flipr-XXXX` | Notification GATT (instantanée) |
| **Start Max** | `F30-XXXX`, `F2B-XXXX` | Connexion 35 secondes + lecture directe |

Le modèle est détecté automatiquement lors du scan BLE.

---

## 🔧 Entités créées

### Capteurs
| Nom | Clé | Unité |
|-----|-----|-------|
| Température Eau | `temperature` | °C |
| pH | `ph` | pH |
| Statut pH | `ph_status` | — |
| Redox | `redox` | mV |
| Batterie | `battery` | % |
| Conductivité | `conductivity` | µS/cm |
| Indice UV | `uv_index` | UV |
| Température Air | `air_temp` | °C |
| État de l'eau | `water_state` | — |
| Chlore | `chlorine` | mg/L |
| Statut Chlore | `chlorine_status` | — |
| Dernière Mesure | `last_update` | timestamp |
| Volume Piscine | `pool_volume` | L |
| Dose pH− | `dose_ph_minus` | g |
| Dose pH+ | `dose_ph_plus` | g |
| Dose Chlore (Entretien) | `dose_cl_maint` | g |
| Dose Chlore (Choc) | `dose_cl_shock` | g |
| Durée Pompe | `pump_hours` | h |
| Conseil Filtration | `conseil_filtration` | — |
| Dernière Alerte | `last_alert` | — |
| Indice LSI | `lsi` | — |
| Statut Eau (LSI) | `lsi_status` | — |
| pH Équilibre | `ph_equilibre` | pH |
| Chlore Libre Est. | `free_chlorine` | mg/L |
| Chlore Actif HOCl | `active_chlorine` | mg/L |
| Source Active | `data_source` | — |
| BLE Signal | `ble_rssi` | dBm |
| BLE Statut | `ble_status` | — |

### Switches
| Nom | Description |
|-----|-------------|
| Flipr Pompe Filtration | Marche forcée de la pompe (via API Hub) |
| Flipr Mode Bluetooth (BLE) | Active/désactive la connexion BLE locale |

### Select
| Nom | Options |
|-----|---------|
| Flipr Mode Filtration | `auto`, `manual`, `off`, `planning` |

### Number (réglables)
| Nom | Plage |
|-----|-------|
| Seuil pH Min / Max | 6.0 – 9.0 |
| Seuil Chlore Min / Max | 0.0 – 5.0 |
| Longueur / Largeur / Profondeur | 0.0 – 50.0 m |

---

## 📐 Doses de traitement

Les calculs utilisent les constantes suivantes (modifiables dans `const.py`) :

| Paramètre | Valeur |
|-----------|--------|
| pH cible | 7.4 |
| Chlore cible (entretien) | 2.0 mg/L |
| Chlore cible (choc) | 5.0 mg/L |
| Dose pH− (bisulfate) | 100 g/m³/unité pH |
| Dose pH+ (carbonate) | 150 g/m³/unité pH |
| Dose chlore choc 70% | 1.5 g/m³/(mg/L) |

---

## 📜 Changelog

### v3.0.0
- 🆕 Double coordinateur Cloud (15 min) + BLE (60 min) en parallèle
- 🆕 Fusion automatique : la mesure la plus récente gagne
- 🆕 Switch d'activation/désactivation du Bluetooth
- 🆕 Scan BLE automatique avec détection du modèle (Classique / Start Max) et du numéro de série
- 🆕 Découverte automatique des appareils du compte Cloud (Flipr + Hub)
- 🆕 Capteurs Source Active, BLE Signal (RSSI) et BLE Statut
- 🆕 Support du Flipr Start Max (connexion 35 secondes)
- ✏️ Config flow multi-étapes avec sélection d'appareil
- ✏️ Options flow avec scan BLE intégré

### v2.0.0
- 🆕 Chimie avancée : Indice LSI, pH d'équilibre, Chlore libre/actif
- 🆕 Calculateur de doses (pH−, pH+, Chlore entretien/choc)
- 🆕 Durée de pompe et conseils de filtration
- 🆕 Persistance locale (Store)
- 🆕 Options flow pour TAC/TH/CYA/TDS

### v1.0.0
- Version initiale : mesures Cloud, switch pompe, seuils réglables

## 🤝 Remerciements & Crédits

Un grand merci aux créateurs et contributeurs des projets suivants pour leur travail inspirant qui sert de base à cette version **Flipr Pool Control** :
* **`flipr`** (Intégration Cloud) : Pour la structure initiale et les appels de l'API Cloud officielle GoFlipr.
* **`flipr_local`** (Intégration BLE) : Pour l'analyse du protocole Bluetooth Low Energy, le décodage binaire des trames GATT et la gestion de la connexion matérielle locale.

---

## 📄 Licence

MIT License — voir le fichier [LICENSE](LICENSE) pour plus de détails.

---

**Made with ❤️ for the Home Assistant community**
