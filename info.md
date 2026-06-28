# Flipr Pool Control

Cette intégration personnalisée pour Home Assistant vous permet de remonter l'ensemble des données de votre analyseur d'eau **Flipr**. 

Elle est unique car elle propose **3 modes de fonctionnement** :
1. **Cloud Exclusif** : Idéal si vous avez l'abonnement Premium ou un Flipr Hub (Wifi).
2. **Hybride (Cloud + Bluetooth)** : Recommandé ! Récupère l'historique et les alertes via le Cloud, tout en scannant localement (BLE) le Flipr s'il est à portée de votre antenne Bluetooth, offrant des mises à jour gratuites et instantanées.
3. **Bluetooth Exclusif (Déconseillé)** : Fonctionne de manière 100% locale sans Cloud (perte des algorithmes avancés de Flipr, de l'historique et du Hub).

## Fonctionnalités
- ✨ **Capteurs Principaux** : Température de l'eau, pH, Redox, Chlore.
- 🧪 **Chimie Avancée** : Indice LSI (Équilibre de l'eau), Chlore Libre Estimé, Chlore Actif (HOCl), pH d'équilibre.
- ⚙️ **Gestion du Hub** : Allumez ou éteignez la filtration (Marche Forcée), changez les modes (Auto, Planning, Manuel).
- 💊 **Conseils de dosage** : Remonte les recommandations de dosage (pH-, pH+, Chlore Choc) directement dans HA.
- 🔋 **Diagnostics** : Niveau de batterie, Indice UV, Température de l'air, Force du signal BLE (RSSI).

## Prérequis pour le Bluetooth
Si vous souhaitez utiliser la fonctionnalité Bluetooth (Hybride ou Local) :
- Vous devez avoir le composant Bluetooth natif de Home Assistant configuré (Dongle USB, ESP Bluetooth Proxy, etc.).
- Votre Flipr doit être à portée de l'antenne Bluetooth.
