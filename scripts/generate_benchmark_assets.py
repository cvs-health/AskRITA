# © 2026 CVS Health and/or one of its affiliates. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# This file uses the following unmodified third-party packages,
# each retaining its original copyright and license:
#   matplotlib (PSF/BSD-style)
#   numpy (BSD-3-Clause)
#   Pillow (PIL-License)

"""
Generate animated GIF benchmark chart previews for docs/benchmarks/*.md.

Every data point is taken verbatim from the benchmark results documentation.

Usage:
    python scripts/generate_benchmark_assets.py

Output:
    docs/assets/benchmark_chart.{png,gif}
    docs/assets/benchmark_soft_f1.{png,gif}
    docs/assets/benchmark_latency.{png,gif}
    docs/assets/benchmark_errors.{png,gif}
    docs/assets/benchmark_<model>.{png,gif}   (6 per-model files)
"""

from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import matplotlib.animation as animation
import numpy as np

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "docs" / "assets"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

TOTAL_FRAMES = 30
INTERVAL_MS = 50

CAT_COLORS = {
    "Overall": "#2F5496",
    "Simple": "#4CAF50",
    "Moderate": "#FF9800",
    "Challenging": "#E53935",
}

# All data verbatim from docs/benchmarks/results.md tables
MODELS = [
    {"name": "Gemini 2.5 Pro",       "key": "gemini_25_pro",
     "ex": {"overall": 64.4, "simple": 77.0, "moderate": 61.2, "challenging": 53.9},
     "f1": {"overall": 64.0, "simple": 75.4, "moderate": 61.7, "challenging": 53.0},
     "latency": 20.1, "errors": 18, "total": 500},
    {"name": "Gemini 2.5 Flash",     "key": "gemini_25_flash",
     "ex": {"overall": 60.6, "simple": 76.4, "moderate": 53.6, "challenging": 54.9},
     "f1": {"overall": 62.1, "simple": 75.1, "moderate": 56.8, "challenging": 55.9},
     "latency": 6.7, "errors": 12, "total": 500},
    {"name": "GPT-5.4",              "key": "gpt_54",
     "ex": {"overall": 54.8, "simple": 68.9, "moderate": 50.8, "challenging": 44.1},
     "f1": {"overall": 60.6, "simple": 71.5, "moderate": 58.7, "challenging": 49.4},
     "latency": 7.0, "errors": 3, "total": 500},
    {"name": "GPT-5.4 Mini",         "key": "gpt_54_mini",
     "ex": {"overall": 53.2, "simple": 70.3, "moderate": 49.6, "challenging": 37.3},
     "f1": {"overall": 57.2, "simple": 72.0, "moderate": 55.0, "challenging": 41.4},
     "latency": 3.6, "errors": 11, "total": 500},
    {"name": "GPT-5.4 Nano",         "key": "gpt_54_nano",
     "ex": {"overall": 40.0, "simple": 53.4, "moderate": 36.0, "challenging": 30.4},
     "f1": {"overall": 43.2, "simple": 56.3, "moderate": 40.0, "challenging": 31.9},
     "latency": 4.1, "errors": 34, "total": 500},
    {"name": "Gemini 2.5 Flash-Lite", "key": "gemini_25_flash_lite",
     "ex": {"overall": 39.4, "simple": 56.1, "moderate": 33.2, "challenging": 30.4},
     "f1": {"overall": 39.0, "simple": 55.8, "moderate": 33.4, "challenging": 28.6},
     "latency": 7.2, "errors": 209, "total": 500},
]


def _set_gif_loop_once(gif_path: Path):
    from PIL import Image
    img = Image.open(str(gif_path))
    frames = []
    durations = []
    try:
        while True:
            frames.append(img.copy())
            durations.append(img.info.get("duration", 50))
            img.seek(img.tell() + 1)
    except EOFError:
        pass
    if not frames:
        return
    durations[-1] = max(durations[-1], 2000)
    frames[0].save(str(gif_path), save_all=True, append_images=frames[1:],
                   duration=durations, loop=1)


def _save(fig, name: str, anim=None):
    png_path = OUTPUT_DIR / f"{name}.png"
    gif_path = OUTPUT_DIR / f"{name}.gif"

    fig.savefig(str(png_path), dpi=150, bbox_inches="tight", facecolor="white")
    print(f"  saved {png_path.relative_to(OUTPUT_DIR.parent.parent)}")

    if anim is not None:
        writer = animation.PillowWriter(fps=20)
        anim.save(str(gif_path), writer=writer, dpi=100,
                  savefig_kwargs={"facecolor": "white"})
        _set_gif_loop_once(gif_path)
        print(f"  saved {gif_path.relative_to(OUTPUT_DIR.parent.parent)}")

    plt.close(fig)


