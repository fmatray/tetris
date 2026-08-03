# Tetris Python

Un jeu Tetris complet développé en Python avec Pygame, incluant des effets visuels spectaculaires, un système de son procédural, un leaderboard et une animation de fin de partie extravagante.

![Tetris Gameplay](https://via.placeholder.com/800x600/000000/FFFFFF?text=Tetris+Gameplay)

## Fonctionnalités

### Gameplay

- ✅ Mécaniques de Tetris classiques (rotation, déplacement, chute)
- ✅ Système de score avec bonus pour les lignes multiples
- ✅ Niveaux progressifs (vitesse augmente toutes les 10 lignes)
- ✅ Handicap personnalisable (0-5 lignes de blocs gris en bas)

### Effets visuels

- ✅ **Particules explosives** : Effets de haute densité et rapides lors de la destruction de lignes.
- ✅ **Animation de Game Over Spectaculaire** : Séquence chaotique incluant screen-shake, glitchs visuels, flashs d'écran et texte arc-en-ciel pulsé.
- ✅ Affichage de la pièce suivante.
- ✅ Interface utilisateur complète (score, lignes, niveau).

### Audio

- ✅ **Sons Procéduraux** : Générés via NumPy pour une expérience unique sans fichiers externes.
- ✅ **Mélodies de Clear** : Musiques spécifiques selon le nombre de lignes effacées.
- ✅ **Impacts & Rotations** : Sons de verrouillage de pièce (high-pitch thud) et rotations.
- ✅ **Séquence Finale** : Mélodie dramatique descendante et effets sonores de glitch lors du Game Over.
- ✅ Option pour activer/désactiver le son.

### Expérience utilisateur

- ✅ Menu de démarrage avec sélection du handicap.
- ✅ Saisie du nom en fin de partie.
- ✅ Leaderboard top 10 persistant.
- ✅ Option pour recommencer ou quitter.

## Installation

### Prérequis

- Python 3.7+ (Testé et optimisé pour Python 3.14)
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
├── main.py            # Point d'entrée principal, moteur de jeu et audio
├── tetris.py          # Logique du jeu (Board, Tetromino)
├── settings.py        # Constantes et configurations
├── leaderboard.txt    # Fichier de sauvegarde des scores
└── README.md          # Documentation du projet
```

## Personnalisation

### Modifier les paramètres

Éditez `settings.py` pour changer :

- Taille de la grille
- Vitesse de chute
- Taille des blocs
- Couleurs des pièces

## Crédits

Développé par Frédéric Matray
Musique et effets sonores générés procéduralement avec NumPy.

## Licence

MIT License - Libre d'utilisation et de modification
