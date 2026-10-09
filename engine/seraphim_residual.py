"""
Project Seraphim §2.4 — residual contraction witness.

  e_{k+1} = (I − T_s K_r) e_k + η
  V = ‖e‖²

Lyapunov-style contraction on observer residual e. Witness only —
does not override Headroom S_H admission.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional, Sequence


@dataclass
class SeraphimResidual:
    dim: int = 4
    T_s: float = 0.05          # sample / step gain
    K_r: float = 8.0           # residual feedback gain (scalar form of K_r)
    eta_scale: float = 1e-4    # process disturbance scale
    e: List[float] = field(default_factory=list)
    V_history: List[float] = field(default_factory=list)

    def __post_init__(self):
        if not self.e:
            self.e = [0.0] * self.dim

    @property
    def V(self) -> float:
        return sum(x * x for x in self.e)

    def contraction_factor(self) -> float:
        # spectral radius proxy for scalar (I - T_s K_r)
        return abs(1.0 - self.T_s * self.K_r)

    def step(
        self,
        eta: Optional[Sequence[float]] = None,
        innovate: Optional[Sequence[float]] = None,
    ) -> float:
        """
        One Seraphim contraction step.
        Optional innovate injects measurement/mismatch into e before contraction.
        """
        if innovate is not None:
            for i, v in enumerate(innovate):
                if i < len(self.e):
                    self.e[i] += float(v)
        a = 1.0 - self.T_s * self.K_r
        new_e = []
        for i, ei in enumerate(self.e):
            noise = 0.0
            if eta is not None and i < len(eta):
                noise = float(eta[i])
            else:
                # deterministic tiny drift from index (reproducible witness)
                noise = self.eta_scale * math.sin(0.17 * (len(self.V_history) + i + 1))
            new_e.append(a * ei + noise)
        self.e = new_e
        V = self.V
        self.V_history.append(V)
        return V

    def contracting(self) -> bool:
        return self.contraction_factor() < 1.0

    def snapshot(self) -> dict:
        return {
            "e": list(self.e),
            "V": self.V,
            "a": self.contraction_factor(),
            "T_s": self.T_s,
            "K_r": self.K_r,
            "steps": len(self.V_history),
            "contracting": self.contracting(),
        }
