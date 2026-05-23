GRID_STEP = 1.0


def snap_to_grid(value: float, step: float = GRID_STEP) -> float:
    return round(value / step) * step
