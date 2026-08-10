(Created: 2026-08-10)

## Roadmap

Un mode **Joueur IA** basé sur le V-network DQN est implémenté dans le package `tetris/ai/` et intégré via `AIState` (voir [ai.md](ai.md) pour le design détaillé). L'IA dispose de deux modes : **Apprentissage** (exploration ε-greedy, sauvegarde du modèle et du journal) et **Jeu** (greedy, sans apprentissage). L'IA apprend en jouant de manière autonome, à cadence humaine (~12 actions/sec), avec évaluation par candidat (soft-drop BFS + SRS wall kicks), features DT-20 normalisées, PBRS Dellacherie (scale 0.1), Prioritized Experience Replay, n-step returns (3-step), 2-piece look-ahead, récompense delta-based, paramètres ε configurables, tableau de statistiques avec tendances, et sauvegarde du modèle, des statistiques et des préférences entre les sessions.

Le **menu** est structuré en arborescence (voir [menus.md](menus.md)) : sous-menu Humain (mode, handicap, touches configurables, statistiques) et sous-menu IA (mode, vitesse, apprentissage, statistiques, reset). Les touches du joueur humain sont entièrement reconfigurables avec détection de conflits et persistance.

Améliorations futures possibles : Stratégies d'apprentissage multiples, MCTS, Self-Play Tournament, Human Replay (imitation learning).