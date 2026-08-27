#!/usr/bin/env python3
"""Analyse les logs d'entraînement IA et affiche un rapport de santé.

Usage: python scripts/analyze_training.py [--charts]
  --charts  Sauvegarder les graphiques dans data/analysis/

Lecture seule — ne modifie aucun fichier de données existant.
"""

from __future__ import annotations

import json
import os
import statistics
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless — pas de fenêtre GUI

import matplotlib.pyplot as plt

# Thème sombre (identique à tetris/visuals/graph_view.py)
_BG = (0.0, 0.0, 0.0)
_FG = (1.0, 1.0, 1.0)
_GRID = (0.235, 0.235, 0.235)

# Drapeaux de santé
OK = "[OK]"
WARN = "[ATTN]"
CRIT = "[CRIT]"

# Seuils
LOSS_WARN = 100.0
GRAD_WARN = 50.0
GRAD_CRIT = 100.0
TD_WARN = 200.0
SUCCESS_WARN = 0.90
SKEW_WARN = 0.40

# Composantes de récompense
REWARD_COMPONENTS = [
    "reward_lines",
    "reward_holes_delta",
    "reward_overhangs",
    "reward_height",
    "reward_bumpiness",
    "reward_wells",
    "reward_survival",
    "reward_pbrs",
    "reward_game_over",
]
REWARD_LABELS = {
    "reward_lines": "Lignes",
    "reward_holes_delta": "Trous",
    "reward_overhangs": "Surplombs",
    "reward_height": "Hauteur",
    "reward_bumpiness": "Irregularité",
    "reward_wells": "Puits",
    "reward_survival": "Survie",
    "reward_pbrs": "PBRS",
    "reward_game_over": "Game Over",
}


# ──────────────────────────────────────────────────────────────
#  Chargement des logs
# ──────────────────────────────────────────────────────────────


def load_training_log(path: str) -> list[dict] | None:
    """Charge le log d'entraînement JSON (liste d'épisodes)."""
    p = Path(path)
    if not p.exists():
        print(f"  [!] Log d'entraînement introuvable: {path}", file=sys.stderr)
        return None
    try:
        data = json.loads(p.read_text())
        if not data:
            print(f"  [!] Log d'entraînement vide: {path}", file=sys.stderr)
            return None
        return data
    except (json.JSONDecodeError, OSError) as e:
        print(f"  [!] Erreur lecture log d'entraînement: {e}", file=sys.stderr)
        return None


def load_step_log(path: str) -> list[dict] | None:
    """Charge le log de pas JSONL (rotation à 100K lignes)."""
    p = Path(path)
    if not p.exists():
        print(f"  [!] Log de pas introuvable: {path}", file=sys.stderr)
        return None
    try:
        entries = []
        with open(p) as f:
            for line in f:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))
        if not entries:
            print(f"  [!] Log de pas vide: {path}", file=sys.stderr)
            return None
        return entries
    except (json.JSONDecodeError, OSError) as e:
        print(f"  [!] Erreur lecture log de pas: {e}", file=sys.stderr)
        return None


def load_behavior_log(path: str) -> list[dict] | None:
    """Charge le log comportemental JSONL (un entry par épisode)."""
    p = Path(path)
    if not p.exists():
        print(f"  [!] Log comportemental introuvable: {path}", file=sys.stderr)
        return None
    try:
        entries = []
        with open(p) as f:
            for line in f:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))
        if not entries:
            print(f"  [!] Log comportemental vide: {path}", file=sys.stderr)
            return None
        return entries
    except (json.JSONDecodeError, OSError) as e:
        print(f"  [!] Erreur lecture log comportemental: {e}", file=sys.stderr)
        return None


def load_tensorboard_summary(event_dir: str) -> dict | None:
    """TensorBoard désactivé — les logs de pas contiennent les mêmes métriques.

    Les fichiers d'événements TensorBoard peuvent dépasser 700Mo, rendant
    le chargement prohibitif. Le log de pas JSONL contient les mêmes
    métriques (loss, grad_norm, lr, etc.) dans un format léger.
    """
    return None


# ──────────────────────────────────────────────────────────────
#  Utilitaires
# ──────────────────────────────────────────────────────────────


def _trend(last_n: list, prev_n: list, key: str) -> str:
    """Compare la moyenne des derniers vs précédents (seuil 5%)."""
    if len(last_n) < 1 or len(prev_n) < 1:
        return "stable"
    recent = statistics.fmean(e.get(key, 0) for e in last_n)
    prev = statistics.fmean(e.get(key, 0) for e in prev_n)
    if prev == 0:
        return "up" if recent > 0 else "stable"
    ratio = recent / prev
    if ratio > 1.05:
        return "up"
    if ratio < 0.95:
        return "down"
    return "stable"


