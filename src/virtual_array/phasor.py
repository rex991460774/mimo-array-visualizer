from __future__ import annotations

import numpy as np


def unit_phasor(phase_rad: np.ndarray) -> np.ndarray:
    """Return ``exp(1j * phase)`` for a real phase array.

    Writing cos/sin into a preallocated complex array gives the same values as
    ``np.exp(1j * phase)`` but avoids NumPy's slower complex ``exp`` path, which
    dominates the 2D array-factor and 2D DBF dictionary computations.
    """
    phase = np.asarray(phase_rad, dtype=float)
    result = np.empty(phase.shape, dtype=complex)
    np.cos(phase, out=result.real)
    np.sin(phase, out=result.imag)
    return result
