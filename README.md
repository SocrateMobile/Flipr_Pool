# Flipr Pool Control pour Home Assistant

![Version](https://img.shields.io/badge/version-3.2.1-blue)
![HACS](https://img.shields.io/badge/HACS-Custom-orange)

Cette intégration non officielle pour Home Assistant permet de connecter votre analyseur d'eau **Flipr** et (optionnellement) votre **Flipr Hub**.

Contrairement aux autres intégrations, celle-ci offre une architecture **Hybride**. Elle se connecte à la fois à l'API Cloud de Flipr (pour récupérer les algorithmes de LSI, de chlore actif et l'historique) ET écoute en direct votre antenne Bluetooth locale. Dès que vous passez à côté de la piscine avec votre téléphone (ce qui déclenche le Bluetooth du Flipr), Home Assistant capte la mesure immédiatement, sans attendre la prochaine synchronisation cloud de votre abonnement (souvent limitée à 1 ou 2 fois par jour sans abonnement premium) !

## 🚀 Fonctionnalités
- ✨ **Capteurs Principaux** : Température, pH, Redox, Chlore, Conductivité.
- 🧪 **Chimie Avancée** : Indice LSI (Équilibre de l'eau), Chlore Libre Estimé, Chlore Actif (HOCl), pH d'équilibre.
- ⚙️ **Gestion du Hub** : Allumez ou éteignez la filtration (Marche Forcée), changez les modes (Auto, Planning, Manuel).
- 💊 **Conseils de dosage** : Remonte les recommandations de dosage directement.
- 🔋 **Diagnostics techniques** : Niveau de batterie, Force du signal BLE (RSSI), Source de la dernière donnée.

## 📦 Installation via HACS

C'est la méthode recommandée.
1. Ouvrez **HACS** dans Home Assistant.
2. Cliquez sur le menu en haut à droite (3 points) et choisissez **Dépôts personnalisés** (Custom repositories).
3. Ajoutez l'URL de votre dépôt GitHub (`https://github.com/SocrateMobile/Flipr_Pool`).
4. Catégorie : **Intégration**.
5. Cliquez sur Ajouter, puis recherchez "Flipr Pool" dans HACS et cliquez sur Télécharger.
6. Redémarrez Home Assistant.

## ⚙️ Configuration

1. Dans Home Assistant, allez dans **Paramètres** -> **Appareils et services**.
2. Cliquez sur **+ Ajouter une intégration** en bas à droite.
3. Cherchez **Flipr Pool**.
4. Suivez l'assistant de configuration. Nous vous conseillons fortement le mode **Cloud + Bluetooth (Hybride)**.

## 📁 Structure du projet pour HACS
Si vous êtes le développeur de ce dépôt, assurez-vous que la structure de votre projet sur GitHub est la suivante :
```
├── README.md
├── info.md
├── hacs.json
└── custom_components/
    └── flipr_pool/
        ├── __init__.py
        ├── manifest.json
        ├── api.py
        ├── sensor.py
        └── ... (les autres fichiers python et json)
```

## 📜 Historique & Évolutions du Projet
Ce projet a connu plusieurs refontes majeures pour devenir l'intégration la plus complète pour Flipr :
- **V1 (Cloud Simple)** : Récupération basique des données via l'API Cloud (pH, Température, Redox).
- **V2 (Traitement & Chimie)** : Ajout des algorithmes de calculs avancés (Doses de traitement pH+/pH-/Chlore, temps de filtration, LSI, Chlore Actif) calculés localement sur base des paramètres de la piscine.
- **V3 (Architecture Hybride & HACS)** : Refonte asynchrone complète, gestion du Flipr Hub (contrôle de la pompe de filtration, marche forcée), anti-bannissement de l'API (Backoff Exponentiel), récupération des données Bluetooth Locales (BLE) en complément du Cloud, et compatibilité totale avec les standards HACS (Diagnostics, Catégories, Traductions i18n).

## 🙏 Remerciements et Projets Inspirants
Cette intégration s'appuie sur le formidable travail de la communauté domotique open-source. Un grand merci en particulier à :
- **Adrien40** et son projet [flipr_local](https://github.com/Adrien40/flipr_local) : Son travail d'ingénierie inverse sur le protocole Bluetooth Low Energy (BLE) du Flipr a été une source d'inspiration majeure pour la composante locale de cette intégration hybride.
- Tous les contributeurs et testeurs de la communauté Home Assistant Francophone qui ont aidé à affiner les algorithmes de traitement de l'eau.

## 📄 Licence
MIT License. Voir le fichier LICENSE pour plus de détails.
