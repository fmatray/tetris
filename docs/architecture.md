(Created: 2026-08-10)

## Architecture Technique

Le projet repose sur une architecture modulaire et extensible :

- **Machine à États Finis (FSM)** : Utilisation du *State Pattern* pour gérer les transitions fluides entre `MenuState`, `HumanMenuState`, `KeybindState`, `HumanState`, `AIState`, `AIMenuState`, `HyperparamMenuState`, `AIStatsState`, `GameOverState` et `LeaderboardState`.
- **Audio Procédural** : Génération d'ondes sinusoïdales via NumPy pour créer des mélodies et effets sonores sans dépendances de fichiers externes.
- **Système de Particules** : Moteur d'effets visuels gérant la physique (gravité, friction) et le cycle de vie des particules pour des explosions dynamiques.
- **Rendu Isolé** : Classe `Renderer` dédiée pour séparer la logique de mise à jour du moteur graphique.
- **Persistance JSON** : Leaderboard stocké dans `leaderboard.json`, trié par score décroissant, incluant le nom, le score, le niveau, les lignes effacées, le générateur de pièces, le mode de jeu et la date.
- **Apprentissage par Renforcement (V-network DQN)** : Agent V-network DQN implémenté avec PyTorch. L'IA apprend en jouant de manière autonome : évaluation par candidat (V-function, features DT-20 17-dim normalisées), exploration ε-greedy (decay et fin configurables), Prioritized Experience Replay (PER Schaul et al. 2015, avec importance sampling), n-step returns (3-step), target network (Polyak τ=0.005, Bellman). La récompense pénalise les nouveaux trous (delta), la hauteur, l'irrégularité et les puits, avec PBRS (Dellacherie, scale 0.1). Soft-drop BFS avec SRS wall kicks pour les surplombs et T-Spins. Look-ahead 2 pièces. Le modèle, les statistiques et les paramètres sont sauvegardés entre les sessions (`ai_model.pt`, `ai_training_log.json`, `settings.json`).

## Structure du projet

```
tetris/
├── main.py                      # Point d'entrée (lance tetris.run())
├── tetris/                      # Package principal
│   ├── __init__.py              # API publique (run)
│   ├── app.py                   # TetrisApp : boucle principale et FSM
│   ├── settings.py              # Constantes et configurations
│   ├── logger.py               # Logging central (configure_logging, get_logger)
│   ├── verify_training.py       # Validation headless de l'entraînement IA
│   ├── game/                    # Logique métier (sans pygame)
│   │   ├── __init__.py
│   │   ├── tetromino.py         # Modèle de pièce
│   │   ├── shapes.py            # Données de formes (SHAPES, SHAPES_TYPES, helpers rotation)
│   │   ├── rules.py             # Fonctions de jeu grid-agnostic (SRS kicks, shape_fits, hard_drop_y)
│   │   ├── board.py             # Grille, collisions, lignes, handicap, hard drop
│   │   ├── piece_provider.py    # Fournisseur de pièces (Aléatoire / 7-Bag / Replay, 1ère pièce sûre I/J/L/T)
│   │   ├── scoring.py           # Règles de score (Guideline : lignes × niveau, combos, drop)
│   │   └── stats.py             # Score, lignes, niveau
│   ├── ai/                      # Apprentissage par renforcement (V-network DQN)
│   │   ├── __init__.py
│   │   ├── network.py           # Réseau de neurones (17→128→64→1)
│   │   ├── agent.py             # DQNAgent (ε-greedy, per-candidate eval, replay, target net)
│   │   ├── replay_buffer.py     # Prioritized Experience Replay (PER, 50 000)
│   │   ├── rewards.py           # Récompense (delta trous + PBRS scale 0.1), features DT-20 normalisées, simulation soft-drop BFS + SRS
│   │   └── trainer.py           # Journal d'entraînement (JSON)
│   ├── audio/                   # Audio procédural (NumPy)
│   │   └── __init__.py          # AudioManager
│   ├── visuals/                 # Rendu et effets visuels
│   │   ├── __init__.py
│   │   ├── fonts.py             # Gestion des polices (tailles normalisées)
│   │   ├── particles.py         # Particle, ParticleSystem
│   │   ├── renderer.py          # Renderer (grille, HUD, animation Game Over)
│   │   ├── graph_view.py        # Rendu du graphique score/épisode (matplotlib)
│   │   └── leaderboard_view.py  # Rendu du tableau des scores
│   ├── states/                  # États FSM (State Pattern)
│   │   ├── __init__.py
│   │   ├── base.py              # State (classe de base)
│   │   ├── menu_base.py         # MenuStateBase (logique de menu réutilisable)
│   │   ├── menu.py              # MenuState (persistance settings.json)
│   │   ├── human_menu.py        # HumanMenuState (mode, touches, stats)
│   │   ├── human_stats.py       # HumanStatsState (page de statistiques humaines)
│   │   ├── keybind.py           # KeybindState (configuration des touches)
│   │   ├── game.py              # GameState (base abstraite: board, pieces, gravité, GameConfig)
│   │   ├── human.py             # HumanState (jeu humain: clavier, DAS, pause)
│   │   ├── ai.py                # AIState (DQN agent, HUD apprentissage + stats; AIConfig; candidates/HUD extraits vers tetris/ai/)
│   │   ├── ai_menu.py           # AIMenuState (mode, vitesse, apprentissage, stats, reset)
│   │   ├── hyperparam_menu.py   # HyperparamMenuState (13 hyperparamètres DQN + reset)
│   │   ├── ai_stats.py           # AIStatsState (tableau stats + graphique)
│   │   ├── game_over.py         # GameOverState
│   │   ├── leaderboard.py       # LeaderboardState
│   │   ├── mcp.py               # MCPState (jeu MCP, hérite GameState ; MCPConfig)
│   │   └── mcp_menu.py          # MCPMenuState (port, démarrage)
│   └── storage/                 # Persistance JSON
│   ├── mcp_server.py            # TetrisMCPServer (serveur MCP HTTP, outils play + resources)
├── tests/                       # Tests unitaires
│   ├── __init__.py
│   ├── conftest.py              # Fixtures partagées
│   ├── test_board.py            # Tests Board
│   ├── test_tetromino.py        # Tests Tetromino
│   ├── test_piece_provider.py   # Tests PieceProvider
│   ├── test_scoring.py          # Tests ScoreEngine
│   ├── test_stats.py            # Tests GameStats
│   ├── test_agent.py            # Tests DQNAgent
│   ├── test_mcp_states.py     # Tests MCPState
│   ├── test_rewards.py          # Tests features + récompense
│   └── test_curriculum.py       # Tests curriculum learning
├── data/                        # Données générées (settings, leaderboard, stats, IA)
│   ├── settings.json            # Préférences du menu
│   ├── leaderboard.json         # Scores top 10
│   ├── human_stats.json         # Historique des parties humaines
│   ├── ai_model.pt              # Poids du modèle DQN
│   ├── ai_training_log.json     # Journal d'entraînement
│   ├── debug.log                # Journal de débogage (mode débogage ON)
│   └── replay_pieces.json       # Séquences de pièces (mode replay)
├── requirements.txt             # Dépendances (pygame, numpy, torch)
└── README.md                    # Documentation du projet
```

