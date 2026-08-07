# Tetris Python

Un jeu Tetris complet développé en Python avec Pygame, incluant des effets visuels spectaculaires, un système de son procédural, un leaderboard et une animation de fin de partie extravagante.

## Fonctionnalités

### Gameplay

- ✅ Mécaniques de Tetris classiques (rotation, déplacement, chute)
- ✅ Système de score avec bonus pour les lignes multiples (1 ligne = 100 pts, 2 = 220, 3 = 350, 4 = 500)
- ✅ Niveaux progressifs (la vitesse augmente selon `0.5 × 0.98^niveau` toutes les 10 lignes)
- ✅ Handicap personnalisable (0-5, chaque niveau ajoute 2 rangées partielles de blocs gris en bas)

### Effets visuels

- ✅ **Particules explosives** : 80 particules par ligne détruite, avec physique (gravité, friction).
- ✅ **Animation de Game Over Spectaculaire** : Séquence chaotique de 4 secondes incluant screen-shake, glitchs visuels, flashs d'écran et texte arc-en-ciel pulsé.
- ✅ Affichage de la pièce suivante.
- ✅ Interface utilisateur complète (score, lignes, niveau).

### Audio

- ✅ **Sons Procéduraux** : Générés via NumPy (ondes sinusoïdales avec enveloppe) pour une expérience unique sans fichiers externes.
- ✅ **Mélodies de Clear** : Musiques spécifiques selon le nombre de lignes effacées (1 à 4).
- ✅ **Impacts & Rotations** : Sons de verrouillage de pièce et rotations (horaires et anti-horaires).
- ✅ **Séquence Finale** : Mélodie dramatique descendante et effets sonores de glitch lors du Game Over.
- ✅ Option pour activer/désactiver le son.

### Expérience utilisateur

- ✅ Menu de démarrage avec sélection du joueur (Humain/IA), du handicap et du son.
- ✅ Saisie du nom (15 caractères max) en fin de partie.
- ✅ Leaderboard top 10 persistant (JSON).
- ✅ Retour automatique au menu principal après le leaderboard.

## Installation

### Prérequis

- Python 3.9+
- Pygame ≥ 2.5.0
- NumPy ≥ 1.24.0

### Installation

```bash
git clone <url-du-dépôt>
cd tetris
pip install -r requirements.txt
```

### Lancement

```bash
python main.py
```

## Contrôles

| Touche | Jeu | Menu |
| -------- | -------- | -------- |
| ← → | Déplacer la pièce | Modifier valeur (Joueur, Handicap, Son) |
| ↑ | Rotation horaire | Navigation vers le haut |
| ↓ | Accélérer la chute | Navigation vers le bas |
| S | Rotation anti-horaire | - |
| Espace | Pause | - |
| Entrée | - | Valider l'action |

## Architecture Technique

Le projet repose sur une architecture modulaire et extensible :

- **Machine à États Finis (FSM)** : Utilisation du *State Pattern* pour gérer les transitions fluides entre `MenuState`, `GameState`, `GameOverState` et `LeaderboardState`.
- **Audio Procédural** : Génération d'ondes sinusoïdales via NumPy pour créer des mélodies et effets sonores sans dépendances de fichiers externes.
- **Système de Particules** : Moteur d'effets visuels gérant la physique (gravité, friction) et le cycle de vie des particules pour des explosions dynamiques.
- **Rendu Isolé** : Classe `Renderer` dédiée pour séparer la logique de mise à jour du moteur graphique.
- **Persistance JSON** : Leaderboard stocké dans `leaderboard.json`, trié par score décroissant, incluant le nom, le score, le niveau, les lignes effacées et la date.


## Principes de conception

Le codebase suit un ensemble de principes de génie logiciel pour rester lisible, testable et extensible.

### Packages plutôt qu'un fichier monolithique

Le code est organisé en packages (`game/`, `audio/`, `visuals/`, `states/`, `storage/`) plutôt qu'un seul fichier. Chaque package a une responsabilité claire, et `main.py` se réduit à un point d'entrée de 10 lignes qui appelle `tetris.run()`.

### DRY (Don't Repeat Yourself)

- `draw_leaderboard()` dans `visuals/leaderboard_view.py` centralise le rendu du tableau des scores, partagé par `LeaderboardState` et `GameOverState` (auparavant dupliqué).
- Le tableau des bonus de score (`LINE_BONUS`) est défini une fois dans `settings.py` et utilisé par `ScoreEngine` — pas de logique de score dupliquée.

### KISS (Keep It Simple)

Chaque module est petit et fait une seule chose. `main.py` ne contient que l'appel à `tetris.run()`. La boucle principale vit dans `TetrisApp._frame()`, qui se lit en une dizaine de lignes.

