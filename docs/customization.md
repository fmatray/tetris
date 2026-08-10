(Created: 2026-08-10)

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

### Mode débogage

Le mode débogage est activable depuis le menu principal (option Débogage ON/OFF, persisté dans `settings.json` clé `debug`). Quand activé :
- Les événements de jeu sont journalisés dans `data/debug.log` (Python `logging`, niveau DEBUG).
- Le contenu restant du sac 7-bag est affiché à droite de l'aperçu de la prochaine pièce (uniquement avec le générateur 7-bag).