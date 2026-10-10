"""Draw results/churches_by_bank.png from results/church_banks.csv (run church_banks.py annotate first)."""
import csv
from collections import Counter
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

RESULTS = Path(__file__).parent / "results"
TOP = 12

SURFACE, INK, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#898781", "#e8e7e3"
# ordinal blue ramp (validated: steps 250/400/550/700), darker = higher ethical rating
RATING_COLOUR = {"1": "#86b6ef", "3": "#3987e5", "4": "#1c5cab", "5": "#0d366b"}
UNRATED = "#d6d5d0"


def main():
    with open(RESULTS / "church_banks.csv", encoding="utf-8", newline="") as f:
        rows = [r for r in csv.DictReader(f) if ";" not in r["match"]]  # one sort code per church

    counts, rating_of = Counter(), {}
    for r in rows:
        if r["match"] == "ambiguous":
            label = "Lloyds or TSB (unresolved)" if r["candidates"] == "Lloyds/TSB" else "Ambiguous"
        elif r["match"] == "unknown":
            label = "Unknown"
        else:
            label = r["bank"]
            rating_of[label] = r["rating"]
        counts[label] += 1

    top = counts.most_common(TOP)
    other = sum(counts.values()) - sum(n for _, n in top)
    bars = top + ([("All other banks", other)] if other else [])
    bars.reverse()  # largest at the top

    fig, ax = plt.subplots(figsize=(8, 6), dpi=150)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)
    colours = [RATING_COLOUR.get(rating_of.get(name, ""), UNRATED) for name, _ in bars]
    hatches = ["" if c != UNRATED else "////" for c in colours]
    ax.barh([n for n, _ in bars], [v for _, v in bars], color=colours, hatch=hatches,
            edgecolor=SURFACE, linewidth=2, height=0.72)
    for i, (_, v) in enumerate(bars):
        ax.text(v + 6, i, f"{v:,}", va="center", fontsize=9, color=MUTED)

    ax.set_title(f"Churches by bank, from the sort code on their giving page (n = {len(rows):,})",
                 loc="left", fontsize=11, color=INK, pad=12)
    ax.set_xlabel("Churches", color=MUTED, fontsize=9)
    ax.tick_params(colors=MUTED, labelsize=9, length=0)
    ax.tick_params(axis="y", colors=INK)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)

    present = sorted({rating_of.get(n, "") for n, _ in bars} - {""})
    handles = [Patch(facecolor=RATING_COLOUR[r], label=f"Rating {r}") for r in present]
    handles.append(Patch(facecolor=UNRATED, hatch="////", edgecolor=SURFACE, label="Unrated or unresolved"))
    ax.legend(handles=handles, loc="lower right", frameon=False, fontsize=9, labelcolor=INK,
              title="Ethical rating (1 low, 5 high)", title_fontsize=9)
    fig.text(0.01, 0.01, "Churches whose website shows one sort code; not weighted by money. "
             "Ratings from bank-ratings.md (source unconfirmed).", fontsize=7.5, color=MUTED)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    out = RESULTS / "churches_by_bank.png"
    fig.savefig(out, facecolor=SURFACE)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
