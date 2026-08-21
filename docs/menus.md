(Created: 2026-08-10)

## Arborescence des menus

```
Menu principal
├── Démarrer le jeu               [ENTER]          → lance la partie (Humain, IA ou MCP selon Joueur)
├── Joueur                        [toggle ◄ ►]     Humain ↔ IA ↔ MCP
├── Humain                        [ENTER]          (grisé si Joueur≠Humain)
│   └── Mode                      [toggle ◄ ►]     Normal ↔ Replay
│       Touches                   [ENTER]          → keybinding config
│       Statistiques              [ENTER]          → human stats page
│       Retour                    [ENTER | ESC]
├── IA                            [ENTER]          (grisé si Joueur≠IA)
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
├── MCP                            [ENTER]          (grisé si Joueur≠MCP)
│   └── Port                       [toggle ◄ ►]     8765 ↔ 8766 ↔ 8767 ↔ 8768
│       Retour                    [ENTER | ESC]
├── Règles du jeu                 [ENTER]          → game rules submenu
│   └── Générateur                [toggle ◄ ►]     Aléatoire ↔ 7-bag ↔ 35-bag ↔ Pondéré
│       Prévisualisation          [toggle ◄ ►]     Désactivé ↔ 1 pièce ↔ 3 pièces
│       Handicap                  [toggle ◄ ►]     0–5
│       Vitesse                   [toggle ◄ ►]     Aucune ↔ Facile ↔ Normal ↔ Moyen ↔ Difficile ↔ Fou ↔ Infernal
│       Fantôme                   [toggle ◄ ►]     ON ↔ OFF
│       Retour                    [ENTER | ESC]
├── Leaderboard                   [ENTER]          → top 10 scores
├── Audio                         [ENTER]          → audio submenu
│   └── Son                       [toggle ◄ ►]     Off ↔ Faible ↔ Moitié ↔ Max
│       Musique                   [toggle ◄ ►]     Off ↔ Faible ↔ Moitié ↔ Max
│       Morceau                   [toggle ◄ ►]     Korobeiniki ↔ Kalinka
│       Retour                    [ENTER | ESC]
├── Débogage                      [toggle ◄ ►]     ON ↔ OFF
└── Quitter                       [ENTER | ESC]
```

## Animation de fond

Les menus affichent une animation de fond: des tétraminos (max
`MENU_ANIM_MAX_PIECES`) tombent lentement depuis le haut de l'écran, en
partant d'une position x aléatoire. Chaque tétromino tourne aléatoirement
(horaire ou anti-horaire). Après un délai, il peut exploser en une animation
de particules; sinon il disparaît en s'estompant près du bas de l'écran. Les
couleurs classiques des tétriminos sont respectées (`SHAPES_COLORS`). Les
constantes sont dans `tetris/settings.py` (préfixe `MENU_ANIM_`).

### Architecture

| Composant | Rôle |
|---|---|
| `tetris/visuals/menu_animation.py` | `MenuBackgroundAnimation` (gestion du pool) + `_FallingPiece` (pièce individuelle) |
| `tetris/states/menu_base.py` | `MenuBase.__init__` crée l'instance; `update()` pilote l'animation; `draw()` dessine fond → animation → particules → UI |
| `tetris/states/hyperparam_menu.py` | `draw()` surchargé: même ordre de dessin mais layout multi-colonnes |
| `tetris/visuals/particles.py` | `ParticleSystem` partagé pour les explosions |

Chaque état de menu possède sa propre instance de `MenuBackgroundAnimation`
(créée dans `MenuBase.__init__`). L'animation redémarre donc à chaque
transition de menu — acceptable pour un fond purement décoratif.

### Cycle de vie d'une pièce

1. **Spawn**: x aléatoire, y juste au-dessus de l'écran. Timer de spawn
   re-rolé dans `[MIN, MAX]_SPAWN_INTERVAL`.
2. **Chute**: `y += FALL_SPEED × dt`; rotation aléatoire quand
   `rot_timer` expire.
3. **Explosion** (aléatoire): après `explode_delay` secondes (rolé une fois
   à la construction), `EXPLODE_CHANCE` est testé chaque frame. Si succès →
   émission de particules et suppression.
4. **Fondu** (sinon): `fade_alpha()` passe linéairement de 1.0 à 0 dans les
   derniers `FADE_DISTANCE` px. Suppression quand alpha = 0 et hors-écran.

### Constantes (`tetris/settings.py`)

| Constante | Valeur par défaut | Description |
|---|---|---|
| `MENU_ANIM_MAX_PIECES` | 7 | Nombre max de tétrominos simultanés |
| `MENU_ANIM_BLOCK_SIZE` | 20 | Taille de bloc (px) |
| `MENU_ANIM_FALL_SPEED` | 35 | Vitesse de chute (px/s) |
| `MENU_ANIM_MIN_SPAWN_INTERVAL` | 0.5 | Interval de spawn min (s) |
| `MENU_ANIM_MAX_SPAWN_INTERVAL` | 5.0 | Interval de spawn max (s) |
| `MENU_ANIM_ROT_INTERVAL` | (1.5, 4.0) | Seconds entre rotations |
| `MENU_ANIM_ROT_CHANCE` | 0.5 | Probabilité rotation CW vs CCW |
| `MENU_ANIM_EXPLODE_DELAY` | (5.0, 16.0) | Délai avant test d'explosion (s) |
| `MENU_ANIM_EXPLODE_CHANCE` | 0.01 | Probabilité par frame après délai |
| `MENU_ANIM_EXPLODE_PARTICLES` | 80 | Particules par explosion |
| `MENU_ANIM_FADE_DISTANCE` | 100 | Distance de fondu depuis le bas (px) |