def _trend_pct(last_n: list, prev_n: list, key: str) -> str:
    """Retourne le pourcentage de changement formaté."""
    if len(last_n) < 1 or len(prev_n) < 1:
        return "N/A"
    recent = statistics.fmean(e.get(key, 0) for e in last_n)
    prev = statistics.fmean(e.get(key, 0) for e in prev_n)
    if prev == 0:
        return "N/A"
    pct = (recent - prev) / prev * 100
    return f"{pct:+.0f}%"


def _arrow(trend: str) -> str:
    return {"up": "↑", "down": "↓", "stable": "→"}.get(trend, "→")


def _moving_average(values: list, window: int) -> list:
    """Moyenne mobile simple (une valeur par entrée)."""
    if not values:
        return []
    out = []
    for i in range(len(values)):
        start = max(0, i - window + 1)
        chunk = values[start : i + 1]
        out.append(sum(chunk) / len(chunk))
    return out


def _percentiles(values: list) -> dict:
    """Retourne p10/p25/p50/p75/p90."""
    if not values:
        return {}
    sv = sorted(values)
    n = len(sv)
    return {
        "p10": sv[int(n * 0.10)],
        "p25": sv[int(n * 0.25)],
        "p50": sv[int(n * 0.50)],
        "p75": sv[int(n * 0.75)],
        "p90": sv[int(n * 0.90)],
    }


def _flag(value: float, warn: float, crit: float | None = None, higher_is_bad: bool = True) -> str:
    """Retourne un drapeau de santé selon les seuils."""
    if higher_is_bad:
        if crit is not None and value >= crit:
            return CRIT
        if value >= warn:
            return WARN
    else:
        if crit is not None and value <= crit:
            return CRIT
        if value <= warn:
            return WARN
    return OK


def _pearson(x: list, y: list) -> float:
    """Coefficient de corrélation de Pearson."""
    n = len(x)
    if n < 2:
        return 0.0
    mx = statistics.fmean(x)
    my = statistics.fmean(y)
    num = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y, strict=False))
    dx = (sum((xi - mx) ** 2 for xi in x)) ** 0.5
    dy = (sum((yi - my) ** 2 for yi in y)) ** 0.5
    if dx == 0 or dy == 0:
        return 0.0
    return num / (dx * dy)


# ──────────────────────────────────────────────────────────────
#  Analyse du log d'entraînement
# ──────────────────────────────────────────────────────────────