## Principes de conception

Le codebase suit un ensemble de principes de génie logiciel pour rester lisible, testable et extensible.

### Packages plutôt qu'un fichier monolithique

Le code est organisé en packages (`game/`, `audio/`, `visuals/`, `states/`, `storage/`) plutôt qu'en un seul fichier. Chaque package a une responsabilité claire, et `main.py` se réduit à un point d'entrée de 10 lignes qui appelle `tetris.run()`.

### DRY (Don't Repeat Yourself)

- `draw_leaderboard()` dans `visuals/leaderboard_view.py` centralise le rendu du tableau des scores, partagé par `LeaderboardState` et `GameOverState` (auparavant dupliqué).
- Le tableau des points de ligne (`LINE_CLEAR_POINTS`) est défini une fois dans `settings.py` et utilisé par `ScoreEngine` — pas de logique de score dupliquée.

### KISS (Keep It Simple)

Chaque module est petit et fait une seule chose. `main.py` ne contient que l'appel à `tetris.run()`. La boucle principale vit dans `TetrisApp._frame()`, qui se lit en une dizaine de lignes.

### SOLID

| Principe | Application |
| -------- | -------- |
| **S** — Single Responsibility | `Board` (grille), `Tetromino` (pièce), `GameStats` (score/niveau), `ScoreEngine` (règles), `AudioManager` (son), `Renderer` (affichage), `ParticleSystem` (effets), `TetrisApp` (boucle) — une classe, un rôle. |
| **O** — Open/Closed | `State` est une classe de base ; ajouter un état se fait par sous-classe sans modifier `TetrisApp`. Les points de ligne s'ajoutent via `LINE_CLEAR_POINTS` (donnée) sans modifier `ScoreEngine`. |
| **L** — Liskov Substitution | Tous les états héritent de `State` avec la même signature `handle_event` / `update` / `draw`. `TetrisApp` les dispatche polymorphiquement. |
| **I** — Interface Segregation | Les `__init__.py` de chaque package sont des docstrings-only — pas de re-exports inutilisés. Les imports se font directement depuis le module source (ex. `from tetris.game.board import Board`). |
| **D** — Dependency Inversion | Les états reçoivent `AudioManager` et `Board` par injection de dépendances (constructeur), jamais par construction interne. `Renderer` lit l'état du jeu sans le muter. |

### Logging et mode débogage

Le module `tetris/logger.py` centralise la journalisation via Python `logging`. `configure_logging(debug)` configure le logger racine `tetris` :
- **Debug OFF** (défaut) : niveau WARNING — seul les erreurs sont écrites dans `data/debug.log`.
- **Debug ON** : niveau DEBUG — tous les messages (apparition de pièces, verrouillage, fin de partie, épisodes IA, curriculum) sont journalisés.

Le mode débogage est activable depuis le menu principal (option Débogage ON/OFF). Il active également la visualisation du sac de pièces restantes (7-bag ou 35-bag) à droite de l'aperçu de la prochaine pièce.

### SLAP (Single Layer of Abstraction)

Chaque fonction opère à un seul niveau d'abstraction :
- `TetrisApp._frame()` — niveau *dispatch FSM* (events, update, draw).
- `GameState.update()` — niveau *boucle de jeu* (gravité, lock delay, spawn). `HumanState.update()` ajoute le DAS.
- `Board.clear_lines()` — niveau *ligne de grille* (détection, suppression, compactage).

Aucune fonction mélange plusieurs niveaux, ce qui garde chaque méthode courte et focalisée.