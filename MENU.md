# Menu Tree

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
│       │   └── Stratégies        [ENTER]          → placeholder
│       │       Hyperparamètres   [ENTER]          → Epsilon decay, Epsilon fin, LR, Gamma, Batch, Buffer, Target sync
│       Statistiques              [ENTER]          → stats + graph (une page)
│       Réinitialiser IA          [ENTER ×2]       supprime modèle + log
│       Retour                    [ENTER | ESC]
├── Démarrer le jeu               [ENTER]          → GameState | AIState
├── Leaderboard                   [ENTER]          → LeaderboardState
└── Quitter                       [ENTER | ESC]    exit
```

## Not yet implemented

- [x] **Touches** (Humain > Touches) — configurable keybindings for the human player
- [x] **Statistiques** (Humain > Statistiques) — human player statistics page
- [ ] **Stratégies** (IA > Apprentissage > Stratégies) — multiple learning strategies selection
- [x] **Hyperparamètres** (IA > Apprentissage > Hyperparamètres) — Epsilon decay, Epsilon fin, Learning rate, Gamma, Batch size, Buffer size, Target sync steps (all configurable via ◄ ► toggles, persisted to settings.json)