def analyze_training_log(episodes: list[dict]) -> dict:
    n = len(episodes)
    last = episodes[-1]
    last100 = episodes[-100:] if n >= 100 else episodes
    prev100 = episodes[-200:-100] if n >= 200 else []

    # Vue d'ensemble
    scores = [e["score"] for e in episodes]
    lines_list = [e["lines"] for e in episodes]
    steps_list = [e["steps"] for e in episodes]
    overview = {
        "episodes": n,
        "score_min": min(scores),
        "score_mean": statistics.fmean(scores),
        "score_median": statistics.median(scores),
        "score_max": max(scores),
        "lines_total": sum(lines_list),
        "lines_mean": statistics.fmean(lines_list),
        "steps_total": sum(steps_list),
        "steps_mean": statistics.fmean(steps_list),
        "first_ts": episodes[0].get("timestamp", "?"),
        "last_ts": last.get("timestamp", "?"),
    }

    # Tendances
    trend_keys = ["score", "lines", "steps", "loss", "avg_v_spread", "epsilon"]
    trends = {}
    for k in trend_keys:
        trends[k] = {
            "direction": _trend(last100, prev100, k),
            "pct": _trend_pct(last100, prev100, k),
        }

    # Dynamiques
    eps = last.get("epsilon", 0.0)
    eps_end = 0.1
    eps_range = 1.0 - eps_end
    eps_progress = 1.0 - (eps - eps_end) / eps_range if eps_range > 0 else 1.0

    lr_vals = [e.get("lr", 0) for e in episodes if e.get("lr", 0) > 0]
    lr_distinct = sorted(set(lr_vals), reverse=True)
    lr_current = last.get("lr", 0)
    lr_reductions = max(0, len(lr_distinct) - 1)

    loss100 = [e.get("avg_loss", 0) for e in last100]
    grad100 = [e.get("grad_norm", 0) for e in last100]
    td100 = [e.get("avg_td_error", 0) for e in last100]
    buffer_fill = last.get("buffer_fill", 0)
    buffer_max = max((e.get("buffer_fill", 0) for e in episodes), default=0)
    buffer_full_ep = None
    if buffer_max > 0:
        for e in episodes:
            if e.get("buffer_fill", 0) >= buffer_max:
                buffer_full_ep = e["episode"]
                break

    dynamics = {
        "epsilon": eps,
        "eps_progress": eps_progress,
        "eps_end": eps_end,
        "lr_current": lr_current,
        "lr_reductions": lr_reductions,
        "lr_distinct": lr_distinct,
        "loss_mean": statistics.fmean(loss100) if loss100 else 0,
        "loss_max": max(loss100) if loss100 else 0,
        "grad_mean": statistics.fmean(grad100) if grad100 else 0,
        "grad_max": max(grad100) if grad100 else 0,
        "td_mean": statistics.fmean(td100) if td100 else 0,
        "td_max": max(td100) if td100 else 0,
        "buffer_fill": buffer_fill,
        "buffer_max": buffer_max,
        "buffer_full_ep": buffer_full_ep,
        "target_syncs": last.get("target_syncs", 0),
        "beta": last.get("beta", 0),
        "beta_progress": (last.get("beta", 0.4) - 0.4) / 0.6,
    }

    # Cuisson (réplique de _cooking_status de hud.py)
    score_trend = _trend(last100, prev100, "score")
    v_spread = last.get("avg_v_spread", 0.0)
    ep_maturity = min(n / 500.0, 1.0)
    level = max(0.0, min(1.0, max(eps_progress, ep_maturity)))

    if n < 200 or eps > 0.3 or score_trend == "up":
        cooking_label = "Pas assez cuit"
        cooking_color = "blue"
    elif score_trend == "down" or v_spread < 0.01:
        cooking_label = "Trop cuit"
        cooking_color = "red"
    else:
        cooking_label = "Bien cuit"
        cooking_color = "green"

    cooking = {"label": cooking_label, "color": cooking_color, "level": level}

    # Décomposition des récompenses (derniers 100)
    reward_means = {}
    for comp in REWARD_COMPONENTS:
        vals = [e.get(comp, 0) for e in last100]
        reward_means[comp] = statistics.fmean(vals) if vals else 0
    neg_components = {k: v for k, v in reward_means.items() if v < 0}
    dominant_neg: str | None = None
    if neg_components:
        dominant_neg = min(neg_components, key=lambda k: reward_means[k])
    reward_trends = {}
    for comp in REWARD_COMPONENTS:
        reward_trends[comp] = _trend(last100, prev100, comp)

    rewards = {
        "means": reward_means,
        "dominant_neg": dominant_neg,
        "trends": reward_trends,
    }

    # Signaux comportementaux
    n_random100 = [e.get("n_random", 0) for e in last100]
    n_greedy100 = [e.get("n_greedy", 0) for e in last100]
    n_hold100 = [e.get("n_hold", 0) for e in last100]
    total_actions100 = [r + g for r, g in zip(n_random100, n_greedy100, strict=False)]
    exploration_rate = (
        statistics.fmean(r / t for r, t in zip(n_random100, total_actions100, strict=False) if t > 0)
        if total_actions100
        else 0
    )
    hold_rate = statistics.fmean(n_hold100) if n_hold100 else 0

    behavior_signals = {
        "exploration_rate": exploration_rate,
        "hold_rate": hold_rate,
        "avg_candidates": statistics.fmean([e.get("avg_candidates", 0) for e in last100]) if last100 else 0,
        "avg_move_len": statistics.fmean([e.get("avg_move_len", 0) for e in last100]) if last100 else 0,
        "candidates_trend": _trend(last100, prev100, "avg_candidates"),
        "move_len_trend": _trend(last100, prev100, "avg_move_len"),
    }

    return {
        "overview": overview,
        "trends": trends,
        "dynamics": dynamics,
        "cooking": cooking,
        "rewards": rewards,
        "behavior_signals": behavior_signals,
        "last100": last100,
        "prev100": prev100,
    }


# ──────────────────────────────────────────────────────────────
#  Analyse du log de pas
# ──────────────────────────────────────────────────────────────


