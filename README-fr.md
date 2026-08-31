# Tetris Python

Un jeu Tetris complet développé en Python avec Pygame, incluant un agent IA Deep Q-Network (DQN), un bot heuristique El-Tetris et une intégration Model Context Protocol (MCP) pour agents externes.

## Fonctionnalités

### Gameplay
- ✅ **Conforme au Tetris Guideline** — Plateau 22 lignes (20 visibles + 2 cachées), rotations SRS avec wall kicks, pièce en réserve (hold), délai de verrouillage avec limite de réinitialisation, détection T-Spin (règle des 3 coins), chaînage Back-to-Back, score combo
- ✅ **Quatre types de joueurs** — Humain, IA DQN, Bot El-Tetris, Agent MCP externe
- ✅ **Générateurs de pièces multiples** — Aléatoire, sac 7-bag, sac 35-bag, pondéré, replay
- ✅ **Règles configurables** — Pièce fantôme, nombre d'aperçus (0/1/3), handicap (0–5), modes de vitesse (aucun/insane)
- ✅ **Graines reproductibles** — Saisie numérique de graine pour séquences de pièces déterministes

### IA Joueur (DQN)
- ✅ **Réseau V DQN** — MLP 17→256→128→1 évaluant la qualité du plateau par placement candidat
- ✅ **Features DT-20** — Vecteur d'état normalisé 17 dimensions (trous, hauteur, irrégularité, puits, transitions, one-hot pièce suivante)
- ✅ **PBRS (Potential-Based Reward Shaping)** — Façonnage de récompense préservant la politique optimale
- ✅ **Prioritized Experience Replay** — Recuit beta 0.4→1.0 sur 10K pas d'apprentissage
- ✅ **Retours N-step** — Cibles TD n-step configurables
- ✅ **BFS Soft-drop** — Énumération complète SRS wall-kick de tous les placements accessibles incluant surplombs
- ✅ **Look-ahead** — Simulation du meilleur placement pièce suivante (profondeur 1–3, optimal El-Tetris)
- ✅ **Candidats hold** — L'IA peut garder une fois par verrouillage, mêmes règles qu'humain
- ✅ **Apprentissage par curriculum** — Restriction progressive du set de pièces avec réinitialisation epsilon
- ✅ **Deux modes** — Apprentissage (epsilon-greedy, mises à jour entraînement, verrouillage accéléré) vs Jeu (glouton, délai complet)
- ✅ **Observabilité 5 niveaux** — JSON par épisode, JSONL par pas, JSONL comportemental, décomposition récompense, TensorBoard

