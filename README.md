# Tetris Python

Un jeu Tetris complet développé en Python avec Pygame, incluant des effets visuels spectaculaires, un système de son, un leaderboard et des options de personnalisation.

![Tetris Gameplay](https://via.placeholder.com/800x600/000000/FFFFFF?text=Tetris+Gameplay)

## Fonctionnalités

### Gameplay

- ✅ Mécaniques de Tetris classiques (rotation, déplacement, chute)
- ✅ Système de score avec bonus pour les lignes multiples
- ✅ Niveaux progressifs (vitesse augmente toutes les 10 lignes)
- ✅ Handicap personnalisable (0-5 lignes de blocs gris en bas)

### Effets visuels

- ✅ Particules spectaculaires lors de la destruction de lignes
- ✅ Affichage de la pièce suivante
- ✅ Interface utilisateur complète (score, lignes, niveau)

### Audio

- ✅ Musique générée procéduralement pour chaque type de ligne complétée
- ✅ Sons de rotation (horaire/anti-horaire)
- ✅ Option pour activer/désactiver le son

### Expérience utilisateur

- ✅ Menu de démarrage avec sélection du handicap
- ✅ Saisie du nom en fin de partie
- ✅ Leaderboard top 10 affiché à l'écran
- ✅ Option pour recommencer ou quitter

## Installation

### Prérequis

- Python 3.7+
- Pygame (`pip install pygame`)
- NumPy (`pip install numpy`)

### Installation

```bash
git clone https://github.com/votre-utilisateur/tetris-python.git
cd tetris-python
pip install -r requirements.txt
```

### Lancement

```bash
python main.py
```

## Contrôles

| Touche | Action |
| -------- | -------- |
| ← → | Déplacer la pièce |
| ↑ | Rotation horaire |
| S | Rotation anti-horaire |
| ↓ | Accélérer la chute (soft drop) |
| Espace | Pause |
| Entrée | Valider dans les menus |
| S (menu) | Activer/désactiver le son |

## Structure du projet

```
tetris-python/
├── main.py            # Point d'entrée principal
├── tetris.py          # Logique du jeu (Board, Tetromino)
├── settings.py        # Constantes et configurations
├── leaderboard.txt    # Fichier de sauvegarde des scores
└── README.md          # Ce fichier
```

## Personnalisation

### Modifier les paramètres

Éditez `settings.py` pour changer :

- Taille de la grille
- Vitesse de chute
- Taille des blocs
- Couleurs des pièces

### Ajouter des fonctionnalités

Quelques idées d'améliorations possibles :

1. Ajouter un système de "hold" (conserver une pièce)
2. Implémenter un mode "marathon" avec objectifs
3. Ajouter des skins pour les pièces
4. Créer un mode multijoueur local
5. Ajouter des effets visuels supplémentaires

## Crédits

Développé par Frédéric Matray
Musique générée procéduralement avec NumPy

## Licence

MIT License - Libre d'utilisation et de modification