def analyze_step_log(steps: list[dict]) -> dict:
    n = len(steps)

    losses = [s["loss"] for s in steps if "loss" in s]
    grads = [s["grad_norm"] for s in steps if "grad_norm" in s]
    td_means = [s["td_error_mean"] for s in steps if "td_error_mean" in s]
    td_maxes = [s["td_error_max"] for s in steps if "td_error_max" in s]
    lrs = [s["lr"] for s in steps if "lr" in s]
    buffers = [s["buffer_fill"] for s in steps if "buffer_fill" in s]
    epsilons = [s["epsilon"] for s in steps if "epsilon" in s]

    last1000_losses = losses[-1000:]
    last1000_grads = grads[-1000:]

    # LR: valeurs distinctes + transitions
    lr_distinct = sorted(set(lrs), reverse=True)
    lr_transitions = []
    for i in range(1, len(lrs)):
        if lrs[i] != lrs[i - 1]:
            lr_transitions.append({"step": steps[i].get("step", i), "from": lrs[i - 1], "to": lrs[i]})

    # TD error: première moitié vs seconde moitié
    half = n // 2
    td_first = statistics.fmean(td_means[:half]) if half > 0 and td_means[:half] else 0
    td_second = statistics.fmean(td_means[half:]) if td_means[half:] else 0

    # Grad instability
    grad_instability_pct = (sum(1 for g in grads if g > GRAD_WARN) / len(grads) * 100) if grads else 0

    # Buffer: quand il atteint le max
    buffer_max = max(buffers) if buffers else 0
    buffer_full_step = None
    if buffer_max > 0:
        for i, b in enumerate(buffers):
            if b >= buffer_max:
                buffer_full_step = i
                break

    # Epsilon: échantillonnage tous les 1000 pas
    eps_samples = epsilons[::1000] if epsilons else []

    return {
        "count": n,
        "loss": {
            "mean": statistics.fmean(losses) if losses else 0,
            "median": statistics.median(losses) if losses else 0,
            "max": max(losses) if losses else 0,
            "min": min(losses) if losses else 0,
            "pcts": _percentiles(losses),
            "last1000_mean": statistics.fmean(last1000_losses) if last1000_losses else 0,
        },
        "grad": {
            "mean": statistics.fmean(grads) if grads else 0,
            "max": max(grads) if grads else 0,
            "instability_pct": grad_instability_pct,
            "last1000_mean": statistics.fmean(last1000_grads) if last1000_grads else 0,
        },
        "td": {
            "mean": statistics.fmean(td_means) if td_means else 0,
            "max": max(td_maxes) if td_maxes else 0,
            "first_half": td_first,
            "second_half": td_second,
        },
        "lr": {
            "distinct": lr_distinct,
            "transitions": lr_transitions,
            "current": lrs[-1] if lrs else 0,
            "steps_at_min": sum(1 for lr in lrs if lr == min(lr_distinct)) if lr_distinct else 0,
        },
        "buffer": {
            "max": buffer_max,
            "full_step": buffer_full_step,
            "current": buffers[-1] if buffers else 0,
        },
        "epsilon": {
            "samples": eps_samples,
            "final": epsilons[-1] if epsilons else 0,
        },
        # Pour les graphiques
        "_losses": losses,
        "_grads": grads,
        "_lrs": lrs,
        "_buffers": buffers,
        "_epsilons": epsilons,
    }


# ──────────────────────────────────────────────────────────────
#  Analyse du log comportemental
# ──────────────────────────────────────────────────────────────


def analyze_behavior_log(behavior: list[dict]) -> dict:
    n = len(behavior)

    # Distribution des colonnes
    col_totals = [0] * 10
    for entry in behavior:
        col_hist = entry.get("col_hist", [])
        for i, c in enumerate(col_hist):
            if i < 10:
                col_totals[i] += c
    col_total = sum(col_totals) or 1
    col_dist = [c / col_total for c in col_totals]
    dominant_col = col_dist.index(max(col_dist)) if col_dist else 0
    is_skewed = max(col_dist) > SKEW_WARN if col_dist else False

    # Distribution des rotations
    rot_totals = [0, 0, 0, 0]
    for entry in behavior:
        rot_hist = entry.get("rot_hist", [])
        for i, r in enumerate(rot_hist):
            if i < 4:
                rot_totals[i] += r
    rot_total = sum(rot_totals) or 1
    rot_dist = [r / rot_total for r in rot_totals]
    rot_labels = ["0°", "90°", "180°", "270°"]
    avoided_rot = [rot_labels[i] for i, d in enumerate(rot_dist) if d < 0.05]

    # Taux de succès
    success_rates = [e.get("placement_success_rate", 1.0) for e in behavior]
    success_mean = statistics.fmean(success_rates) if success_rates else 1.0
    success_min = min(success_rates) if success_rates else 1.0

    # Tendance du taux de succès
    last100_s = success_rates[-100:] if len(success_rates) >= 100 else success_rates
    prev100_s = success_rates[-200:-100] if len(success_rates) >= 200 else []
    success_trend = "stable"
    if prev100_s:
        recent_avg = statistics.fmean(last100_s)
        prev_avg = statistics.fmean(prev100_s)
        if prev_avg > 0:
            ratio = recent_avg / prev_avg
            success_trend = "up" if ratio > 1.05 else ("down" if ratio < 0.95 else "stable")

    # Corrélation score vs taux de succès
    scores_b = [e.get("score", 0) for e in behavior]
    success_b = [e.get("placement_success_rate", 1.0) for e in behavior]
    pearson = _pearson(scores_b, success_b)

    return {
        "count": n,
        "col_dist": col_dist,
        "col_totals": col_totals,
        "dominant_col": dominant_col,
        "is_skewed": is_skewed,
        "rot_dist": rot_dist,
        "rot_totals": rot_totals,
        "rot_labels": rot_labels,
        "avoided_rot": avoided_rot,
        "success_mean": success_mean,
        "success_min": success_min,
        "success_trend": success_trend,
        "pearson_score_success": pearson,
    }


