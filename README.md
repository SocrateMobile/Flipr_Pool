# Flipr Pool Control pour Home Assistant (v3.2.1)

[![license](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
![HACS](https://img.shields.io/badge/HACS-Custom-orange)

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

### Calculs automatiques
- **Doses de correction** : pH− (bisulfate), pH+ (carbonate), Chlore entretien, Chlore choc
- **Durée de pompe optimale** basée sur la température et la qualité de l'eau
- **Conseils de filtration** contextuels

### Chimie avancée
- **Indice LSI** (Langelier Saturation Index) — équilibre corrosif/entartrant
- **pH d'équilibre** calculé
- **Chlore libre estimé** (à partir du Redox et du pH)
- **Chlore actif HOCl** (forme biocide efficace)

### 🆕 Architecture Hybride Cloud + BLE
- ☁️ **Cloud** : API GoFlipr, interrogé toutes les **15 minutes**
- 📡 **BLE** : Bluetooth local, interrogé toutes les **60 minutes** (économie batterie)
- 🔀 **Fusion automatique** : les entités affichent toujours la donnée **la plus récente**
- 🔌 **Switch ON/OFF** pour activer/désactiver le Bluetooth depuis le dashboard
- 📊 Capteur **"Source Active"** : indique `cloud` ou `bluetooth`
- 📶 Capteur **"BLE Signal"** : RSSI en dBm pour diagnostiquer la portée
- 🔍 **Scan BLE automatique** dans les options : détecte les Flipr à portée avec modèle et numéro de série
- 🔎 **Découverte automatique des appareils** du compte Cloud (Flipr + Hub) lors de l'installation

---

## 📦 Installation

### Via HACS (recommandé)
1. Ouvrez HACS dans Home Assistant
2. Cliquez sur **⋮ > Dépôts personnalisés**
3. Ajoutez l'URL : `https://github.com/SocrateMobile/Flipr_Pool`
4. Catégorie : **Intégration**
5. Recherchez **Flipr Pool** et installez
6. Redémarrez Home Assistant

### Manuellement
1. Copiez le dossier `custom_components/flipr_pool/` dans votre répertoire `config/custom_components/`
2. Redémarrez Home Assistant
3. **Paramètres > Appareils et Services > Ajouter une intégration > Flipr Pool**

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

---

## 🔧 Entités créées

*(Toutes les entités sont regroupées par catégories HACS : Capteurs, Configuration, Diagnostics).*

### Capteurs (Dashboard par défaut)
- Température Eau, pH (et statut), Redox, Chlore (et statut), Conductivité
- Doses (pH-, pH+, Chlore), Durée Pompe, LSI, HOCl

### Diagnostics
- Batterie, Température Air, Indice UV, Source Active, BLE Signal, Dernière Mise à Jour, Dernière Alerte.

### Contrôles (Hub)
- Switch : Marche Forcée Pompe, Activation BLE Local.
- Sélection : Mode de Filtration (Auto, Manuel, Planning).
- Configuration : Seuils pH/Chlore, Dimensions de la piscine.

---

## 📜 Changelog

### v3.2.1 (HACS & Internationalisation)
- 🌍 Traduction native (Français, Anglais, Espagnol, Italien) via `strings.json`
- 🗂️ Catégorisation officielle HACS (Diagnostic / Configuration) des entités
- 🔧 Création du module de Diagnostic sécurisé
- ✅ Conformité avec l'architecture de dépôt HACS (hacs.json, info.md)

### v3.0.0
- 🆕 Double coordinateur Cloud (15 min) + BLE (60 min) en parallèle
- 🆕 Fusion automatique : la mesure la plus récente gagne
- 🆕 Scan BLE automatique avec détection du modèle
- 🆕 Découverte automatique des appareils du compte Cloud (Flipr + Hub)

### v2.0.0
- 🆕 Chimie avancée : Indice LSI, pH d'équilibre, Chlore libre/actif
- 🆕 Calculateur de doses (pH−, pH+, Chlore entretien/choc)

## 🤝 Remerciements & Crédits

Un grand merci aux créateurs et contributeurs des projets suivants pour leur travail inspirant qui sert de base à cette version **Flipr Pool Control** :
* **`flipr`** (Intégration Cloud) par **@cnico** : Pour la structure initiale et les appels de l'API Cloud officielle GoFlipr.
* **`flipr_local`** (Intégration BLE) par **@Adrien40** : Pour l'analyse du protocole Bluetooth Low Energy, le décodage binaire des trames GATT et la gestion de la connexion matérielle locale.

---

## 📄 Licence

MIT License — voir le fichier [LICENSE](LICENSE) pour plus de détails.

---

**Made with ❤️ for the Home Assistant community**