# ---------------------------------------------------------------------------
# 1. benchmark_chart — Grouped bar: EX accuracy by difficulty
# ---------------------------------------------------------------------------
def gen_ex_chart():
    labels = [m["name"] for m in MODELS]
    categories = ["Overall", "Simple", "Moderate", "Challenging"]
    cat_keys = ["overall", "simple", "moderate", "challenging"]

    data = {cat: [m["ex"][key] for m in MODELS] for cat, key in zip(categories, cat_keys)}

    x = np.arange(len(labels))
    n_cats = len(categories)
    bar_width = 0.18
    offsets = np.arange(n_cats) - (n_cats - 1) / 2

    fig, ax = plt.subplots(figsize=(14, 6))
    fig.patch.set_facecolor("white")

    all_bars = []
    bar_targets = []
    for i, cat in enumerate(categories):
        positions = x + offsets[i] * bar_width
        bars = ax.bar(positions, [0]*len(labels), bar_width,
                      label=cat, color=CAT_COLORS[cat], edgecolor="white", linewidth=0.5)
        all_bars.append(bars)
        bar_targets.append(data[cat])

    texts = []
    for i, cat in enumerate(categories):
        for j, val in enumerate(data[cat]):
            pos_x = x[j] + offsets[i] * bar_width
            t = ax.text(pos_x, 0, "", ha="center", va="bottom", fontsize=7, fontweight="bold")
            texts.append((t, val))

    ax.set_ylabel("Execution Accuracy (EX %)", fontsize=12, fontweight="bold")
    ax.set_title("BIRD Mini-Dev Benchmark — Execution Accuracy by Difficulty",
                 fontsize=14, fontweight="bold", pad=15)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=10, rotation=25, ha="right")
    ax.set_ylim(0, 95)
    ax.legend(title="Difficulty", loc="upper right", fontsize=10, title_fontsize=11, framealpha=0.9)
    ax.grid(axis="y", alpha=0.3, linestyle="--")
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    def update(frame):
        frac = min(1.0, frame / (TOTAL_FRAMES * 0.7))
        for bars, targets in zip(all_bars, bar_targets):
            for bar, target in zip(bars, targets):
                bar.set_height(target * frac)
        for t, val in texts:
            h = val * frac
            t.set_position((t.get_position()[0], h + 0.8))
            t.set_text(f"{h:.1f}" if frac > 0.8 else "")

    anim = animation.FuncAnimation(fig, update, frames=TOTAL_FRAMES, interval=INTERVAL_MS, blit=False)
    update(TOTAL_FRAMES)
    _save(fig, "benchmark_chart", anim)


# ---------------------------------------------------------------------------
# 2. benchmark_soft_f1 — Grouped bar: Soft F1 by difficulty
# ---------------------------------------------------------------------------
def gen_f1_chart():
    labels = [m["name"] for m in MODELS]
    categories = ["Overall", "Simple", "Moderate", "Challenging"]
    cat_keys = ["overall", "simple", "moderate", "challenging"]

    data = {cat: [m["f1"][key] for m in MODELS] for cat, key in zip(categories, cat_keys)}

    x = np.arange(len(labels))
    n_cats = len(categories)
    bar_width = 0.18
    offsets = np.arange(n_cats) - (n_cats - 1) / 2

    fig, ax = plt.subplots(figsize=(14, 6))
    fig.patch.set_facecolor("white")

    all_bars = []
    bar_targets = []
    for i, cat in enumerate(categories):
        positions = x + offsets[i] * bar_width
        bars = ax.bar(positions, [0]*len(labels), bar_width,
                      label=cat, color=CAT_COLORS[cat], edgecolor="white", linewidth=0.5)
        all_bars.append(bars)
        bar_targets.append(data[cat])

    texts = []
    for i, cat in enumerate(categories):
        for j, val in enumerate(data[cat]):
            pos_x = x[j] + offsets[i] * bar_width
            t = ax.text(pos_x, 0, "", ha="center", va="bottom", fontsize=7, fontweight="bold")
            texts.append((t, val))

    ax.set_ylabel("Soft F1 Score (%)", fontsize=12, fontweight="bold")
    ax.set_title("BIRD Mini-Dev Benchmark — Soft F1 Score by Difficulty",
                 fontsize=14, fontweight="bold", pad=15)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=10, rotation=25, ha="right")
    ax.set_ylim(0, 95)
    ax.legend(title="Difficulty", loc="upper right", fontsize=10, title_fontsize=11, framealpha=0.9)
    ax.grid(axis="y", alpha=0.3, linestyle="--")
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    def update(frame):
        frac = min(1.0, frame / (TOTAL_FRAMES * 0.7))
        for bars, targets in zip(all_bars, bar_targets):
            for bar, target in zip(bars, targets):
                bar.set_height(target * frac)
        for t, val in texts:
            h = val * frac
            t.set_position((t.get_position()[0], h + 0.8))
            t.set_text(f"{h:.1f}" if frac > 0.8 else "")

    anim = animation.FuncAnimation(fig, update, frames=TOTAL_FRAMES, interval=INTERVAL_MS, blit=False)
    update(TOTAL_FRAMES)
    _save(fig, "benchmark_soft_f1", anim)


