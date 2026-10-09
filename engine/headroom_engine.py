"""
Headroom Admission Engine — reconstruct from Headroom PPA design (64/150,688 family).
No Magpie DEN on seal. Canonical: S_H = S_solv · R_H
GRANT iff ProspectiveClaimed <= Supported AND |r_H| <= epsilon_H
TripleEcho is observer-only (Phi_H cannot buy R_H / Case D).
"""
from __future__ import annotations

import hashlib
import json
import math
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


DIMS = ("compute", "memory", "power", "thermal")
EPS_H_DEFAULT = 1e-6
PPA_REF = "Headroom PPA 64/150,688"  # design nucleus; not Magpie DEN


@dataclass
class ResourceVector:
    """Four-rail resource word: compute / memory / power / thermal."""
    compute: float = 0.0
    memory: float = 0.0
    power: float = 0.0
    thermal: float = 0.0

    def as_tuple(self) -> Tuple[float, float, float, float]:
        return (self.compute, self.memory, self.power, self.thermal)

    def __add__(self, other: "ResourceVector") -> "ResourceVector":
        return ResourceVector(*(a + b for a, b in zip(self.as_tuple(), other.as_tuple())))

    def __sub__(self, other: "ResourceVector") -> "ResourceVector":
        return ResourceVector(*(a - b for a, b in zip(self.as_tuple(), other.as_tuple())))

    def __mul__(self, scalar: float) -> "ResourceVector":
        return ResourceVector(*(a * scalar for a in self.as_tuple()))

    def componentwise_le(self, other: "ResourceVector") -> bool:
        return all(a <= b + 1e-15 for a, b in zip(self.as_tuple(), other.as_tuple()))

    def clamp_nonneg(self) -> "ResourceVector":
        return ResourceVector(*(max(0.0, a) for a in self.as_tuple()))

    def max_norm(self) -> float:
        return max(abs(a) for a in self.as_tuple())

    def to_dict(self) -> Dict[str, float]:
        return {k: float(v) for k, v in zip(DIMS, self.as_tuple())}

    @classmethod
    def from_seq(cls, seq: Sequence[float]) -> "ResourceVector":
        vals = list(seq) + [0.0] * 4
        return cls(*[float(x) for x in vals[:4]])

    @classmethod
    def ones(cls, scale: float = 1.0) -> "ResourceVector":
        return cls(scale, scale, scale, scale)


@dataclass
class HowardResidual:
    """
    Howard / residual mismatch.
    H_ij = d_ij - λ * D_K(i,j); r_H is aggregate magnitude used by the gate.
    """
    r_H: float = 0.0
    lambda_scale: float = 1.0
    pairs: List[Tuple[float, float]] = field(default_factory=list)  # (d, D_K)

    def recompute(self) -> float:
        if not self.pairs:
            self.r_H = 0.0
            return self.r_H
        num = 0.0
        den = 0.0
        for d, dk in self.pairs:
            num += d * dk
            den += dk * dk
        if den > 0:
            self.lambda_scale = max(0.0, num / (den + 1e-18))
        residuals = [d - self.lambda_scale * dk for d, dk in self.pairs]
        # RMS magnitude
        self.r_H = math.sqrt(sum(r * r for r in residuals) / len(residuals))
        return self.r_H

    def valid(self, epsilon_H: float = EPS_H_DEFAULT) -> bool:
        return abs(self.r_H) <= epsilon_H


@dataclass
class TripleEchoObserver:
    """
    Observer-only three-lane diagnostic coherence Phi_H.
    NEVER an admission authority — Case D: Phi cannot buy R_H.
    """
    lanes: Tuple[complex, complex, complex] = (0j, 0j, 0j)
    phi_H: float = 0.0

    def observe(self, z1: complex, z2: complex, z3: complex) -> float:
        self.lanes = (z1, z2, z3)
        # Coherence: mean pairwise phase agreement magnitude in [0,1]
        mags = [abs(z) for z in self.lanes]
        if min(mags) < 1e-18:
            self.phi_H = 0.0
            return self.phi_H
        u = [z / abs(z) for z in self.lanes]
        c12 = abs(u[0].conjugate() * u[1])
        c23 = abs(u[1].conjugate() * u[2])
        c31 = abs(u[2].conjugate() * u[0])
        # Also fold magnitude balance
        bal = 1.0 - (max(mags) - min(mags)) / (sum(mags) + 1e-18)
        self.phi_H = max(0.0, min(1.0, (c12 + c23 + c31) / 3.0 * bal))
        return self.phi_H

    def note(self) -> str:
        return f"Phi_H={self.phi_H:.4f} (observer-only; not admission authority)"


