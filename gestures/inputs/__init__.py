"""One file per input. Each module describes a single gesture.

Pick which ones are active with a preset or an explicit list; the model is
trained on exactly those, so adding or removing a gesture never requires
touching code — only these files.
"""

from __future__ import annotations

import importlib
import pkgutil
from dataclasses import dataclass


@dataclass(frozen=True)
class InputSpec:
    name: str
    recording: str
    group: str
    side: str
    flight: str
    uses_eyes: bool
    refractory_s: float
    doc: str


def load(name: str) -> InputSpec:
    module = importlib.import_module(f"inputs.{name}")
    return InputSpec(
        name=module.NAME,
        recording=module.RECORDING,
        group=module.GROUP,
        side=module.SIDE,
        flight=module.FLIGHT,
        uses_eyes=module.USES_EYES,
        refractory_s=module.REFRACTORY_S,
        doc=(module.__doc__ or "").strip(),
    )


def available() -> list[str]:
    return sorted(m.name for m in pkgutil.iter_modules(__path__))


#: Combinations validated together. Any other mix works too; train.py reports
#: how well the chosen inputs separate and warns about colliding pairs.
PRESETS = {
    "brazos": ["puno_izq", "puno_der", "brazo_izq", "brazo_der"],
    "cabeza": ["cuello_izq", "cuello_der", "blink", "happy"],
    "mente": ["giro_imag_izq", "giro_imag_der", "cerrar_ojos", "enojado"],
}
