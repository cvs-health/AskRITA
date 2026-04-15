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
#   squarify (MIT)

"""
Generate animated GIF chart previews for docs/charts/*.md pages.

Every data point is taken verbatim from the corresponding documentation file.
No synthetic or made-up data is used.

Usage:
    python scripts/generate_chart_assets.py

Output:
    docs/assets/charts/sample_<type>.gif   (14 files)
    docs/assets/charts/sample_<type>.png   (14 static fallbacks)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.animation as animation
import numpy as np

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "docs" / "assets" / "charts"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

TOTAL_FRAMES = 30
INTERVAL_MS = 50

BLUE = "#4285f4"
GREEN = "#34a853"
YELLOW = "#fbbc04"
RED = "#ea4335"
ORANGE = "#ff7f0e"
GREY = "#9aa0a6"


def _set_gif_loop_once(gif_path: Path):
    """Re-save a GIF with loop=1 so it plays once and stops on the last frame."""
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

    # Last frame stays visible longer
    durations[-1] = max(durations[-1], 2000)

    frames[0].save(
        str(gif_path),
        save_all=True,
        append_images=frames[1:],
        duration=durations,
        loop=1,
    )


def _save(fig, name: str, anim=None):
    """Save both a static PNG and an animated GIF (plays once)."""
    png_path = OUTPUT_DIR / f"{name}.png"
    gif_path = OUTPUT_DIR / f"{name}.gif"

    fig.savefig(str(png_path), dpi=120, bbox_inches="tight", facecolor="white")
    print(f"  saved {png_path.relative_to(OUTPUT_DIR.parent.parent.parent)}")

    if anim is not None:
        writer = animation.PillowWriter(fps=20)
        writer.args_key = "pillow_args"
        anim.save(str(gif_path), writer=writer, dpi=100,
                  savefig_kwargs={"facecolor": "white"})
        _set_gif_loop_once(gif_path)
        print(f"  saved {gif_path.relative_to(OUTPUT_DIR.parent.parent.parent)}")

    plt.close(fig)


# ---------------------------------------------------------------------------
# 1. BAR CHART  (horizontal) — bar-chart.md  lines 78-84
# ---------------------------------------------------------------------------
def gen_bar():
    categories = ["Retail Store", "Walk-in Clinic", "Wellness Center",
                   "Premium Services", "Digital Services"]
    values = [8.4, 8.7, 8.2, 7.9, 7.1]

    fig, ax = plt.subplots(figsize=(8, 4.5))
    fig.patch.set_facecolor("white")

    bars = ax.barh(categories, [0]*len(values), color=BLUE)
    ax.set_xlim(0, 10)
    ax.set_xlabel("Satisfaction Score (1-10)")
    ax.set_title("Customer Satisfaction by Service Area", fontsize=14, fontweight="bold")
    ax.invert_yaxis()

    def update(frame):
        frac = min(1.0, frame / (TOTAL_FRAMES * 0.7))
        for bar, v in zip(bars, values):
            bar.set_width(v * frac)
        return bars

    anim = animation.FuncAnimation(fig, update, frames=TOTAL_FRAMES, interval=INTERVAL_MS, blit=False)
    update(TOTAL_FRAMES)
    _save(fig, "sample_bar", anim)


# ---------------------------------------------------------------------------
# 2. COLUMN CHART  (vertical) — column-chart.md  lines 79-87
# ---------------------------------------------------------------------------
def gen_column():
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun"]
    values = [2450, 2890, 3120, 2780, 3450, 3890]

    fig, ax = plt.subplots(figsize=(8, 4.5))
    fig.patch.set_facecolor("white")

    bars = ax.bar(months, [0]*len(values), color=BLUE)
    ax.set_ylim(0, max(values) * 1.15)
    ax.set_xlabel("Month")
    ax.set_ylabel("Response Count")
    ax.set_title("Monthly Survey Response Volume", fontsize=14, fontweight="bold")

    def update(frame):
        frac = min(1.0, frame / (TOTAL_FRAMES * 0.7))
        for bar, v in zip(bars, values):
            bar.set_height(v * frac)
        return bars

    anim = animation.FuncAnimation(fig, update, frames=TOTAL_FRAMES, interval=INTERVAL_MS, blit=False)
    update(TOTAL_FRAMES)
    _save(fig, "sample_column", anim)


# ---------------------------------------------------------------------------
# 3. LINE CHART — line-chart.md  lines 85-98
# ---------------------------------------------------------------------------
def gen_line():
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    nps = [68, 71, 74, 72, 76, 78, 75, 79, 82, 80, 84, 86]

    fig, ax = plt.subplots(figsize=(8, 4.5))
    fig.patch.set_facecolor("white")
    line, = ax.plot([], [], color=BLUE, linewidth=3, marker="o", markersize=5)
    ax.set_xlim(-0.5, len(months) - 0.5)
    ax.set_ylim(60, 95)
    ax.set_xticks(range(len(months)))
    ax.set_xticklabels(months, rotation=45, ha="right")
    ax.set_xlabel("Month")
    ax.set_ylabel("NPS Score")
    ax.set_title("Customer Satisfaction Trend Over Time", fontsize=14, fontweight="bold")

    def update(frame):
        n = max(1, int(len(nps) * min(1.0, frame / (TOTAL_FRAMES * 0.7))))
        line.set_data(range(n), nps[:n])
        return [line]

    anim = animation.FuncAnimation(fig, update, frames=TOTAL_FRAMES, interval=INTERVAL_MS, blit=False)
    update(TOTAL_FRAMES)
    _save(fig, "sample_line", anim)


# ---------------------------------------------------------------------------
# 4. PIE CHART — pie-chart.md  lines 77-83
# ---------------------------------------------------------------------------
def gen_pie():
    labels = ["Very Satisfied", "Satisfied", "Neutral", "Dissatisfied", "Very Dissatisfied"]
    values = [4250, 3890, 1120, 680, 260]
    colors = ["#28a745", "#6cb33f", "#ffc107", "#fd7e14", "#dc3545"]

    fig, ax = plt.subplots(figsize=(7, 5))
    fig.patch.set_facecolor("white")

    def update(frame):
        ax.clear()
        frac = min(1.0, frame / (TOTAL_FRAMES * 0.7))
        angle = 360 * frac
        wedges, texts, autotexts = ax.pie(
            values, labels=labels, colors=colors, autopct="%1.0f%%",
            startangle=90, counterclock=False,
            pctdistance=0.75,
            textprops={"fontsize": 9},
        )
        for w in wedges:
            theta1 = w.theta1
            theta2 = w.theta2
            if theta2 - 90 > angle:
                w.set_visible(False)
            elif theta1 - 90 > angle:
                w.set_visible(False)

        ax.set_title("Customer Satisfaction Distribution", fontsize=14, fontweight="bold")

    # For the animated version, use a simpler fade-in approach
    fig2, ax2 = plt.subplots(figsize=(7, 5))
    fig2.patch.set_facecolor("white")

    frames_list = []
    for f in range(TOTAL_FRAMES):
        frac = min(1.0, f / (TOTAL_FRAMES * 0.65))
        alpha = frac
        ax2.clear()
        wedges, texts, autotexts = ax2.pie(
            values, labels=labels, colors=colors, autopct="%1.0f%%",
            startangle=90, counterclock=False,
            pctdistance=0.75,
            textprops={"fontsize": 9},
        )
        for w in wedges:
            w.set_alpha(alpha)
        for t in texts:
            t.set_alpha(alpha)
        for t in autotexts:
            t.set_alpha(alpha)
        ax2.set_title("Customer Satisfaction Distribution", fontsize=14, fontweight="bold")

    # Static version
    fig_s, ax_s = plt.subplots(figsize=(7, 5))
    fig_s.patch.set_facecolor("white")
    ax_s.pie(values, labels=labels, colors=colors, autopct="%1.0f%%",
             startangle=90, counterclock=False, pctdistance=0.75,
             textprops={"fontsize": 9})
    ax_s.set_title("Customer Satisfaction Distribution", fontsize=14, fontweight="bold")

    # Build animation with growing wedges
    fig_a, ax_a = plt.subplots(figsize=(7, 5))
    fig_a.patch.set_facecolor("white")

    def update_pie(frame):
        ax_a.clear()
        frac = min(1.0, frame / (TOTAL_FRAMES * 0.7))
        partial = [v * frac for v in values]
        if sum(partial) == 0:
            partial = [1]
            c = ["white"]
            l = [""]
        else:
            c = colors
            l = labels
        ax_a.pie(partial, labels=l, colors=c, autopct="%1.0f%%" if frac > 0.3 else "",
                 startangle=90, counterclock=False, pctdistance=0.75,
                 textprops={"fontsize": 9})
        ax_a.set_title("Customer Satisfaction Distribution", fontsize=14, fontweight="bold")

    anim = animation.FuncAnimation(fig_a, update_pie, frames=TOTAL_FRAMES, interval=INTERVAL_MS)
    update_pie(TOTAL_FRAMES)

    fig_s.savefig(str(OUTPUT_DIR / "sample_pie.png"), dpi=120, bbox_inches="tight", facecolor="white")
    print(f"  saved docs/assets/charts/sample_pie.png")
    _writer = animation.PillowWriter(fps=20)
    anim.save(str(OUTPUT_DIR / "sample_pie.gif"), writer=_writer, dpi=100,
              savefig_kwargs={"facecolor": "white"})
    _set_gif_loop_once(OUTPUT_DIR / "sample_pie.gif")
    print(f"  saved docs/assets/charts/sample_pie.gif")
    plt.close("all")


# ---------------------------------------------------------------------------
# 5. SCATTER CHART — scatter-chart.md  lines 81-97
# ---------------------------------------------------------------------------
def gen_scatter():
    x_vals = [2.3, 3.1, 1.8, 4.2, 2.9, 3.7, 1.5, 5.1,
              2.7, 3.9, 2.1, 4.8, 1.9, 3.4, 4.5]
    y_vals = [8.7, 8.2, 9.1, 7.5, 8.4, 7.8, 9.3, 6.9,
              8.6, 7.3, 8.9, 7.1, 9.0, 8.0, 7.2]

    fig, ax = plt.subplots(figsize=(8, 4.5))
    fig.patch.set_facecolor("white")
    scat = ax.scatter([], [], s=60, color=BLUE, zorder=5)
    ax.set_xlim(0, 6)
    ax.set_ylim(6, 10)
    ax.set_xlabel("Average Response Time (minutes)")
    ax.set_ylabel("Customer Satisfaction Score (1-10)")
    ax.set_title("Response Time vs Customer Satisfaction", fontsize=14, fontweight="bold")

    # Trend line
    z = np.polyfit(x_vals, y_vals, 1)
    p = np.poly1d(z)
    trend_x = np.linspace(0.5, 5.5, 100)
    trend_line, = ax.plot([], [], color=ORANGE, linewidth=2, linestyle="--", alpha=0.8)

    def update(frame):
        n = max(1, int(len(x_vals) * min(1.0, frame / (TOTAL_FRAMES * 0.6))))
        offsets = np.column_stack([x_vals[:n], y_vals[:n]])
        scat.set_offsets(offsets)
        if frame > TOTAL_FRAMES * 0.5:
            frac = min(1.0, (frame - TOTAL_FRAMES * 0.5) / (TOTAL_FRAMES * 0.3))
            cutoff = int(len(trend_x) * frac)
            trend_line.set_data(trend_x[:cutoff], p(trend_x[:cutoff]))
        return [scat, trend_line]

    anim = animation.FuncAnimation(fig, update, frames=TOTAL_FRAMES, interval=INTERVAL_MS, blit=False)
    update(TOTAL_FRAMES)
    _save(fig, "sample_scatter", anim)


# ---------------------------------------------------------------------------
# 6. HISTOGRAM — histogram-chart.md: normal distribution around 8.0, stdev 1.2
# ---------------------------------------------------------------------------
def gen_histogram():
    np.random.seed(42)
    scores = np.random.normal(8.0, 1.2, 1000)
    scores = np.clip(scores, 1, 10)

    fig, ax = plt.subplots(figsize=(8, 4.5))
    fig.patch.set_facecolor("white")
    bins = np.arange(1, 10.5, 0.5)

    ax.set_xlim(1, 10)
    ax.set_xlabel("Satisfaction Score (1-10)")
    ax.set_ylabel("Number of Responses")
    ax.set_title("Customer Satisfaction Score Distribution", fontsize=14, fontweight="bold")

    counts, _ = np.histogram(scores, bins=bins)
    max_count = counts.max()
    ax.set_ylim(0, max_count * 1.15)
    bar_edges = bins[:-1]
    bar_width = 0.5
    bar_containers = ax.bar(bar_edges, [0]*len(counts), width=bar_width, align="edge", color=BLUE)

    def update(frame):
        frac = min(1.0, frame / (TOTAL_FRAMES * 0.7))
        for bar, c in zip(bar_containers, counts):
            bar.set_height(c * frac)
        return list(bar_containers)

    anim = animation.FuncAnimation(fig, update, frames=TOTAL_FRAMES, interval=INTERVAL_MS, blit=False)
    update(TOTAL_FRAMES)
    _save(fig, "sample_histogram", anim)


# ---------------------------------------------------------------------------
# 7. COMBO CHART — combo-chart.md  lines 90-96
# ---------------------------------------------------------------------------
def gen_combo():
    segments = ["Commercial", "Medicare", "Medicaid", "Individual"]
    response_count = [15420, 8932, 5621, 2103]
    nps_score = [72, 68, 45, 38]

    fig, ax1 = plt.subplots(figsize=(8, 4.5))
    fig.patch.set_facecolor("white")

    x = np.arange(len(segments))
    bars = ax1.bar(x, [0]*len(segments), width=0.55, color="#1f77b4", label="Response Count")
    ax1.set_ylim(0, max(response_count) * 1.2)
    ax1.set_ylabel("Response Count", color="#1f77b4")
    ax1.set_xticks(x)
    ax1.set_xticklabels(segments)
    ax1.set_title("Response Volume vs NPS Score by Business Segment", fontsize=13, fontweight="bold")
    ax1.tick_params(axis="y", labelcolor="#1f77b4")

    ax2 = ax1.twinx()
    line, = ax2.plot([], [], color=ORANGE, linewidth=3, marker="o", markersize=8, label="NPS Score")
    ax2.set_ylim(0, 100)
    ax2.set_ylabel("NPS Score", color=ORANGE)
    ax2.tick_params(axis="y", labelcolor=ORANGE)

    handles = [mpatches.Patch(color="#1f77b4", label="Response Count"),
               plt.Line2D([0], [0], color=ORANGE, linewidth=3, marker="o", label="NPS Score")]
    ax1.legend(handles=handles, loc="upper right")

    def update(frame):
        frac = min(1.0, frame / (TOTAL_FRAMES * 0.7))
        for bar, v in zip(bars, response_count):
            bar.set_height(v * frac)
        n = max(1, int(len(nps_score) * frac))
        line.set_data(x[:n], [s * frac for s in nps_score[:n]])
        return list(bars) + [line]

    anim = animation.FuncAnimation(fig, update, frames=TOTAL_FRAMES, interval=INTERVAL_MS, blit=False)
    update(TOTAL_FRAMES)
    _save(fig, "sample_combo", anim)


# ---------------------------------------------------------------------------
# 8. SANKEY — sankey-chart.md  lines 80-84  (flow data)
# Matplotlib doesn't have a native sankey for Google-Charts-style diagrams,
# so we use matplotlib.sankey for a simplified version with the exact data.
# ---------------------------------------------------------------------------
def gen_sankey():
    from matplotlib.sankey import Sankey

    fig, ax = plt.subplots(figsize=(10, 5.5))
    fig.patch.set_facecolor("white")

    # Exact data from sankey-chart.md
    # Survey Invitation -> Survey Started: 1000
    # Survey Started -> Demographics: 850  |  -> Abandoned: 150
    # Demographics -> Experience Questions: 750  |  -> Abandoned: 100
    # Experience Questions -> NPS Question: 680  |  -> Abandoned: 70
    # NPS Question -> Survey Completed: 620  |  -> Abandoned: 60

    sankey = Sankey(ax=ax, unit="", format="%d", gap=0.5, scale=1.0/1000)
    sankey.add(flows=[1000, -850, -150],
               labels=["Survey\nInvitation", "Started", "Abandoned"],
               orientations=[0, 0, -1],
               facecolor="#4285f4", alpha=0.7)
    sankey.add(flows=[850, -750, -100],
               labels=[None, "Demographics", "Abandoned"],
               orientations=[0, 0, -1],
               prior=0, connect=(1, 0),
               facecolor="#34a853", alpha=0.7)
    sankey.add(flows=[750, -680, -70],
               labels=[None, "Experience\nQuestions", "Abandoned"],
               orientations=[0, 0, -1],
               prior=1, connect=(1, 0),
               facecolor="#fbbc04", alpha=0.7)
    sankey.add(flows=[680, -620, -60],
               labels=[None, "Completed", "Abandoned"],
               orientations=[0, 0, -1],
               prior=2, connect=(1, 0),
               facecolor="#ff7f0e", alpha=0.7)

    diagrams = sankey.finish()
    ax.set_title("Customer Journey Flow", fontsize=14, fontweight="bold")
    ax.axis("off")

    fig.savefig(str(OUTPUT_DIR / "sample_sankey.png"), dpi=120, bbox_inches="tight", facecolor="white")
    print(f"  saved docs/assets/charts/sample_sankey.png")

    # Fade-in animation
    fig_a, ax_a = plt.subplots(figsize=(10, 5.5))
    fig_a.patch.set_facecolor("white")

    sankey2 = Sankey(ax=ax_a, unit="", format="%d", gap=0.5, scale=1.0/1000)
    sankey2.add(flows=[1000, -850, -150], labels=["Survey\nInvitation", "Started", "Abandoned"],
                orientations=[0, 0, -1], facecolor="#4285f4", alpha=0.7)
    sankey2.add(flows=[850, -750, -100], labels=[None, "Demographics", "Abandoned"],
                orientations=[0, 0, -1], prior=0, connect=(1, 0), facecolor="#34a853", alpha=0.7)
    sankey2.add(flows=[750, -680, -70], labels=[None, "Experience\nQuestions", "Abandoned"],
                orientations=[0, 0, -1], prior=1, connect=(1, 0), facecolor="#fbbc04", alpha=0.7)
    sankey2.add(flows=[680, -620, -60], labels=[None, "Completed", "Abandoned"],
                orientations=[0, 0, -1], prior=2, connect=(1, 0), facecolor="#ff7f0e", alpha=0.7)
    diagrams2 = sankey2.finish()
    ax_a.set_title("Customer Journey Flow", fontsize=14, fontweight="bold")
    ax_a.axis("off")

    all_patches = []
    for d in diagrams2:
        all_patches.append(d.patch)
        all_patches.extend(d.texts)

    def update(frame):
        frac = min(1.0, frame / (TOTAL_FRAMES * 0.7))
        for p in all_patches:
            p.set_alpha(frac * 0.7 if hasattr(p, "get_facecolor") else frac)

    anim = animation.FuncAnimation(fig_a, update, frames=TOTAL_FRAMES, interval=INTERVAL_MS)
    _writer = animation.PillowWriter(fps=20)
    anim.save(str(OUTPUT_DIR / "sample_sankey.gif"), writer=_writer, dpi=100,
              savefig_kwargs={"facecolor": "white"})
    _set_gif_loop_once(OUTPUT_DIR / "sample_sankey.gif")
    print(f"  saved docs/assets/charts/sample_sankey.gif")
    plt.close("all")


# ---------------------------------------------------------------------------
# 9. GAUGE — gauge-chart.md: NPS Score = 72, range 0-100
#    red 0-30, yellow 30-70, green 70-100
# ---------------------------------------------------------------------------
def gen_gauge():
    value = 72
    fig, ax = plt.subplots(figsize=(5, 4), subplot_kw={"projection": "polar"})
    fig.patch.set_facecolor("white")

    theta_range = np.pi
    red_end = np.pi * (30 / 100)
    yellow_end = np.pi * (70 / 100)

    # Draw colored arcs
    n_pts = 200
    for start, end, color in [
        (0, red_end, "#dc3545"),
        (red_end, yellow_end, "#ffc107"),
        (yellow_end, np.pi, "#28a745"),
    ]:
        theta = np.linspace(np.pi - start, np.pi - end, n_pts)
        ax.fill_between(theta, 0.6, 1.0, color=color, alpha=0.6)

    ax.set_ylim(0, 1.4)
    ax.set_thetamin(0)
    ax.set_thetamax(180)
    ax.set_axis_off()

    needle_angle = np.pi * (1 - value / 100)

    # Static
    ax.annotate("", xy=(needle_angle, 0.95), xytext=(needle_angle, 0.0),
                arrowprops=dict(arrowstyle="->", color="black", lw=2.5))
    ax.text(np.pi / 2, 0.3, f"{value}", ha="center", va="center",
            fontsize=28, fontweight="bold")
    ax.text(np.pi / 2, 0.05, "NPS Score", ha="center", va="center", fontsize=12, color="gray")

    fig.savefig(str(OUTPUT_DIR / "sample_gauge.png"), dpi=120, bbox_inches="tight", facecolor="white")
    print(f"  saved docs/assets/charts/sample_gauge.png")

    # Animation: needle swings from 0 to 72
    fig_a, ax_a = plt.subplots(figsize=(5, 4), subplot_kw={"projection": "polar"})
    fig_a.patch.set_facecolor("white")

    for start, end, color in [
        (0, red_end, "#dc3545"),
        (red_end, yellow_end, "#ffc107"),
        (yellow_end, np.pi, "#28a745"),
    ]:
        theta = np.linspace(np.pi - start, np.pi - end, n_pts)
        ax_a.fill_between(theta, 0.6, 1.0, color=color, alpha=0.6)

    ax_a.set_ylim(0, 1.4)
    ax_a.set_thetamin(0)
    ax_a.set_thetamax(180)
    ax_a.set_axis_off()

    needle = ax_a.annotate("", xy=(np.pi, 0.95), xytext=(np.pi, 0.0),
                           arrowprops=dict(arrowstyle="->", color="black", lw=2.5))
    val_text = ax_a.text(np.pi / 2, 0.3, "0", ha="center", va="center",
                         fontsize=28, fontweight="bold")
    ax_a.text(np.pi / 2, 0.05, "NPS Score", ha="center", va="center", fontsize=12, color="gray")

    def update(frame):
        frac = min(1.0, frame / (TOTAL_FRAMES * 0.7))
        current = int(value * frac)
        angle = np.pi * (1 - current / 100)
        needle.xy = (angle, 0.95)
        needle.set_position((angle, 0.0))
        val_text.set_text(str(current))

    anim = animation.FuncAnimation(fig_a, update, frames=TOTAL_FRAMES, interval=INTERVAL_MS)
    _writer = animation.PillowWriter(fps=20)
    anim.save(str(OUTPUT_DIR / "sample_gauge.gif"), writer=_writer, dpi=100,
              savefig_kwargs={"facecolor": "white"})
    _set_gif_loop_once(OUTPUT_DIR / "sample_gauge.gif")
    print(f"  saved docs/assets/charts/sample_gauge.gif")
    plt.close("all")


# ---------------------------------------------------------------------------
# 10. GEO CHART — geo-chart.md  lines 75-85 (US states + NPS scores)
# Matplotlib basemap is heavy; use a simple US-shaped heatmap table instead.
# ---------------------------------------------------------------------------
def gen_geo():
    states = {
        "CA": 75, "TX": 68, "NY": 72, "FL": 65, "IL": 70,
        "PA": 69, "OH": 66, "GA": 71, "NC": 67,
    }

    fig, ax = plt.subplots(figsize=(8, 5))
    fig.patch.set_facecolor("white")

    # Simple grid representation of US states with NPS values
    sorted_states = sorted(states.items(), key=lambda x: x[1], reverse=True)
    state_names = [s[0] for s in sorted_states]
    state_vals = [s[1] for s in sorted_states]

    cmap = plt.cm.RdYlGn
    norm = plt.Normalize(60, 80)
    bar_colors = [cmap(norm(v)) for v in state_vals]

    bars = ax.barh(state_names, [0]*len(state_vals), color=bar_colors)
    ax.set_xlim(0, 85)
    ax.set_xlabel("NPS Score")
    ax.set_title("NPS Score by State", fontsize=14, fontweight="bold")
    ax.invert_yaxis()

    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    fig.colorbar(sm, ax=ax, label="NPS Score", pad=0.02)

    def update(frame):
        frac = min(1.0, frame / (TOTAL_FRAMES * 0.7))
        for bar, v in zip(bars, state_vals):
            bar.set_width(v * frac)
        return bars

    anim = animation.FuncAnimation(fig, update, frames=TOTAL_FRAMES, interval=INTERVAL_MS, blit=False)
    update(TOTAL_FRAMES)
    _save(fig, "sample_geo", anim)


# ---------------------------------------------------------------------------
# 11. CALENDAR HEATMAP — calendar-chart.md  lines 38-51
# Uses the exact formula from the docs.
# ---------------------------------------------------------------------------
def gen_calendar():
    from datetime import datetime, timedelta

    start_date = datetime(2024, 1, 1)
    dates = []
    volumes = []
    for i in range(365):
        current_date = start_date + timedelta(days=i)
        base_volume = 100
        seasonal_factor = 1 + 0.3 * (i % 30) / 30
        daily_volume = int(base_volume * seasonal_factor + (i % 7) * 10)
        dates.append(current_date)
        volumes.append(daily_volume)

    volumes = np.array(volumes)

    # Create a week x weekday matrix for the year
    # ISO: Monday=0
    first_weekday = dates[0].weekday()
    total_weeks = (365 + first_weekday) // 7 + 1
    grid = np.full((7, total_weeks), np.nan)

    for i, (d, v) in enumerate(zip(dates, volumes)):
        week = (i + first_weekday) // 7
        wd = d.weekday()
        grid[wd, week] = v

    fig, ax = plt.subplots(figsize=(12, 3))
    fig.patch.set_facecolor("white")

    cmap = plt.cm.YlGn
    im = ax.imshow(grid, aspect="auto", cmap=cmap, interpolation="nearest",
                   vmin=volumes.min(), vmax=volumes.max())
    ax.set_yticks(range(7))
    ax.set_yticklabels(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"], fontsize=8)

    month_starts = []
    for m in range(1, 13):
        d = datetime(2024, m, 1)
        idx = (d - start_date).days
        week = (idx + first_weekday) // 7
        month_starts.append((week, d.strftime("%b")))

    ax.set_xticks([w for w, _ in month_starts])
    ax.set_xticklabels([l for _, l in month_starts], fontsize=8)
    ax.set_title("Daily Survey Response Volume - 2024", fontsize=14, fontweight="bold")
    fig.colorbar(im, ax=ax, label="Response Count", pad=0.01, fraction=0.02)

    # Animation: reveal week by week
    fig_a, ax_a = plt.subplots(figsize=(12, 3))
    fig_a.patch.set_facecolor("white")

    grid_anim = np.full_like(grid, np.nan)
    im_a = ax_a.imshow(grid_anim, aspect="auto", cmap=cmap, interpolation="nearest",
                       vmin=volumes.min(), vmax=volumes.max())
    ax_a.set_yticks(range(7))
    ax_a.set_yticklabels(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"], fontsize=8)
    ax_a.set_xticks([w for w, _ in month_starts])
    ax_a.set_xticklabels([l for _, l in month_starts], fontsize=8)
    ax_a.set_title("Daily Survey Response Volume - 2024", fontsize=14, fontweight="bold")
    fig_a.colorbar(im_a, ax=ax_a, label="Response Count", pad=0.01, fraction=0.02)

    def update(frame):
        cols_to_show = max(1, int(total_weeks * min(1.0, frame / (TOTAL_FRAMES * 0.8))))
        grid_anim[:, :cols_to_show] = grid[:, :cols_to_show]
        im_a.set_data(grid_anim)
        return [im_a]

    anim = animation.FuncAnimation(fig_a, update, frames=TOTAL_FRAMES, interval=INTERVAL_MS, blit=False)

    fig.savefig(str(OUTPUT_DIR / "sample_calendar.png"), dpi=120, bbox_inches="tight", facecolor="white")
    print(f"  saved docs/assets/charts/sample_calendar.png")
    _writer = animation.PillowWriter(fps=20)
    anim.save(str(OUTPUT_DIR / "sample_calendar.gif"), writer=_writer, dpi=100,
              savefig_kwargs={"facecolor": "white"})
    _set_gif_loop_once(OUTPUT_DIR / "sample_calendar.gif")
    print(f"  saved docs/assets/charts/sample_calendar.gif")
    plt.close("all")


# ---------------------------------------------------------------------------
# 12. TIMELINE — timeline-chart.md  lines 42-60
# ---------------------------------------------------------------------------
def gen_timeline():
    from datetime import datetime, timedelta
    import matplotlib.dates as mdates

    events = [
        ("Q1 Email Campaign", datetime(2024, 1, 15), datetime(2024, 2, 15)),
        ("Q1 SMS Campaign", datetime(2024, 1, 20), datetime(2024, 2, 10)),
        ("Q2 Email Campaign", datetime(2024, 4, 1), datetime(2024, 5, 1)),
    ]

    colors_list = [BLUE, GREEN, YELLOW]

    # Convert dates to matplotlib float format for barh compatibility
    starts_num = [mdates.date2num(e[1]) for e in events]
    durations_num = [mdates.date2num(e[2]) - mdates.date2num(e[1]) for e in events]

    fig, ax = plt.subplots(figsize=(10, 3.5))
    fig.patch.set_facecolor("white")

    bars_list = []
    for i, (label, start, end) in enumerate(events):
        bar = ax.barh(i, 0, left=starts_num[i], height=0.5,
                      color=colors_list[i], alpha=0.8)
        bars_list.append((bar, durations_num[i]))

    ax.set_yticks(range(len(events)))
    ax.set_yticklabels([e[0] for e in events], fontsize=10)
    ax.set_xlabel("Date")
    ax.set_title("Survey Campaign Timeline", fontsize=14, fontweight="bold")
    ax.invert_yaxis()
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    ax.xaxis.set_major_locator(mdates.MonthLocator())

    all_dates = [mdates.date2num(e[1]) for e in events] + [mdates.date2num(e[2]) for e in events]
    ax.set_xlim(min(all_dates) - 5, max(all_dates) + 5)

    def update(frame):
        frac = min(1.0, frame / (TOTAL_FRAMES * 0.7))
        for bar_container, dur in bars_list:
            for b in bar_container:
                b.set_width(dur * frac)
        return []

    anim = animation.FuncAnimation(fig, update, frames=TOTAL_FRAMES, interval=INTERVAL_MS, blit=False)
    update(TOTAL_FRAMES)
    _save(fig, "sample_timeline", anim)


# ---------------------------------------------------------------------------
# 13. TREEMAP — treemap-chart.md  lines 77-85  (exact data)
# Using squarify for treemap layout.
# ---------------------------------------------------------------------------
def gen_treemap():
    try:
        import squarify
    except ImportError:
        print("  [SKIP] treemap: pip install squarify first")
        # Generate a static placeholder
        _gen_treemap_fallback()
        return

    # Leaf-level data from treemap-chart.md
    labels = ["Retail Store", "Walk-in Clinic", "Wellness Center",
              "Medicare", "Medicaid", "Commercial",
              "Mobile App", "Website"]
    values = [2500, 1500, 1000, 1800, 700, 500, 1200, 800]
    parents = ["Healthcare", "Healthcare", "Healthcare",
               "Insurance", "Insurance", "Insurance",
               "Digital", "Digital"]

    parent_colors = {
        "Healthcare": "#4285f4",
        "Insurance": "#34a853",
        "Digital": "#fbbc04",
    }
    colors = [parent_colors[p] for p in parents]

    fig, ax = plt.subplots(figsize=(9, 5.5))
    fig.patch.set_facecolor("white")
    ax.set_title("Survey Response Distribution", fontsize=14, fontweight="bold")

    normed = squarify.normalize_sizes(values, 100, 60)
    rects = squarify.squarify(normed, 0, 0, 100, 60)

    patches = []
    texts = []
    for r, lbl, val, clr in zip(rects, labels, values, colors):
        rect = plt.Rectangle((r["x"], r["y"]), r["dx"], r["dy"],
                              facecolor=clr, edgecolor="white", linewidth=2, alpha=0.85)
        ax.add_patch(rect)
        patches.append(rect)
        cx = r["x"] + r["dx"] / 2
        cy = r["y"] + r["dy"] / 2
        t = ax.text(cx, cy, f"{lbl}\n{val:,}", ha="center", va="center",
                    fontsize=9, fontweight="bold", color="white")
        texts.append(t)

    ax.set_xlim(0, 100)
    ax.set_ylim(0, 60)
    ax.set_axis_off()

    # Legend
    for parent, color in parent_colors.items():
        ax.plot([], [], "s", color=color, markersize=10, label=parent)
    ax.legend(loc="upper right", framealpha=0.9)

    fig.savefig(str(OUTPUT_DIR / "sample_treemap.png"), dpi=120, bbox_inches="tight", facecolor="white")
    print(f"  saved docs/assets/charts/sample_treemap.png")

    # Animation: rects grow
    fig_a, ax_a = plt.subplots(figsize=(9, 5.5))
    fig_a.patch.set_facecolor("white")
    ax_a.set_title("Survey Response Distribution", fontsize=14, fontweight="bold")
    ax_a.set_xlim(0, 100)
    ax_a.set_ylim(0, 60)
    ax_a.set_axis_off()

    a_patches = []
    a_texts = []
    for r, lbl, val, clr in zip(rects, labels, values, colors):
        rect = plt.Rectangle((r["x"] + r["dx"]/2, r["y"] + r["dy"]/2), 0, 0,
                              facecolor=clr, edgecolor="white", linewidth=2, alpha=0.85)
        ax_a.add_patch(rect)
        a_patches.append((rect, r))
        cx = r["x"] + r["dx"] / 2
        cy = r["y"] + r["dy"] / 2
        t = ax_a.text(cx, cy, "", ha="center", va="center",
                      fontsize=9, fontweight="bold", color="white")
        a_texts.append((t, f"{lbl}\n{val:,}"))

    for parent, color in parent_colors.items():
        ax_a.plot([], [], "s", color=color, markersize=10, label=parent)
    ax_a.legend(loc="upper right", framealpha=0.9)

    def update(frame):
        frac = min(1.0, frame / (TOTAL_FRAMES * 0.7))
        for rect, r in a_patches:
            w = r["dx"] * frac
            h = r["dy"] * frac
            rect.set_xy((r["x"] + (r["dx"] - w)/2, r["y"] + (r["dy"] - h)/2))
            rect.set_width(w)
            rect.set_height(h)
        for t, full_text in a_texts:
            t.set_text(full_text if frac > 0.4 else "")

    anim = animation.FuncAnimation(fig_a, update, frames=TOTAL_FRAMES, interval=INTERVAL_MS)
    _writer = animation.PillowWriter(fps=20)
    anim.save(str(OUTPUT_DIR / "sample_treemap.gif"), writer=_writer, dpi=100,
              savefig_kwargs={"facecolor": "white"})
    _set_gif_loop_once(OUTPUT_DIR / "sample_treemap.gif")
    print(f"  saved docs/assets/charts/sample_treemap.gif")
    plt.close("all")


def _gen_treemap_fallback():
    """Simple bar-based fallback if squarify is not installed."""
    labels = ["Retail Store", "Walk-in Clinic", "Wellness Center",
              "Medicare", "Medicaid", "Commercial", "Mobile App", "Website"]
    values = [2500, 1500, 1000, 1800, 700, 500, 1200, 800]
    colors = [BLUE]*3 + [GREEN]*3 + [YELLOW]*2

    fig, ax = plt.subplots(figsize=(9, 5))
    fig.patch.set_facecolor("white")
    ax.barh(labels, values, color=colors)
    ax.set_xlabel("Response Count")
    ax.set_title("Survey Response Distribution", fontsize=14, fontweight="bold")
    ax.invert_yaxis()
    _save(fig, "sample_treemap")


# ---------------------------------------------------------------------------
# 14. TABLE (sparklines) — table-chart.md  lines 41-61
# Render as a styled matplotlib table with mini trend lines.
# ---------------------------------------------------------------------------
def gen_table():
    stores = [
        {"id": "Store #1234", "loc": "Boston, MA", "nps": 78,
         "trend": [65, 68, 71, 74, 76, 78], "resp": 1250, "sat": 8.4},
        {"id": "Store #5678", "loc": "Austin, TX", "nps": 82,
         "trend": [70, 73, 76, 78, 80, 82], "resp": 1450, "sat": 8.7},
    ]

    fig, axes = plt.subplots(2, 1, figsize=(10, 4),
                              gridspec_kw={"height_ratios": [1, 1]})
    fig.patch.set_facecolor("white")
    fig.suptitle("Store Performance Dashboard", fontsize=14, fontweight="bold", y=1.02)

    for ax, store in zip(axes, stores):
        ax.plot(store["trend"], color=BLUE, linewidth=2, marker="o", markersize=4)
        ax.set_ylim(min(store["trend"]) - 5, max(store["trend"]) + 5)
        ax.set_xticks([])
        ax.set_ylabel("NPS")
        info = f"{store['id']} — {store['loc']}   |   NPS: {store['nps']}   Responses: {store['resp']:,}   CSAT: {store['sat']}"
        ax.set_title(info, fontsize=10, loc="left")

    fig.tight_layout()

    fig.savefig(str(OUTPUT_DIR / "sample_table.png"), dpi=120, bbox_inches="tight", facecolor="white")
    print(f"  saved docs/assets/charts/sample_table.png")

    # Animation: trend lines draw in
    fig_a, axes_a = plt.subplots(2, 1, figsize=(10, 4),
                                  gridspec_kw={"height_ratios": [1, 1]})
    fig_a.patch.set_facecolor("white")
    fig_a.suptitle("Store Performance Dashboard", fontsize=14, fontweight="bold", y=1.02)

    lines = []
    for ax, store in zip(axes_a, stores):
        line, = ax.plot([], [], color=BLUE, linewidth=2, marker="o", markersize=4)
        ax.set_ylim(min(store["trend"]) - 5, max(store["trend"]) + 5)
        ax.set_xlim(-0.2, len(store["trend"]) - 0.8)
        ax.set_xticks([])
        ax.set_ylabel("NPS")
        info = f"{store['id']} — {store['loc']}   |   NPS: {store['nps']}   Responses: {store['resp']:,}   CSAT: {store['sat']}"
        ax.set_title(info, fontsize=10, loc="left")
        lines.append((line, store["trend"]))

    fig_a.tight_layout()

    def update(frame):
        frac = min(1.0, frame / (TOTAL_FRAMES * 0.7))
        for line, trend in lines:
            n = max(1, int(len(trend) * frac))
            line.set_data(range(n), trend[:n])
        return [l for l, _ in lines]

    anim = animation.FuncAnimation(fig_a, update, frames=TOTAL_FRAMES, interval=INTERVAL_MS, blit=False)
    _writer = animation.PillowWriter(fps=20)
    anim.save(str(OUTPUT_DIR / "sample_table.gif"), writer=_writer, dpi=100,
              savefig_kwargs={"facecolor": "white"})
    _set_gif_loop_once(OUTPUT_DIR / "sample_table.gif")
    print(f"  saved docs/assets/charts/sample_table.gif")
    plt.close("all")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    generators = [
        ("bar", gen_bar),
        ("column", gen_column),
        ("line", gen_line),
        ("pie", gen_pie),
        ("scatter", gen_scatter),
        ("histogram", gen_histogram),
        ("combo", gen_combo),
        ("sankey", gen_sankey),
        ("gauge", gen_gauge),
        ("geo", gen_geo),
        ("calendar", gen_calendar),
        ("timeline", gen_timeline),
        ("treemap", gen_treemap),
        ("table", gen_table),
    ]

    print(f"Generating chart assets in {OUTPUT_DIR}\n")
    for name, gen_fn in generators:
        print(f"[{name}]")
        try:
            gen_fn()
        except Exception as e:
            print(f"  ERROR: {e}")
            import traceback
            traceback.print_exc()
        print()

    print("Done.")


if __name__ == "__main__":
    main()