# ──────────────────────────────────────────────────────────────
#  Formatage du rapport
# ──────────────────────────────────────────────────────────────


def print_report(analysis: dict) -> None:
    sep = "═" * 60

    print(f"\n{sep}")
    print("  RAPPORT D'ANALYSE D'ENTRAÎNEMENT IA")
    print(sep)

    # Vue d'ensemble
    if "training" in analysis:
        t = analysis["training"]
        ov = t["overview"]
        print("\n=== Vue d'ensemble ===")
        print(f"  Épisodes: {ov['episodes']}")
        print(
            f"  Score:  min={ov['score_min']}  moy={ov['score_mean']:.0f}  méd={ov['score_median']:.0f}  max={ov['score_max']}"
        )
        print(f"  Lignes: total={ov['lines_total']}  moy={ov['lines_mean']:.1f}/ép")
        print(f"  Pas:    total={ov['steps_total']}  moy={ov['steps_mean']:.1f}/ép")
        print(f"  Période: {ov['first_ts']} → {ov['last_ts']}")

        # Tendances
        print("\n=== Tendances (100 derniers vs 100 précédents) ===")
        tr = t["trends"]
        trend_labels = {
            "score": "Score",
            "lines": "Lignes",
            "steps": "Pas/ép",
            "loss": "Perte",
            "avg_v_spread": "V-spread",
            "epsilon": "Epsilon",
        }
        for k, label in trend_labels.items():
            if k in tr:
                d = tr[k]
                print(f"  {label:12s} {d['pct']:>8s} {_arrow(d['direction'])} {d['direction']}")

        # Dynamiques
        print("\n=== Dynamiques d'entraînement ===")
        dy = t["dynamics"]

        eps_flag = OK if dy["eps_progress"] > 0.5 else WARN
        print(f"  Epsilon: {dy['epsilon']:.3f} (décroissance {dy['eps_progress']:.0%})  {eps_flag}")

        lr_flag = OK if dy["lr_reductions"] <= 5 else WARN
        print(f"  LR: {dy['lr_current']:.1e} ({dy['lr_reductions']} réductions)  {lr_flag}")

        loss_flag = _flag(dy["loss_mean"], LOSS_WARN)
        print(f"  Perte (100 der): moy={dy['loss_mean']:.1f}  max={dy['loss_max']:.1f}  {loss_flag}")

        grad_flag = _flag(dy["grad_max"], GRAD_WARN, GRAD_CRIT)
        print(f"  Grad norm (100 der): moy={dy['grad_mean']:.1f}  max={dy['grad_max']:.1f}  {grad_flag}")

        td_flag = _flag(dy["td_mean"], TD_WARN)
        print(f"  TD erreur (100 der): moy={dy['td_mean']:.1f}  max={dy['td_max']:.1f}  {td_flag}")

        buf_flag = OK if dy["buffer_fill"] >= dy["buffer_max"] * 0.9 else WARN
        buf_full = f" (plein à ép {dy['buffer_full_ep']})" if dy["buffer_full_ep"] else ""
        print(f"  Buffer: {dy['buffer_fill']}/{dy['buffer_max']}{buf_full}  {buf_flag}")

        print(f"  Target syncs: {dy['target_syncs']}")
        print(f"  Beta (PER): {dy['beta']:.2f} (progression {dy['beta_progress']:.0%})")

        # Cuisson
        print("\n=== Cuisson ===")
        ck = t["cooking"]
        print(f"  État: {ck['label']}  (niveau {ck['level']:.0%})")

        # Décomposition des récompenses
        print("\n=== Décomposition des récompenses (100 derniers) ===")
        rw = t["rewards"]
        for comp in REWARD_COMPONENTS:
            label = REWARD_LABELS.get(comp, comp)
            val = rw["means"][comp]
            trend = rw["trends"].get(comp, "stable")
            print(f"  {label:12s} {val:>8.2f}  {_arrow(trend)}")
        if rw["dominant_neg"]:
            print(f"  → Négatif dominant: {REWARD_LABELS.get(rw['dominant_neg'], rw['dominant_neg'])}")

        # Signaux comportementaux
        print("\n=== Signaux comportementaux (100 derniers) ===")
        bs = t["behavior_signals"]
        print(f"  Taux d'exploration: {bs['exploration_rate']:.1%} (random/total)")
        print(f"  Taux de hold: {bs['hold_rate']:.1f}/ép")
        print(f"  Candidats moyens: {bs['avg_candidates']:.1f} {_arrow(bs['candidates_trend'])}")
        print(f"  Longueur moyenne des mouvements: {bs['avg_move_len']:.1f} {_arrow(bs['move_len_trend'])}")

    # Log de pas
    if "steps" in analysis:
        s = analysis["steps"]
        print("\n=== Log de pas ===")
        print(f"  Entrées: {s['count']}")

        lo = s["loss"]
        print(f"  Perte: moy={lo['mean']:.1f}  méd={lo['median']:.1f}  min={lo['min']:.1f}  max={lo['max']:.1f}")
        pcts = lo["pcts"]
        if pcts:
            print(
                f"    Percentiles: p10={pcts['p10']:.1f}  p25={pcts['p25']:.1f}  p50={pcts['p50']:.1f}  p75={pcts['p75']:.1f}  p90={pcts['p90']:.1f}"
            )
        print(f"    1000 derniers: moy={lo['last1000_mean']:.1f}")

        gr = s["grad"]
        grad_flag = _flag(gr["max"], GRAD_WARN, GRAD_CRIT)
        print(
            f"  Gradient: moy={gr['mean']:.1f}  max={gr['max']:.1f}  instabilité={gr['instability_pct']:.1f}%  {grad_flag}"
        )

        td = s["td"]
        td_dir = "↓" if td["second_half"] < td["first_half"] else ("↑" if td["second_half"] > td["first_half"] else "→")
        td_flag = _flag(td["mean"], TD_WARN)
        print(
            f"  TD erreur: moy={td['mean']:.1f}  max={td['max']:.1f}  1ère→2ème moitié: {td['first_half']:.1f}→{td['second_half']:.1f} {td_dir}  {td_flag}"
        )

        lr = s["lr"]
        lr_flag = OK if lr["steps_at_min"] < s["count"] * 0.8 else WARN
        print(
            f"  LR: actuel={lr['current']:.1e}  valeurs={len(lr['distinct'])}  pas au min={lr['steps_at_min']}  {lr_flag}"
        )
        if lr["transitions"]:
            print(f"    Transitions: {len(lr['transitions'])}")
            for tr in lr["transitions"][:5]:
                print(f"      pas {tr['step']}: {tr['from']:.1e} → {tr['to']:.1e}")

        bu = s["buffer"]
        buf_flag = OK if bu["current"] >= bu["max"] * 0.9 else WARN
        full_info = f" (plein au pas #{bu['full_step']})" if bu["full_step"] else ""
        print(f"  Buffer: {bu['current']}/{bu['max']}{full_info}  {buf_flag}")

        ep = s["epsilon"]
        print(f"  Epsilon: final={ep['final']:.4f}  échantillons={len(ep['samples'])}")

    # Log comportemental
    if "behavior" in analysis:
        b = analysis["behavior"]
        print("\n=== Log comportemental ===")
        print(f"  Entrées: {b['count']}")

        col_flag = WARN if b["is_skewed"] else OK
        print(f"  Distribution des colonnes (col la plus utilisée: {b['dominant_col']})  {col_flag}")
        col_bar = "  "
        for i, d in enumerate(b["col_dist"]):
            bar_len = int(d * 40)
            col_bar += f"  c{i}: [{'#' * bar_len}{' ' * (40 - bar_len)}] {d:.1%}\n  "
        print(col_bar.rstrip())

        print("  Rotations:")
        for i, (label, d) in enumerate(zip(b["rot_labels"], b["rot_dist"], strict=False)):
            rot_flag = WARN if d < 0.05 else OK
            print(f"    {label}: {d:.1%}  {rot_flag}")
        if b["avoided_rot"]:
            print(f"  → Rotations évitées: {', '.join(b['avoided_rot'])}  {WARN}")

        success_flag = _flag(b["success_mean"], SUCCESS_WARN, higher_is_bad=False)
        print(
            f"  Taux de succès: moy={b['success_mean']:.1%}  min={b['success_min']:.1%}  tendance={b['success_trend']}  {success_flag}"
        )

        p = b["pearson_score_success"]
        corr_label = "positive" if p > 0.1 else ("négative" if p < -0.1 else "négligeable")
        print(f"  Corrélation score↔succès: r={p:.3f} ({corr_label})")

    # Recommandations
    print("\n=== Recommandations ===")
    _print_recommendations(analysis)

    print(f"\n{sep}\n")


