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

- ✅ Menu de démarrage avec sélection du joueur (Humain/IA), du son, et sous-menus dédiés.
- ✅ **Sous-menu Humain** : Mode (Normal/Replay), Handicap (0-5), Touches (touches configurables), Statistiques (page de statistiques du joueur humain).
- ✅ **Sous-menu IA** : Mode (Apprentissage/Jeu), Vitesse (normal/rapide), Apprentissage (hyperparamètres DQN : Epsilon decay, Epsilon fin, Learning rate, Gamma, Batch size, Buffer size, Target sync — configurables via ◄ ►, persistés dans `settings.json`, reset aux valeurs par défaut), Statistiques (tableau + graphique score/épisode), Réinitialiser IA, Retour.
- ✅ **Touches configurables** : 7 actions (gauche, droite, rotation horaire/anti-horaire, chute douce, chute rapide, pause) reconfigurables via le menu. Détection de conflits et touches réservées. Persistance dans `settings.json`.
- ✅ Saisie du nom (15 caractères max) en fin de partie.
- ✅ Leaderboard top 10 persistant (JSON).
- ✅ Retour automatique au menu principal après le leaderboard.
- ✅ **Joueur IA (DQN)** : Mode apprentissage par renforcement (Deep Q-Learning). L'IA apprend à jouer de manière autonome, à vitesse humaine, et affiche ses statistiques d'apprentissage en temps réel : paramètres d'entraînement (mode, vitesse, épisode, epsilon, decay, perte) et tableau de statistiques (pièces, lignes, score, niveau — courant, total, meilleur, moyenne, 100 derniers, tendance ↑/↓/→). Placement BFS avec minimisation des trous. Paramètres ε configurables (decay, fin) persistés dans `settings.json`. Mode Jeu (greedy, sans apprentissage) ou Apprentissage (exploration ε-greedy).

## Installation

### Prérequis

- Python 3.9+
- Pygame ≥ 2.5.0
- NumPy ≥ 1.24.0
- PyTorch ≥ 2.0 (requis pour le mode IA)

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

Les touches sont configurables via le menu (**Humain > Touches**). Les valeurs par défaut :

| Touche | Jeu | Menu |
| -------- | -------- | -------- |
| ← → | Déplacer la pièce | Modifier valeur / Navigation |
| ↑ | Rotation horaire | Navigation vers le haut |
| ↓ | Chute douce | Navigation vers le bas |
| S | Rotation anti-horaire | - |
| Espace | Chute rapide | - |
| P | Pause | - |
| Échap | Retour au menu (sans sauvegarde du score) | Retour / Quitter |
| Entrée | - | Valider l'action |


## Architecture Technique

Le projet repose sur une architecture modulaire et extensible :

