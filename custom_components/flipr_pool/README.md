# Flipr Pool Control for Home Assistant (v2.0.0)

Intégration personnalisée pour les analyseurs de piscine Flipr. Cette intégration permet de récupérer les mesures en temps réel et de calculer automatiquement les doses de traitement nécessaires ainsi que le temps de filtration optimal.

## Caractéristiques

- **Mesures en temps réel** : Température de l'eau, pH, Redox (Désinfection), Batterie.
- **Statuts clairs** : Alertes si le pH ou le Chlore est trop haut ou trop bas.
- **Calculateur de traitement (v2)** : Calcule les grammes de pH-, pH+ ou Chlore à ajouter en fonction du volume de votre piscine.
- **Optimisation de filtration** : Calcul du temps de fonctionnement quotidien de la pompe (basé sur la température et la qualité de l'eau).
- **Interface Moderne** : Regroupement automatique sous un seul appareil Flipr avec icônes personnalisées.

## Installation

1. Copiez le dossier `flipr_pool` dans votre répertoire `custom_components/` de Home Assistant.
2. Redémarrez Home Assistant.
3. Allez dans **Paramètres > Appareils et Services > Ajouter une intégration**.
4. Recherchez **Flipr Pool Control**.

## Configuration

Lors de l'installation, il vous sera demandé :
- Votre **Email** et **Mot de passe** Flipr.
- L'**ID de votre module** (S/N présent sur l'appareil ou l'app officielle).
- Les **dimensions de votre piscine** (optionnel, nécessaire pour les calculs de doses).

> Vous pouvez modifier les dimensions à tout moment via le bouton **Configurer** sur la carte de l'intégration.

## Doses de traitement
Les calculs sont basés sur les standards suivants (modifiables dans `const.py`) :
- **pH cible** : 7.4
- **Chlore cible** : 2.0 mg/L
- **Produits** : Bisulfate de sodium (pH-), Carbonate de sodium (pH+), Chlore choc 70%.

## Licence
MIT License. Voir le fichier LICENSE pour plus de détails.
