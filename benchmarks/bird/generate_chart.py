# Copyright 2026 CVS Health and/or one of its affiliates
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

"""Generate BIRD benchmark grouped bar chart and update README.md.

Reads evaluation_report.json from each benchmarks/bird/output/*/ directory,
produces a matplotlib grouped bar chart image at docs/assets/benchmark_chart.png,
and updates the README with a results table + embedded image.
"""

import re
import os
import json
import glob
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

DISPLAY_MAP = {
    "gpt-5.4": "GPT-5.4",
    "gpt-5.4-mini": "GPT-5.4 Mini",
    "gpt-5.4-nano": "GPT-5.4 Nano",
    "gemini-2.5-pro": "Gemini 2.5 Pro",
    "gemini-2.5-flash": "Gemini 2.5 Flash",
    "gemini-2.5-flash-lite": "Gemini 2.5 Flash-Lite",
}

SIMPLE_N, MODERATE_N, CHALLENGING_N = 148, 250, 102
CHART_ABS_PATH = str(PROJECT_ROOT / "docs" / "assets" / "benchmark_chart.png")
CHART_REL_PATH = "docs/assets/benchmark_chart.png"
OUTPUT_GLOB = str(PROJECT_ROOT / "benchmarks" / "bird" / "output" / "*/")
README_PATH = str(PROJECT_ROOT / "README.md")

CATEGORY_COLORS = {
    "Overall": "#2F5496",
    "Simple": "#4CAF50",
    "Moderate": "#FF9800",
    "Challenging": "#E53935",
}


def collect_results():
    model_data = []
    for d in sorted(glob.glob(OUTPUT_GLOB)):
        report_path = os.path.join(d, "evaluation_report.json")
        if not os.path.exists(report_path):
            continue
        with open(report_path) as f:
            report = json.load(f)
        name = os.path.basename(d.rstrip("/")).rsplit("_", 2)[0]
        ea = report["execution_accuracy"]
        model_data.append({
            "key": name,
            "overall": ea["overall"],
            "simple": ea["simple"],
            "moderate": ea["moderate"],
            "challenging": ea["challenging"],
            "total": report.get("total", 500),
        })
    model_data.sort(key=lambda m: m["overall"], reverse=True)
    return model_data


def generate_chart(model_data: list) -> str:
    """Create a grouped bar chart and save as PNG. Returns the image path."""
    labels = [DISPLAY_MAP.get(m["key"], m["key"]) for m in model_data]
    categories = ["Overall", "Simple", "Moderate", "Challenging"]
    cat_keys = ["overall", "simple", "moderate", "challenging"]

    data = {cat: [m[key] for m in model_data] for cat, key in zip(categories, cat_keys)}

    x = np.arange(len(labels))
    n_cats = len(categories)
    bar_width = 0.18
    offsets = np.arange(n_cats) - (n_cats - 1) / 2

    fig, ax = plt.subplots(figsize=(14, 6))

    for i, cat in enumerate(categories):
        positions = x + offsets[i] * bar_width
        bars = ax.bar(
            positions, data[cat], bar_width,
            label=cat, color=CATEGORY_COLORS[cat], edgecolor="white", linewidth=0.5,
        )
        for bar in bars:
            height = bar.get_height()
            ax.text(
                bar.get_x() + bar.get_width() / 2, height + 0.8,
                f"{height:.1f}", ha="center", va="bottom", fontsize=8, fontweight="bold",
            )

    ax.set_ylabel("Execution Accuracy (EX %)", fontsize=12, fontweight="bold")
    ax.set_title(
        "BIRD Mini-Dev Benchmark — Execution Accuracy by Difficulty",
        fontsize=14, fontweight="bold", pad=15,
    )
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=11, rotation=25, ha="right")
    ax.set_ylim(0, 95)
    ax.legend(
        title="Difficulty", loc="upper right", fontsize=10, title_fontsize=11,
        framealpha=0.9,
    )
    ax.grid(axis="y", alpha=0.3, linestyle="--")
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    os.makedirs(os.path.dirname(CHART_ABS_PATH), exist_ok=True)
    fig.tight_layout()
    fig.savefig(CHART_ABS_PATH, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)

    print(f"Chart saved to {CHART_ABS_PATH}")
    return CHART_REL_PATH


def build_readme_section(model_data: list, chart_path: str) -> str:
    total = model_data[0]["total"] if model_data else 500

    rows = []
    for m in model_data:
        dn = DISPLAY_MAP.get(m["key"], m["key"])
        rows.append(
            f'| **{dn}** | **{m["overall"]:.1f}%** '
            f'| {m["simple"]:.1f}% | {m["moderate"]:.1f}% | {m["challenging"]:.1f}% |'
        )

    table = "\n".join(rows)
    return f"""## 📊 Model Performance Comparison (BIRD Benchmark)

BIRD Mini-Dev text-to-SQL execution accuracy (EX) across {total} questions, with oracle knowledge (evidence) enabled.

| Model | Overall | Simple ({SIMPLE_N}) | Moderate ({MODERATE_N}) | Challenging ({CHALLENGING_N}) |
|:---|:---:|:---:|:---:|:---:|
{table}

![BIRD Benchmark Results]({chart_path})
"""


def update_readme(section: str):
    with open(README_PATH, "r") as f:
        content = f.read()

    pattern = re.compile(
        r"## 📊 Model Performance Comparison \(BIRD Benchmark\).*?(?=## Core Features)",
        re.DOTALL,
    )

    if pattern.search(content):
        new_content = pattern.sub(section + "\n", content)
        print("Updated existing chart in README.md")
    else:
        new_content = content.replace("## Core Features", section + "\n## Core Features")
        print("Inserted new chart into README.md")

    with open(README_PATH, "w") as f:
        f.write(new_content)


if __name__ == "__main__":
    data = collect_results()
    if not data:
        print("No benchmark results found in benchmarks/bird/output/*/")
    else:
        path = generate_chart(data)
        section = build_readme_section(data, path)
        update_readme(section)