# ---------------------------------------------------------------------------
# 3. benchmark_latency — Horizontal bar: avg latency per model
# ---------------------------------------------------------------------------
def gen_latency_chart():
    sorted_models = sorted(MODELS, key=lambda m: m["latency"])
    names = [m["name"] for m in sorted_models]
    latencies = [m["latency"] for m in sorted_models]

    colors = ["#4285f4" if lat < 10 else "#ff9800" if lat < 15 else "#E53935"
              for lat in latencies]

    fig, ax = plt.subplots(figsize=(10, 4.5))
    fig.patch.set_facecolor("white")

    bars = ax.barh(names, [0]*len(names), color=colors, edgecolor="white", linewidth=0.5)
    ax.set_xlim(0, max(latencies) * 1.2)
    ax.set_xlabel("Average Latency (seconds)", fontsize=12, fontweight="bold")
    ax.set_title("BIRD Mini-Dev Benchmark — Avg Latency per Question",
                 fontsize=14, fontweight="bold", pad=15)
    ax.invert_yaxis()
    ax.grid(axis="x", alpha=0.3, linestyle="--")
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    val_texts = []
    for bar, lat in zip(bars, latencies):
        t = ax.text(0, bar.get_y() + bar.get_height()/2, "",
                    ha="left", va="center", fontsize=10, fontweight="bold")
        val_texts.append((t, lat))

    def update(frame):
        frac = min(1.0, frame / (TOTAL_FRAMES * 0.7))
        for bar, lat in zip(bars, latencies):
            bar.set_width(lat * frac)
        for t, lat in val_texts:
            w = lat * frac
            t.set_position((w + 0.3, t.get_position()[1]))
            t.set_text(f"{w:.1f}s" if frac > 0.5 else "")

    anim = animation.FuncAnimation(fig, update, frames=TOTAL_FRAMES, interval=INTERVAL_MS, blit=False)
    update(TOTAL_FRAMES)
    _save(fig, "benchmark_latency", anim)


# ---------------------------------------------------------------------------
# 4. benchmark_errors — Horizontal bar: error count per model
# ---------------------------------------------------------------------------
def gen_errors_chart():
    sorted_models = sorted(MODELS, key=lambda m: m["errors"], reverse=True)
    names = [m["name"] for m in sorted_models]
    errors = [m["errors"] for m in sorted_models]
    error_pcts = [m["errors"] / m["total"] * 100 for m in sorted_models]

    colors = ["#E53935" if e > 50 else "#ff9800" if e > 15 else "#4CAF50"
              for e in errors]

    fig, ax = plt.subplots(figsize=(10, 4.5))
    fig.patch.set_facecolor("white")

    bars = ax.barh(names, [0]*len(names), color=colors, edgecolor="white", linewidth=0.5)
    ax.set_xlim(0, max(errors) * 1.2)
    ax.set_xlabel("Number of Errors (out of 500)", fontsize=12, fontweight="bold")
    ax.set_title("BIRD Mini-Dev Benchmark — Error Rate by Model",
                 fontsize=14, fontweight="bold", pad=15)
    ax.invert_yaxis()
    ax.grid(axis="x", alpha=0.3, linestyle="--")
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    val_texts = []
    for bar, err, pct in zip(bars, errors, error_pcts):
        t = ax.text(0, bar.get_y() + bar.get_height()/2, "",
                    ha="left", va="center", fontsize=10, fontweight="bold")
        val_texts.append((t, err, pct))

    def update(frame):
        frac = min(1.0, frame / (TOTAL_FRAMES * 0.7))
        for bar, err in zip(bars, errors):
            bar.set_width(err * frac)
        for t, err, pct in val_texts:
            w = err * frac
            t.set_position((w + 2, t.get_position()[1]))
            t.set_text(f"{int(round(w))} ({pct:.1f}%)" if frac > 0.5 else "")

    anim = animation.FuncAnimation(fig, update, frames=TOTAL_FRAMES, interval=INTERVAL_MS, blit=False)
    update(TOTAL_FRAMES)
    _save(fig, "benchmark_errors", anim)


