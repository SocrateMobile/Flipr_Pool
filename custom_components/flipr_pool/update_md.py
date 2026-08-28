import os

with open("examples/flipr_official_app_analyse.yaml", "r") as f:
    analyse = f.read()

with open("examples/flipr_official_app_controle.yaml", "r") as f:
    controle = f.read()

# Create combined yaml
combined = "type: horizontal-stack\ncards:\n"

for line in analyse.splitlines():
    combined += "  - " + line + "\n" if line.startswith("type:") else "    " + line + "\n"

for line in controle.splitlines():
    combined += "  - " + line + "\n" if line.startswith("type:") else "    " + line + "\n"

with open("examples/flipr_official_app_combined.yaml", "w") as f:
    f.write(combined)

md_content = f"""# Cartes Lovelace "Flipr Official App"

Voici les codes YAML complets. Vous pouvez cliquer sur l'icône de copie en haut à droite de chaque bloc de code pour les récupérer facilement et les coller dans votre tableau de bord Home Assistant.

> [!NOTE]
> **Détection automatique de votre appareil Flipr**
> Le code JavaScript intégré dans ces cartes est conçu pour rechercher automatiquement le nom exact de votre appareil Flipr dans Home Assistant (par exemple `sensor.jardin_flipr_piscine_ph`).
> Vous n'avez pas besoin de renommer vos entités ou de modifier le code si votre appareil est dans une pièce spécifique (comme "Jardin") ou s'il s'appelle différemment, tant que les entités d'origine générées par l'intégration contiennent le mot "flipr" !

## Aperçu du rendu

![Rendu de la carte double](file:///Users/jean-fredericlavigne/.gemini/antigravity/brain/40e8c04a-1d11-42a1-a23b-2fc2d77c904d/.user_uploaded/media_1785964282711.png)

## Vue Combinée (Analyse à gauche, Contrôle à droite)
Cette vue utilise une carte `horizontal-stack` pour afficher les deux vues côte à côte.

```yaml
{combined}
```

## 1. Vue Analyse (Isolée)

```yaml
{analyse}
```

## 2. Vue Contrôle (Isolée)

```yaml
{controle}
```
"""
with open("/Users/jean-fredericlavigne/.gemini/antigravity/brain/40e8c04a-1d11-42a1-a23b-2fc2d77c904d/copy_paste_cards.md", "w") as f:
    f.write(md_content)