### Bot El-Tetris
- ✅ **Évaluation El-Tetris** — 6 heuristiques (hauteur d'atterrissage, cellules érodées, transitions lignes/colonnes, trous, sommes puits) avec somme pondérée
- ✅ **BFS Soft-drop** — Même énumération candidats que l'IA, replay exact via séquences de mouvements BFS
- ✅ **Look-ahead** — Profondeur configurable (aucun / aperçu)
- ✅ **Bibliothèque bot partagée** — `BotMovesMixin` réutilisé par états IA et bot

### Intégration MCP
- ✅ **Serveur HTTP FastMCP** — Transport streamable-http, thread démon
- ✅ **Outils** — `play(moves)`, `start_game(config)`
- ✅ **Ressources** — `board://state` (instantané plateau temps réel), `tetris://rules` (référence règles)
- ✅ **Architecture file d'attente** — Communication thread-safe entre serveur MCP et `MCPState`

### Audio
- ✅ **SFX procéduraux** — Ondes sinusoïdales NumPy avec enveloppes (déplacement, rotation, verrouillage, ligne, niveau, game over)
- ✅ **Musique MIDI polyphonique** — Korobeiniki et Kalinka parsées depuis fichiers `.mid`, synthétisées via NumPy
- ✅ **Adaptation vitesse musique** — Mise à l'échelle tempo régénère buffer audio à durée `1/vitesse`
- ✅ **Crossfade** — Transitions fluides entre pistes
- ✅ **Contrôles volume** — Volumes son/musique indépendants (0–3)

### Visuels
- ✅ **Rendu** — Couche présentation pure (plateau, aperçu, hold, fantôme, stats, classement)
- ✅ **Système particules** — Effets basés physique (gravité, friction) sur lignes complétées (80 particules/ligne)
- ✅ **Overlay debug** — Visualisation sac 7-bag, infos vitesse, debug trous/surplombs (toggle touche `d`)

### Persistance & Logs
- ✅ **Réglages** — `data/settings.json` (tous prefs menus, keybinds, hyperparams IA)
- ✅ **Classement** — Top 10 scores (`data/leaderboard.json`)
- ✅ **Stats humain** — Historique parties non borné (`data/human_stats.json`)
- ✅ **Modèle IA** — Checkpoint PyTorch (`data/ai_model.pt`: poids, optimiseur, epsilon, état curriculum)
- ✅ **Logs entraînement** — Observabilité 5 niveaux (voir section IA Joueur)
- ✅ **Logging centralisé** — Module `tetris.logger`, mode debug écrit dans `data/debug.log`

## Installation

### Prérequis
- Python 3.9+
- pygame-ce 2.5.x (pas pygame standard)
- PyTorch 2.0+
- NumPy 1.24+
- matplotlib 3.7+
- mido 1.3+

### Installation
```bash
pip install -r requirements.txt
```

### Lancement
```bash
python main.py
```

### Test Sans Affichage (Headless)
```bash
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python3 -c "
import pygame
from tetris.states.menu import MenuState
pygame.init()
screen = pygame.Surface((1500, 800))
font = pygame.font.Font(None, 20)
from tetris.audio import AudioManager
audio = AudioManager(sound_volume=0, music_volume=0)
state = MenuState(screen, font, audio)
# Piloter les états avec événements synthétiques...
"
```

### Validation Entraînement IA (Headless)
```bash
python -m tetris.verify_training
```
Critères de succès : best_score > 10000, avg_score > 1000, avg_duration > 30s, max_loss < 1000.

## Contrôles

Les touches sont configurables via le menu (**Humain > Touches**). Valeurs par défaut :

| Touche | Jeu | Menu |
|--------|-----|------|
| `←` / `→` | Déplacement gauche/droite | Naviguer |
| `↑` | Rotation horaire | Naviguer / Changer valeur |
| `↓` | Chute douce | Naviguer / Changer valeur |
| `Espace` | Chute dure | Sélectionner |
| `C` / `Shift` | Réserve (hold) | — |
| `P` / `Échap` | Pause | Retour |
| `M` | Muet audio | — |
| `D` | Basculer overlay debug | — |
| `Entrée` | — | Sélectionner |
| `Retour` | — | Retour |

## Documentation

La documentation technique se trouve dans le dossier `docs/` :

| Document | Description |
|----------|-------------|
| `architecture.md` | Architecture système, diagramme FSM, diagramme classes |
| `ai.md` | Conception IA DQN, réseau V, features DT-20, PBRS, pipeline entraînement |
| `bot.md` | Bot El-Tetris, évaluation El-Tetris, bibliothèque bot partagée |
| `game_rules.md` | Conformité Guideline, moteur règles, alignement humain/IA |
| `menus.md` | Hiérarchie menus, keybinds, persistance réglages |
| `human.md` | Gameplay humain, DAS, personnalisation touches, graine/replay |
| `music_and_sound.md` | Synthèse SFX, parsing MIDI, adaptation vitesse musique |
| `mcp.md` | Serveur MCP, outils, ressources, simulation |
| `performance.md` | Méthodologie profilage, optimisations, benchmarks |
| `development.md` | Commandes, conventions, tests, fichiers données, résumé DQN |
| `roadmap.md` | Jalons, priorités, améliorations, dette technique |

## Structure du Projet

```
tetris/
├── ai/              # Agent DQN, réseau, récompenses, candidats, HUD
├── audio/           # AudioManager, synthèse SFX, parsing MIDI
├── bots/            # Bibliothèque bot partagée (BotMovesMixin)
├── game/            # Domaine pur: Board, Tetromino, formes, score, stats, fournisseurs pièces, règles
├── logger.py        # Logging centralisé
├── mcp_server.py    # Serveur HTTP FastMCP
├── settings.py      # Toutes constantes, constantes chemins
├── states/          # États FSM (16 classes)
├── storage/         # Persistance JSON
└── visuals/         # Rendu, ParticleSystem
```

## Développement

```bash
# Lint
ruff check .

# Vérification types
zuban check .

# Tests (headless)
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python -m pytest tests/ -q

# Couverture
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python -m pytest tests/ --cov=tetris --cov-report=term-missing -q
```

## Crédits

Développé par Frédéric Matray.
Musique et effets sonores générés procéduralement avec NumPy.
Tetris® est une marque de The Tetris Company.

## Licence

Licence MIT — Libre d'utilisation et de modification.

## Références

- [Tetris Wiki](https://tetris.wiki) — Guide exhaustif sur mécaniques, SRS et histoire du jeu.
- [Tetris Guideline](https://tetris.wiki/Tetris_Guideline) — Spécification officielle pour implémentations Tetris.