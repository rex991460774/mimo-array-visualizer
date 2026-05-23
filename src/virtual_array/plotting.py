from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from .geometry import AntennaArray


def plot_physical_array(array: AntennaArray, output_path: str | Path) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    tx_xy = array.tx_xy()
    rx_xy = array.rx_xy()

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.scatter(tx_xy[:, 0], tx_xy[:, 1], marker="d", facecolors="none", edgecolors="#b35b5b", label="Tx")
    ax.scatter(rx_xy[:, 0], rx_xy[:, 1], marker="*", color="#4056b4", label="Rx")
    _annotate(ax, tx_xy, [point.name for point in array.tx], dy=0.8)
    _annotate(ax, rx_xy, [point.name for point in array.rx], dy=-1.2)
    ax.set_title("Physical antenna layout")
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.grid(True, alpha=0.35)
    ax.axis("equal")
    ax.legend()
    fig.tight_layout()
    fig.savefig(output, dpi=180)
    plt.close(fig)
    return output


def plot_virtual_array(
    array: AntennaArray,
    output_path: str | Path,
    scale: float = 1.0,
) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    unique, counts = array.unique_virtual_xy(scale=scale)
    single_mask = counts == 1
    overlap_mask = counts > 1

    fig, ax = plt.subplots(figsize=(9, 5))
    if np.any(single_mask):
        ax.scatter(
            unique[single_mask, 0],
            unique[single_mask, 1],
            s=34,
            marker="o",
            color="#2f6fbb",
            edgecolors="#1f2933",
            linewidths=0.4,
            label="single",
        )
    if np.any(overlap_mask):
        overlap_xy = unique[overlap_mask]
        overlap_counts = counts[overlap_mask]
        scatter = ax.scatter(
            overlap_xy[:, 0],
            overlap_xy[:, 1],
            s=80 + 30 * overlap_counts,
            marker="s",
            c=overlap_counts,
            cmap="autumn_r",
            edgecolors="#111111",
            linewidths=0.8,
            label="overlap",
            zorder=3,
        )
        ax.scatter(
            overlap_xy[:, 0],
            overlap_xy[:, 1],
            s=28,
            marker="x",
            color="#111111",
            linewidths=1.2,
            zorder=4,
        )
        for (x, y), count in zip(overlap_xy, overlap_counts):
            ax.annotate(
                f"x{int(count)}",
                xy=(x, y),
                xytext=(5, 5),
                textcoords="offset points",
                fontsize=8,
                color="#8a1c1c",
                weight="bold",
            )
        colorbar = fig.colorbar(scatter, ax=ax)
        colorbar.set_label("overlap multiplicity")
    ax.set_title("Virtual array")
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.grid(True, alpha=0.35)
    ax.axis("equal")
    ax.legend()
    fig.tight_layout()
    fig.savefig(output, dpi=180)
    plt.close(fig)
    return output


def _annotate(ax: plt.Axes, xy: np.ndarray, labels: list[str], dy: float) -> None:
    for (x, y), label in zip(xy, labels):
        ax.text(x, y + dy, label, fontsize=8, ha="center", va="center")