- **Machine à États Finis (FSM)** : Utilisation du *State Pattern* pour gérer les transitions fluides entre `MenuState`, `HumanMenuState`, `KeybindState`, `GameState`, `AIState`, `AIMenuState`, `HyperparamMenuState`, `StatsState`, `GameOverState` et `LeaderboardState`.
- **Audio Procédural** : Génération d'ondes sinusoïdales via NumPy pour créer des mélodies et effets sonores sans dépendances de fichiers externes.
- **Système de Particules** : Moteur d'effets visuels gérant la physique (gravité, friction) et le cycle de vie des particules pour des explosions dynamiques.
- **Rendu Isolé** : Classe `Renderer` dédiée pour séparer la logique de mise à jour du moteur graphique.
- **Persistance JSON** : Leaderboard stocké dans `leaderboard.json`, trié par score décroissant, incluant le nom, le score, le niveau, les lignes effacées et la date.
- **Apprentissage par Renforcement (Double DQN)** : Agent Deep Q-Network implémenté avec PyTorch. L'IA apprend en jouant de manière autonome : exploration ε-greedy (decay et fin configurables), experience replay (buffer 50 000), Double DQN (online sélectionne, target évalue), target network (sync toutes les 500 étapes). L'état du plateau est encodé en vecteur de 220 features (grille 200 + pièce courante 7 + pièce suivante 7 + orientation 4 + position 2). Les macro-actions (colonne × rotation) sont exécutées par BFS soft-drop avec minimisation des trous. La récompense pénalise les nouveaux trous (delta), la hauteur et l'irrégularité. Le modèle, les statistiques et les paramètres sont sauvegardés entre les sessions (`ai_model.pt`, `ai_training_log.json`, `settings.json`).


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
│   │   ├── board.py             # Grille, collisions, lignes, handicap, hard drop
│   │   ├── scoring.py           # Règles de score (bonus multi-lignes)
│   │   └── stats.py             # Score, lignes, niveau
│   ├── ai/                      # Apprentissage par renforcement (Double DQN)
│   │   ├── __init__.py
│   │   ├── network.py           # Réseau de neurones (220→256→128→64→40)
│   │   ├── agent.py             # DQNAgent (ε-greedy, Double DQN, replay, target net)
│   │   ├── replay_buffer.py     # Buffer d'experience replay (50 000)
│   │   ├── rewards.py           # Récompense (delta trous) et extraction de features
│   │   └── trainer.py           # Journal d'entraînement (JSON)
│   ├── audio/                   # Audio procédural (NumPy)
│   │   └── __init__.py          # AudioManager
│   ├── visuals/                 # Rendu et effets visuels
│   │   ├── __init__.py
│   │   ├── particles.py         # Particle, ParticleSystem
│   │   ├── renderer.py          # Renderer (grille, HUD, animation Game Over)
│   │   └── graph_view.py        # Rendu du graphique score/épisode (matplotlib)
│   ├── states/                  # États FSM (State Pattern)
│   │   ├── __init__.py
│   │   ├── base.py              # State (classe de base)
│   │   ├── menu.py              # MenuState (persistance settings.json)
│   │   ├── human_menu.py        # HumanMenuState (mode, handicap, touches, stats)
│   │   ├── keybind.py           # KeybindState (configuration des touches)
│   │   ├── ai.py                # AIState (DQN agent, HUD apprentissage + stats)
│   │   ├── ai_menu.py           # AIMenuState (mode, vitesse, apprentissage, stats, reset)
│   │   ├── hyperparam_menu.py   # HyperparamMenuState (7 hyperparamètres DQN + reset)
│   │   ├── stats.py             # StatsState (tableau stats + graphique)
│   │   ├── graph.py             # GraphState (courbe score vs épisode)
│   │   ├── game_over.py         # GameOverState
│   │   └── leaderboard.py       # LeaderboardState
│   └── storage/                 # Persistance JSON
│       └── __init__.py          # load_leaderboard, save_score, save_human_game
├── data/                        # Données générées (settings, leaderboard, stats, IA)
│   ├── settings.json            # Préférences du menu
│   ├── leaderboard.json         # Scores top 10
│   ├── human_stats.json         # Historique des parties humaines
│   ├── ai_model.pt              # Poids du modèle DQN
│   ├── ai_training_log.json     # Journal d'entraînement
│   └── replay_pieces.json       # Séquences de pièces (mode replay)
├── requirements.txt             # Dépendances (pygame, numpy, torch)
├── AI.md                        # Document de conception : mode joueur IA (DQN)
└── README.md                    # Documentation du projet
```

## Personnalisation

### Modifier les paramètres

Éditez `tetris/settings.py` pour changer :

- Dimensions de la grille (`BOARD_WIDTH`, `BOARD_HEIGHT`)
- Taille des blocs (`BLOCK_SIZE`)
- Dimensions de l'écran (`SCREEN_WIDTH`, `SCREEN_HEIGHT`)
- Couleurs des pièces (`SHAPES_COLORS`)
- Touches par défaut (`DEFAULT_KEYBINDS`, `KEYBIND_LABELS`)

> Les touches sont reconfigurables via le menu (**Humain > Touches**) et persistées dans `settings.json`. Les valeurs par défaut sont définies dans `tetris/settings.py` (`DEFAULT_KEYBINDS`).
>
> La vitesse de chute est calculée dans `tetris/states/game.py` (`DROP_BASE × DROP_DECAY^niveau`) et configurable via `tetris/settings.py` (`DROP_BASE`, `DROP_DECAY`, `SOFT_DROP_FACTOR`).

## Arborescence des menus

```
Menu principal
├── Joueur                        [toggle ◄ ►]     Humain ↔ IA
├── Son                           [toggle ◄ ►]     ON ↔ OFF
├── Humain                        [ENTER]          (grisé si Joueur=IA)
│   └── Mode                      [toggle ◄ ►]     Normal ↔ Replay
│       Handicap                  [toggle ◄ ►]     0–5
│       Touches                   [ENTER]          → keybinding config
│       Statistiques              [ENTER]          → human stats page
│       Retour                    [ENTER | ESC]
├── IA                            [ENTER]          (grisé si Joueur=Humain)
│   └── Mode                      [toggle ◄ ►]     Apprentissage ↔ Jeu
│       Vitesse                   [toggle ◄ ►]     normal ↔ fast
│       Apprentissage             [ENTER]          (grisé si Mode=Jeu)
│       │   └── Epsilon decay     [toggle ◄ ►]     0.990–0.9999
│       │       Epsilon fin       [toggle ◄ ►]     0.02–0.10
│       │       Learning rate     [toggle ◄ ►]     1e-6–1e-2
│       │       Gamma              [toggle ◄ ►]     0.80–0.99
│       │       Batch size        [toggle ◄ ►]     8–256
│       │       Buffer size       [toggle ◄ ►]     1000–200000
│       │       Target sync       [toggle ◄ ►]     100–2000
│       │       Réinitialiser     [ENTER]          reset to defaults
│       │       Retour            [ENTER | ESC]
│       Statistiques              [ENTER]          → stats + graph (une page)
│       Réinitialiser IA          [ENTER ×2]       supprime modèle + log
│       Retour                    [ENTER | ESC]
├── Démarrer le jeu               [ENTER]          → GameState | AIState
├── Leaderboard                   [ENTER]          → LeaderboardState
└── Quitter                       [ENTER | ESC]    exit
```

## Roadmap

Un mode **Joueur IA** basé sur le Double DQN est implémenté dans le package `tetris/ai/` et intégré via `AIState` (voir `AI.md` pour le design détaillé). L'IA dispose de deux modes : **Apprentissage** (exploration ε-greedy, sauvegarde du modèle et du journal) et **Jeu** (greedy, sans apprentissage). L'IA apprend en jouant de manière autonome, à cadence humaine (~12 actions/sec), avec placement BFS (minimisation des trous), récompense delta-based, paramètres ε configurables, tableau de statistiques avec tendances, et sauvegarde du modèle, des statistiques et des préférences entre les sessions.

Le **menu** est structuré en arborescence (voir ci-dessus) : sous-menu Humain (mode, handicap, touches configurables, statistiques) et sous-menu IA (mode, vitesse, apprentissage, statistiques, reset). Les touches du joueur humain sont entièrement reconfigurables avec détection de conflits et persistance.

Améliorations futures possibles : Stratégies d'apprentissage multiples, Prioritized Experience Replay, Curriculum Learning, MCTS.

## Crédits

Développé par Frédéric Matray
Musique et effets sonores générés procéduralement avec NumPy.

## Licence

MIT License - Libre d'utilisation et de modification