class HashLedger:
    """Append-only hash-chained decision ledger."""

    def __init__(self, genesis: str = "HEADROOM_SEAL_v1"):
        self.chain: List[Dict[str, Any]] = []
        self._prev = hashlib.sha256(genesis.encode()).hexdigest()

    def append(self, record: Dict[str, Any]) -> str:
        body = json.dumps(record, sort_keys=True, default=str)
        digest = hashlib.sha256((self._prev + "|" + body).encode()).hexdigest()
        entry = {
            "n": len(self.chain),
            "prev": self._prev[:16],
            "digest": digest,
            "record": record,
            "ts": time.time(),
        }
        self.chain.append(entry)
        self._prev = digest
        return digest

    def tip(self) -> str:
        return self._prev

    def ribbon(self, n: int = 12) -> List[str]:
        return [e["digest"][:12] for e in self.chain[-n:]]

    def to_list(self) -> List[Dict[str, Any]]:
        return list(self.chain)


@dataclass
class AdmissionVerdict:
    admit: bool
    S_solv: int
    R_H: int
    S_H: int
    reason: str
    r_H: float
    phi_H: float
    claimed: Dict[str, float]
    interior: Dict[str, float]
    digest: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class HeadroomAdmissionController:
    """
    Pre-dispatch admission: S_H = S_solv · R_H.
    Refusal is pure — refused work does not pollute ActiveClaimed.
    """

    def __init__(
        self,
        supported: Optional[ResourceVector] = None,
        epsilon_H: float = EPS_H_DEFAULT,
        ledger: Optional[HashLedger] = None,
    ):
        self.supported = supported or ResourceVector(100.0, 100.0, 100.0, 100.0)
        self.active = ResourceVector()
        self.epsilon_H = epsilon_H
        self.ledger = ledger or HashLedger()
        self.echo = TripleEchoObserver()
        self.howard = HowardResidual()
        self.telemetry_ticks = 0
        self.admits = 0
        self.refuses = 0
        self.ppa_ref = PPA_REF

    @property
    def interior(self) -> ResourceVector:
        return (self.supported - self.active).clamp_nonneg()

    def update_telemetry(
        self,
        supported: Optional[ResourceVector] = None,
        release: Optional[ResourceVector] = None,
        scale: Optional[float] = None,
    ) -> ResourceVector:
        """Refresh Supported / Active from telemetry. Diagnostic scaling may shrink rails."""
        self.telemetry_ticks += 1
        if supported is not None:
            self.supported = supported
        if release is not None:
            self.active = (self.active - release).clamp_nonneg()
        if scale is not None:
            # Dynamic headroom contraction (power/thermal bias)
            s = max(0.0, min(1.0, scale))
            self.supported = ResourceVector(
                self.supported.compute,
                self.supported.memory,
                self.supported.power * s,
                self.supported.thermal * s,
            )
        return self.interior

    def evaluate(
        self,
        R: ResourceVector,
        pairs: Optional[Sequence[Tuple[float, float]]] = None,
        echo: Optional[Tuple[complex, complex, complex]] = None,
        meta: Optional[Dict[str, Any]] = None,
    ) -> AdmissionVerdict:
        """
        Evaluate request R with optional Howard pairs and TripleEcho lanes.
        Phi_H logged only — never overrides residual gate.
        """
        if pairs is not None:
            self.howard.pairs = list(pairs)
            self.howard.recompute()
        phi = 0.0
        if echo is not None:
            phi = self.echo.observe(*echo)
        else:
            phi = self.echo.phi_H

        interior = self.interior
        S_solv = 1 if R.componentwise_le(interior) else 0
        R_H = 1 if self.howard.valid(self.epsilon_H) else 0
        S_H = S_solv * R_H  # product = AND; Phi cannot buy R_H

        if S_H == 1:
            # Atomic commit of whole resource-state transition
            self.active = self.active + R
            self.admits += 1
            reason = "CRYSTALLIZE"
            admit = True
        else:
            # Refusal purity: ActiveClaimed unchanged
            self.refuses += 1
            admit = False
            if S_solv == 0 and R_H == 0:
                reason = "DISSOLVE:insolvence+residual"
            elif S_solv == 0:
                reason = "DISSOLVE:insolvence"
            else:
                reason = "DISSOLVE:residual"

        verdict = AdmissionVerdict(
            admit=admit,
            S_solv=S_solv,
            R_H=R_H,
            S_H=S_H,
            reason=reason,
            r_H=self.howard.r_H,
            phi_H=phi,
            claimed=R.to_dict(),
            interior=interior.to_dict(),
        )
        digest = self.ledger.append(
            {
                "S_H": S_H,
                "S_solv": S_solv,
                "R_H": R_H,
                "r_H": self.howard.r_H,
                "phi_H": phi,
                "admit": admit,
                "reason": reason,
                "meta": meta or {},
                "ppa": self.ppa_ref,
            }
        )
        verdict.digest = digest
        return verdict
