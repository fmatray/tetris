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

| Touche | Jeu | Menu |
| -------- | -------- | -------- |
| ← → | Déplacer la pièce | Modifier valeur (Handicap, Son) |
| ↑ | Rotation horaire | Navigation vers le haut |
| ↓ | Accélérer la chute | Navigation vers le bas |
| S | Rotation anti-horaire | - |
| Espace | Pause | - |
| Entrée | - | Valider l'action |

## Architecture Technique

Le projet repose sur une architecture modulaire et extensible :

- **Machine à États Finis (FSM)** : Utilisation du *State Pattern* pour gérer les transitions fluides entre le `MenuState`, `GameState`, `GameOverState` et `LeaderboardState`.
- **Audio Procédural** : Génération de ondes sinusoïdales via NumPy pour créer des mélodies et effets sonores sans dépendances de fichiers externes.
- **Système de Particules** : Moteur d'effets visuels gérant la physique (gravité, friction) et le cycle de vie des particules pour des explosions dynamiques.
- **Rendu Isolé** : Classe `Renderer` dédiée pour séparer la logique de mise à jour du moteur graphique.
- **Persistance JSON** : Leaderboard stocké dans un format JSON structuré incluant le nom, le score, le niveau, les lignes effacées et la date.

## Structure du projet

```
tetris-python/
├── main.py            # FSM, Moteur de jeu, Audio et Rendu
├── tetris.py          # Logique métier (Board, Tetromino)
├── settings.py        # Constantes et configurations
├── leaderboard.json   # Sauvegarde des scores (JSON)
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