### SOLID

| Principe | Application |
| -------- | -------- |
| **S** — Single Responsibility | `Board` (grille), `Tetromino` (pièce), `GameStats` (score/niveau), `ScoreEngine` (règles), `AudioManager` (son), `Renderer` (affichage), `ParticleSystem` (effets), `TetrisApp` (boucle) — une classe, un rôle. |
| **O** — Open/Closed | `State` est une classe de base ; ajouter un état se fait par sous-classe sans modifier `TetrisApp`. Les bonus de score s'ajoutent via `LINE_BONUS` (donnée) sans modifier `ScoreEngine`. |
| **L** — Liskov Substitution | Tous les états héritent de `State` avec la même signature `handle_event` / `update` / `draw`. `TetrisApp` les dispatche polymorphiquement. |
| **I** — Interface Segregation | Les `__init__.py` de chaque package n'exposent que le strict nécessaire (ex. `game/` exporte `Board`, `Tetromino`, `GameStats`, `ScoreEngine`). |
| **D** — Dependency Inversion | Les états reçoivent `AudioManager` et `Board` par injection de dépendances (constructeur), jamais par construction interne. `Renderer` lit l'état du jeu sans le muter. |

### SLAP (Single Layer of Abstraction)

Chaque fonction opère à un seul niveau d'abstraction :

- `TetrisApp._frame()` — niveau *dispatch FSM* (events, update, draw).
- `GameState._tick()` — niveau *chute de pièce* (verrouillage, lignes, spawn).
- `Board.clear_lines()` — niveau *ligne de grille* (détection, suppression, compactage).

Aucune fonction mélange plusieurs niveaux, ce qui garde chaque méthode courte et focalisée.

## Structure du projet

```
tetris/
├── main.py                      # Point d'entrée (lance tetris.run())
├── tetris/                      # Package principal
│   ├── __init__.py              # API publique (run)
│   ├── app.py                   # TetrisApp : boucle principale et FSM
│   ├── settings.py              # Constantes et configurations
│   ├── game/                    # Logique métier (sans pygame)
│   │   ├── __init__.py
│   │   ├── tetromino.py         # Modèle de pièce
│   │   ├── board.py             # Grille, collisions, lignes, handicap
│   │   ├── scoring.py           # Règles de score (bonus multi-lignes)
│   │   └── stats.py             # Score, lignes, niveau
│   ├── audio/                   # Audio procédural (NumPy)
│   │   └── __init__.py          # AudioManager
│   ├── visuals/                 # Rendu et effets visuels
│   │   ├── __init__.py
│   │   ├── particles.py         # Particle, ParticleSystem
│   │   ├── renderer.py          # Renderer (grille, HUD, animation Game Over)
│   │   └── leaderboard_view.py  # Rendu partagé du leaderboard (DRY)
│   ├── states/                  # États FSM (State Pattern)
│   │   ├── __init__.py
│   │   ├── base.py              # State (classe de base)
│   │   ├── menu.py              # MenuState
│   │   ├── game.py              # GameState
│   │   ├── game_over.py         # GameOverState
│   │   └── leaderboard.py       # LeaderboardState
│   └── storage/                 # Persistance JSON
│       └── __init__.py          # load_leaderboard, save_score
├── leaderboard.json             # Sauvegarde des scores top 10 (JSON)
├── requirements.txt             # Dépendances (pygame, numpy)
├── AI.md                        # Document de conception : mode joueur IA (DQN, non implémenté)
└── README.md                    # Documentation du projet

## Personnalisation

### Modifier les paramètres

Éditez `tetris/settings.py` pour changer :

- Dimensions de la grille (`BOARD_WIDTH`, `BOARD_HEIGHT`)
- Taille des blocs (`BLOCK_SIZE`)
- Dimensions de l'écran (`SCREEN_WIDTH`, `SCREEN_HEIGHT`)
- Couleurs des pièces (`SHAPES_COLORS`)

> La vitesse de chute est calculée dans `tetris/states/game.py` (`DROP_BASE × DROP_DECAY^niveau`) et configurable via `tetris/settings.py` (`DROP_BASE`, `DROP_DECAY`, `SOFT_DROP_FACTOR`).

## Roadmap

Un mode **Joueur IA** basé sur le Deep Q-Learning (DQN) est conçu dans `AI.md` : entraînement par renforcement, représentation de l'état du plateau, fonction de récompense et pipeline d'entraînement. Ce mode n'est pas encore implémenté.

## Crédits

Développé par Frédéric Matray
Musique et effets sonores générés procéduralement avec NumPy.

## Licence

MIT License - Libre d'utilisation et de modification