def _print_recommendations(analysis: dict) -> None:
    """Génère des recommandations basées sur les seuils."""
    recs = []

    if "training" in analysis:
        t = analysis["training"]
        dy = t["dynamics"]
        ck = t["cooking"]

        if ck["color"] == "blue":
            recs.append("• Entraînement en cours — continuer à entraîner pour convergence")
        elif ck["color"] == "red":
            recs.append("• SURCUISSON: score stagne ou baisse — envisager early stopping ou reset LR")

        if dy["lr_reductions"] >= 5 and dy["lr_current"] <= 1e-6:
            recs.append("• LR au minimum (plateau) — envisager un reset de LR ou un nouveau cycle")

        if dy["loss_mean"] > LOSS_WARN:
            recs.append(
                f"• Perte élevée ({dy['loss_mean']:.0f}) — vérifier le taux d'apprentissage ou la taille du batch"
            )

        if dy["grad_max"] > GRAD_CRIT:
            recs.append(f"• Gradient explosif (max {dy['grad_max']:.0f}) — envisager gradient clipping")

        if dy["td_mean"] > TD_WARN:
            recs.append(
                f"• TD erreur élevée ({dy['td_mean']:.0f}) — la cible est loin — vérifier gamma ou fréquence de sync cible"
            )

        bs = t["behavior_signals"]
        if bs["exploration_rate"] > 0.7:
            recs.append(
                f"• Exploration dominante ({bs['exploration_rate']:.0%}) — epsilon encore élevé, plus de temps nécessaire"
            )

    if "steps" in analysis:
        s = analysis["steps"]
        if s["grad"]["instability_pct"] > 10:
            recs.append(
                f"• {s['grad']['instability_pct']:.0f}% des pas ont grad > {GRAD_WARN} — gradient clipping recommandé"
            )

    if "behavior" in analysis:
        b = analysis["behavior"]
        if b["is_skewed"]:
            recs.append(
                f"• Placement déséquilibré (col {b['dominant_col']} surutilisé) — la politique évite une partie du plateau"
            )
        if b["success_mean"] < SUCCESS_WARN:
            recs.append(f"• Taux de succès faible ({b['success_mean']:.0%}) — vérifier l'exécution des placements")
        if b["avoided_rot"]:
            recs.append(
                f"• Rotations évitées: {', '.join(b['avoided_rot'])} — la politique n'explore pas toutes les orientations"
            )

    if not recs:
        recs.append("• Aucune anomalie détectée — l'entraînement semble sain")

    for r in recs:
        print(f"  {r}")


