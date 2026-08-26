# Tetris Python

Un jeu Tetris complet développé en Python avec Pygame, incluant des effets visuels spectaculaires, un système de son procédural, un leaderboard et une animation de fin de partie extravagante.

## Fonctionnalités

### Gameplay

- ✅ Mécaniques de Tetris classiques (rotation, déplacement, chute)
- ✅ Système de score standard (Guideline Tetris) : Single 100×niveau, Double 300×niveau, Triple 500×niveau, Tetris 800×niveau, combos 50×compteur×niveau, chute douce 1 pt/case, chute rapide 2 pts/case
- ✅ Niveaux progressifs (la vitesse augmente selon `0.5 × 0.98^niveau` toutes les 10 lignes)
- ✅ Handicap personnalisable (0-5, chaque niveau ajoute 2 rangées partielles de blocs gris en bas)

- ✅ **Diagnostic des trous et surplombs** : option « Trous et surplombs » (menu Règles du jeu) affichant des marqueurs blancs sur la grille — `X` = trou inaccessible depuis le haut, `O` = surplomb atteignable mais recouvert. L'IA intègre aussi une pénalité sur les surplombs dans sa récompense.

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

### Débogage

- ✅ **Mode Débogage** : Option activable dans le menu principal (Débogage ON/OFF). Journalise les événements de jeu (apparition de pièces, verrouillage, fin de partie, épisodes IA, curriculum) dans `data/debug.log` via Python `logging`. Visualise le contenu restant du sac 7-bag (pièces colorées avec lettres) à droite de l'aperçu de la prochaine pièce. Pendant le jeu, la touche **`d`** active/désactive l'overlay visuel de débogage (Humain, IA, MCP).

### Expérience utilisateur
- ✅ Menu de démarrage avec sélection du joueur (Humain/IA), du son, du générateur (Aléatoire/7-bag), du débogage (ON/OFF), et sous-menus dédiés.
- ✅ **Sous-menu Humain** : Mode (Normal/Replay), Handicap (0-5), Touches (touches configurables), Statistiques (page de statistiques du joueur humain).
- ✅ **Sous-menu IA** : Mode (Apprentissage/Jeu), Vitesse (normal/rapide), Apprentissage (13 hyperparamètres DQN : Epsilon decay, Epsilon fin, Learning rate, Gamma, Batch size, Buffer size, Curriculum, Fréq. curriculum, Epsilon curr., Warm-start, Maj. par pièce, Look-ahead, Soft-drop — configurables via ◄ ►, persistés dans `settings.json`, reset aux valeurs par défaut), Statistiques (tableau + graphique score/épisode), Réinitialiser IA, Retour.
- ✅ **Touches configurables** : 7 actions (gauche, droite, rotation horaire/anti-horaire, chute douce, chute rapide, pause) reconfigurables via le menu. Détection de conflits et touches réservées. Persistance dans `settings.json`.
- ✅ Saisie du nom (15 caractères max) en fin de partie.
- ✅ Leaderboard top 10 persistant (JSON).
- ✅ Retour automatique au menu principal après le leaderboard.
- ✅ **Joueur IA (V-network DQN)** : Mode apprentissage par renforcement (Deep Q-Learning). L'IA apprend à jouer de manière autonome, à vitesse humaine, et affiche ses statistiques d'apprentissage en temps réel : paramètres d'entraînement (mode, vitesse, épisode, epsilon, decay, perte, look-ahead, soft-drop, maj/pièce) et tableau de statistiques (pièces, lignes, score, niveau — courant, total, meilleur, moyenne, 100 derniers, tendance ↑/↓/→). Évaluation par candidat (V-function) avec features DT-20 normalisées, PBRS (Dellacherie, scale 0.1), Prioritized Experience Replay, n-step returns (3-step), soft-drop BFS avec SRS wall kicks, 2-piece look-ahead. Paramètres ε configurables (decay, fin) persistés dans `settings.json`. Mode Jeu (greedy, sans apprentissage) ou Apprentissage (exploration ε-greedy).

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

## Documentation Technique

La documentation détaillée se trouve dans le dossier `docs/` :

| Document | Description |
| -------- | -------- |
| [Architecture](docs/architecture.md) | Architecture technique, structure du projet et principes de conception |
| [IA](docs/ai.md) | Design document du mode joueur IA (V-network DQN) |
| [Menus](docs/menus.md) | Arborescence complète des menus |
| [Personnalisation](docs/customization.md) | Paramètres configurables |
| [Roadmap](docs/roadmap.md) | État d'avancement et améliorations futures |

## Crédits

Développé par Frédéric Matray
Musique et effets sonores générés procéduralement avec NumPy.

## Licence

MIT License - Libre d'utilisation et de modification

## Références

- [Tetris Wiki](https://tetris.wiki) — Guide exhaustif sur mécaniques, SRS et histoire du jeu.
- [Harddrop tetris wiki](https://harddrop.com/wiki/Tetris_Wiki) - Un autre wiki sur tetris 
- [Pygame CE](https://pygame-ce.org) — Documentation de l'extension Community Edition de Pygame.
- [PyTorch Documentation](https://pytorch.org/docs/) — Référence pour l'implémentation du réseau de neurones DQN.
- [Deep Q-Learning (Nature)](https://www.nature.com/articles/nature14236) — Article fondateur sur les réseaux DQN.