# ---------------------------------------------------------------------------
# 5-10. Per-model: EX vs Soft F1 grouped bar
# ---------------------------------------------------------------------------
def gen_model_chart(model: dict):
    difficulties = ["Overall", "Simple", "Moderate", "Challenging"]
    diff_keys = ["overall", "simple", "moderate", "challenging"]

    ex_vals = [model["ex"][k] for k in diff_keys]
    f1_vals = [model["f1"][k] for k in diff_keys]

    x = np.arange(len(difficulties))
    bar_width = 0.32

    fig, ax = plt.subplots(figsize=(9, 5))
    fig.patch.set_facecolor("white")

    ex_bars = ax.bar(x - bar_width/2, [0]*len(difficulties), bar_width,
                     label="Execution Accuracy (EX)", color="#2F5496", edgecolor="white")
    f1_bars = ax.bar(x + bar_width/2, [0]*len(difficulties), bar_width,
                     label="Soft F1", color="#4CAF50", edgecolor="white")

    ax.set_ylabel("Score (%)", fontsize=12, fontweight="bold")
    ax.set_title(f"{model['name']} — EX vs Soft F1 Breakdown",
                 fontsize=14, fontweight="bold", pad=15)
    ax.set_xticks(x)
    ax.set_xticklabels(difficulties, fontsize=11)
    ax.set_ylim(0, 95)
    ax.legend(loc="upper right", fontsize=10, framealpha=0.9)
    ax.grid(axis="y", alpha=0.3, linestyle="--")
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    ex_texts = []
    f1_texts = []
    for i in range(len(difficulties)):
        t1 = ax.text(x[i] - bar_width/2, 0, "", ha="center", va="bottom",
                     fontsize=9, fontweight="bold", color="#2F5496")
        t2 = ax.text(x[i] + bar_width/2, 0, "", ha="center", va="bottom",
                     fontsize=9, fontweight="bold", color="#4CAF50")
        ex_texts.append((t1, ex_vals[i]))
        f1_texts.append((t2, f1_vals[i]))

    def update(frame):
        frac = min(1.0, frame / (TOTAL_FRAMES * 0.7))
        for bar, val in zip(ex_bars, ex_vals):
            bar.set_height(val * frac)
        for bar, val in zip(f1_bars, f1_vals):
            bar.set_height(val * frac)
        for t, val in ex_texts:
            h = val * frac
            t.set_position((t.get_position()[0], h + 0.8))
            t.set_text(f"{val:.1f}%" if frac > 0.8 else "")
        for t, val in f1_texts:
            h = val * frac
            t.set_position((t.get_position()[0], h + 0.8))
            t.set_text(f"{val:.1f}%" if frac > 0.8 else "")

    anim = animation.FuncAnimation(fig, update, frames=TOTAL_FRAMES, interval=INTERVAL_MS, blit=False)
    update(TOTAL_FRAMES)
    _save(fig, f"benchmark_{model['key']}", anim)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print(f"Generating benchmark assets in {OUTPUT_DIR}\n")

    generators = [
        ("EX accuracy chart", gen_ex_chart),
        ("Soft F1 chart", gen_f1_chart),
        ("Latency chart", gen_latency_chart),
        ("Error rate chart", gen_errors_chart),
    ]

    for desc, fn in generators:
        print(f"[{desc}]")
        try:
            fn()
        except Exception as e:
            print(f"  ERROR: {e}")
            import traceback
            traceback.print_exc()
        print()

    for model in MODELS:
        desc = f"{model['name']} — EX vs Soft F1"
        print(f"[{desc}]")
        try:
            gen_model_chart(model)
        except Exception as e:
            print(f"  ERROR: {e}")
            import traceback
            traceback.print_exc()
        print()

    print("Done.")


if __name__ == "__main__":
    main()
