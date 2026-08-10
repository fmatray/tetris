(Created: 2026-08-10)

## Arborescence des menus

```
Menu principal
├── Joueur                        [toggle ◄ ►]     Humain ↔ IA
├── Son                           [toggle ◄ ►]     ON ↔ OFF
├── Générateur                    [toggle ◄ ►]     Aléatoire ↔ 7-bag
├── Débogage                      [toggle ◄ ►]     ON ↔ OFF
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
│       │       Gamma             [toggle ◄ ►]     0.80–0.99
│       │       Batch size        [toggle ◄ ►]     8–256
│       │       Buffer size       [toggle ◄ ►]     1000–200000
│       │       Curriculum        [toggle ◄ ►]     OFF ↔ ON
│       │       Fréq. curriculum  [toggle ◄ ►]     10–500
│       │       Epsilon curr.     [toggle ◄ ►]     reset/boost/decay
│       │       Warm-start        [toggle ◄ ►]     OFF ↔ ON
│       │       Maj. par pièce    [toggle ◄ ►]     1–8
│       │       Look-ahead        [toggle ◄ ►]     OFF ↔ ON
│       │       Soft-drop         [toggle ◄ ►]     OFF ↔ ON
│       │       Réinitialiser     [ENTER]          reset to defaults
│       │       Retour            [ENTER | ESC]
│       Statistiques              [ENTER]          → stats + graph (une page)
│       Réinitialiser IA          [ENTER ×2]       supprime modèle + log
│       Retour                    [ENTER | ESC]
```