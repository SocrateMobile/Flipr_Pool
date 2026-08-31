# Flipr Pool Control (v5.7.2)

Cette intégration personnalisée pour Home Assistant vous permet de remonter l'ensemble des données de votre analyseur d'eau **Flipr** (AnalysR, Start, Start Max) et de piloter votre pompe via le **Flipr Hub / Control**.

 Elle propose **3 modes de fonctionnement** :
1. **Cloud Exclusif** : Idéal si vous avez l'abonnement Premium ou un Flipr Hub (Wifi).
2. **Hybride (Cloud + Bluetooth)** : Recommandé ! Récupère l'historique, les prévisions météo et les alertes via le Cloud, tout en scannant localement (BLE) le Flipr s'il est à portée de votre antenne Bluetooth.
3. **Bluetooth Exclusif** : Fonctionne de manière 100% locale sans Cloud (pour la prise de mesure directe sans abonnement).

## ✨ Fonctionnalités Principales (Organisées en 6 Thèmes)

- 💧 **Mesures Instantanées** : Température de l'eau, pH, Redox, Chlore, Conductivité, État de l'eau, Statuts explicatifs pH/Chlore.
- 🌤️ **Météo & Prévisions** : Température air actu/prévision, Indice UV, Pluie, Vent, Couverture nuageuse, Prévisions eau (+1h / demain).
- 🧪 **Chimie Avancée & Dosages** : Indice LSI (Équilibre corrosif/entartrant), pH d'équilibre, Chlore actif HOCl, Calcul des doses pH-, pH+, TAC+ (Bicarbonate de Sodium), Chlore entretien & choc, Durée de filtration calculée.
- 🔌 **Gestion de la Pompe (Hub)** : Allumez ou éteignez la filtration (Marche Forcée), changez les modes (Auto, Planning, Manuel) avec auto-détection du Hub.
- ⚙️ **Diagnostics Matériels** : Niveau de batterie, Étalonnage des sondes requis, Abonnement Flipr valide, Statut réseau Sigfox, Compteur de redémarrages, Dernier contact Cloud, RSSI Bluetooth, Version.

---

## 🤝 Crédits

Remerciements chaleureux à **@cnico** (créateur de l'intégration `flipr` initiale) et **@Adrien40** (créateur de l'intégration `flipr_local` BLE) pour leur travail fondateur qui sert d'inspiration à cette version unifiée **Flipr Pool Control**.
