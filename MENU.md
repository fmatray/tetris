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

## Not yet implemented

- [x] **Touches** (Humain > Touches) — configurable keybindings for the human player
- [x] **Statistiques** (Humain > Statistiques) — human player statistics page
- [x] **Hyperparamètres** (IA > Apprentissage) — Epsilon decay, Epsilon fin, Learning rate, Gamma, Batch size, Buffer size, Target sync steps (all configurable via ◄ ► toggles, persisted to settings.json)