# ──────────────────────────────────────────────────────────────
#  Graphiques (optionnel)
# ──────────────────────────────────────────────────────────────


def save_charts(analysis: dict, output_dir: str) -> list[str]:
    """Sauvegarde les graphiques dans output_dir. Retourne les chemins créés."""
    os.makedirs(output_dir, exist_ok=True)
    saved: list[str] = []

    # 1. Courbe de score
    if "training" in analysis:
        all_eps = analysis["training"].get("_all_episodes", [])
        if all_eps:
            ep_nums = [e["episode"] for e in all_eps]
            scores = [e["score"] for e in all_eps]
            fig, ax = plt.subplots(figsize=(11, 6), dpi=100)
            fig.patch.set_facecolor(_BG)
            ax.set_facecolor(_BG)
            ax.plot(ep_nums, scores, color="cyan", linewidth=0.8, alpha=0.6, label="Score")
            ma = _moving_average(scores, min(20, len(scores)))
            ax.plot(ep_nums, ma, color="yellow", linewidth=1.8, label="Moy. 20")
            ax.legend(facecolor=_BG, edgecolor=_FG, labelcolor=_FG)
            ax.set_xlabel("Épisode", color=_FG, fontsize=12)
            ax.set_ylabel("Score", color=_FG, fontsize=12)
            ax.set_title("Score par épisode", color=_FG, fontsize=16)
            ax.tick_params(colors=_FG)
            for spine in ax.spines.values():
                spine.set_color(_FG)
            ax.grid(True, color=_GRID, alpha=0.5)
            path = os.path.join(output_dir, "score_curve.png")
            fig.savefig(path, facecolor=_BG)
            plt.close(fig)
            saved.append(path)

        # 4. Heatmap colonnes
        if "behavior" in analysis:
            b = analysis["behavior"]
            fig, ax = plt.subplots(figsize=(8, 4), dpi=100)
            fig.patch.set_facecolor(_BG)
            ax.set_facecolor(_BG)
            colors = ["#e74c3c" if d > SKEW_WARN else "#3498db" for d in b["col_dist"]]
            ax.bar(range(10), b["col_dist"], color=colors, edgecolor=_FG, linewidth=0.5)
            ax.set_xlabel("Colonne", color=_FG, fontsize=12)
            ax.set_ylabel("Proportion", color=_FG, fontsize=12)
            ax.set_title("Distribution des placements par colonne", color=_FG, fontsize=14)
            ax.tick_params(colors=_FG)
            for spine in ax.spines.values():
                spine.set_color(_FG)
            ax.grid(True, color=_GRID, alpha=0.5, axis="y")
            path = os.path.join(output_dir, "column_heatmap.png")
            fig.savefig(path, facecolor=_BG)
            plt.close(fig)
            saved.append(path)

        # 5. Dynamiques (4 sous-graphiques)
        if "steps" in analysis:
            s = analysis["steps"]
            fig, axes = plt.subplots(2, 2, figsize=(12, 8), dpi=100)
            fig.patch.set_facecolor(_BG)

            sample_step = max(1, len(s["_losses"]) // 1000)

            ax = axes[0, 0]
            ax.set_facecolor(_BG)
            xs = range(0, len(s["_losses"]), sample_step)
            ax.plot(xs, s["_losses"][::sample_step], color="red", linewidth=0.8, alpha=0.7)
            ax.set_title("Perte", color=_FG, fontsize=12)
            ax.tick_params(colors=_FG, labelsize=8)
            ax.grid(True, color=_GRID, alpha=0.5)

            ax = axes[0, 1]
            ax.set_facecolor(_BG)
            ax.plot(xs, s["_grads"][::sample_step], color="orange", linewidth=0.8, alpha=0.7)
            ax.set_title("Norme de gradient", color=_FG, fontsize=12)
            ax.tick_params(colors=_FG, labelsize=8)
            ax.grid(True, color=_GRID, alpha=0.5)

            ax = axes[1, 0]
            ax.set_facecolor(_BG)
            ax.plot(xs, s["_lrs"][::sample_step], color="green", linewidth=1.0)
            ax.set_title("Taux d'apprentissage", color=_FG, fontsize=12)
            ax.tick_params(colors=_FG, labelsize=8)
            ax.set_yscale("log")
            ax.grid(True, color=_GRID, alpha=0.5)

            ax = axes[1, 1]
            ax.set_facecolor(_BG)
            ax.plot(xs, s["_buffers"][::sample_step], color="cyan", linewidth=0.8, alpha=0.7)
            ax.set_title("Remplissage du buffer", color=_FG, fontsize=12)
            ax.tick_params(colors=_FG, labelsize=8)
            ax.grid(True, color=_GRID, alpha=0.5)

            for row in axes:
                for sp in row:
                    for spine in sp.spines.values():
                        spine.set_color(_FG)

            fig.suptitle("Dynamiques d'entraînement", color=_FG, fontsize=16)
            fig.tight_layout()
            path = os.path.join(output_dir, "dynamics.png")
            fig.savefig(path, facecolor=_BG)
            plt.close(fig)
            saved.append(path)

        # 3. Décomposition des récompenses
        if "rewards" in analysis.get("training", {}):
            rw = analysis["training"]["rewards"]
            labels = [REWARD_LABELS.get(c, c) for c in REWARD_COMPONENTS]
            values = [rw["means"][c] for c in REWARD_COMPONENTS]
            colors = ["#2ecc71" if v >= 0 else "#e74c3c" for v in values]

            fig, ax = plt.subplots(figsize=(10, 5), dpi=100)
            fig.patch.set_facecolor(_BG)
            ax.set_facecolor(_BG)
            ax.barh(range(len(labels)), values, color=colors, edgecolor=_FG, linewidth=0.5)
            ax.set_yticks(range(len(labels)))
            ax.set_yticklabels(labels, color=_FG)
            ax.set_xlabel("Récompense moyenne", color=_FG, fontsize=12)
            ax.set_title("Décomposition des récompenses (100 derniers)", color=_FG, fontsize=14)
            ax.tick_params(colors=_FG)
            ax.axvline(0, color=_FG, linewidth=0.8)
            for spine in ax.spines.values():
                spine.set_color(_FG)
            ax.grid(True, color=_GRID, alpha=0.5, axis="x")
            fig.tight_layout()
            path = os.path.join(output_dir, "reward_decomposition.png")
            fig.savefig(path, facecolor=_BG)
            plt.close(fig)
            saved.append(path)

    return saved


# ──────────────────────────────────────────────────────────────
#  Point d'entrée
# ──────────────────────────────────────────────────────────────


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Analyse les logs d'entraînement IA",
    )
    parser.add_argument(
        "--charts",
        action="store_true",
        help="Sauvegarder les graphiques dans data/analysis/",
    )
    args = parser.parse_args()

    # Importer les constantes de chemin paresseusement (évite pygame au moment de l'import)
    from tetris.settings import (
        BEHAVIOR_LOG_PATH,
        DATA_DIR,
        LOG_PATH,
        STEP_LOG_PATH,
    )

    # Charger
    print("Chargement des logs...", file=sys.stderr)
    training = load_training_log(LOG_PATH)
    steps = load_step_log(STEP_LOG_PATH)
    behavior = load_behavior_log(BEHAVIOR_LOG_PATH)

    # Analyser
    analysis: dict = {}
    if training:
        analysis["training"] = analyze_training_log(training)
        analysis["training"]["_all_episodes"] = training
    if steps:
        analysis["steps"] = analyze_step_log(steps)
    if behavior:
        analysis["behavior"] = analyze_behavior_log(behavior)

    # Rapport
    print_report(analysis)

    # Graphiques
    if args.charts:
        out = os.path.join(DATA_DIR, "analysis")
        saved = save_charts(analysis, out)
        if saved:
            print(f"\nGraphiques sauvegardés dans {out}/", file=sys.stderr)
            for p in saved:
                print(f"  {p}", file=sys.stderr)

    if not analysis:
        print("Aucun log trouvé — rien à analyser.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
