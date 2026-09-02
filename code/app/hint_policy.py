import json
from pathlib import Path
from typing import Dict, Optional

from app.config import (
    HINT_LEVELS_PATH,
    MAX_HINT_LEVEL
)


class HintPolicyError(ValueError):
    pass


class HintPolicy:
    def __init__(
        self,
        path: Optional[Path] = None
    ) -> None:
        self.path = path or HINT_LEVELS_PATH
        self.levels = self._load()

    def _load(self) -> Dict[str, Dict]:
        if not self.path.exists():
            raise HintPolicyError(
                f"Hint-Policy nicht gefunden: {self.path}"
            )

        with self.path.open(
            "r",
            encoding="utf-8"
        ) as file:
            levels = json.load(file)

        if not isinstance(levels, dict):
            raise HintPolicyError(
                "Hint-Policy muss ein JSON-Objekt sein"
            )

        for level in range(
            1,
            MAX_HINT_LEVEL + 1
        ):
            key = str(level)

            if key not in levels:
                raise HintPolicyError(
                    f"Hilfestufe {level} fehlt"
                )

            config = levels[key]

            required = {
                "name",
                "goal",
                "max_words",
                "may_include",
                "must_not_include",
                "include_solution_steps",
                "include_final_answer"
            }

            missing = required - set(config.keys())

            if missing:
                raise HintPolicyError(
                    f"Hilfestufe {level}: "
                    f"Felder fehlen: {sorted(missing)}"
                )

        return levels

    def get(
        self,
        hint_level: int
    ) -> Dict:
        if not 1 <= hint_level <= MAX_HINT_LEVEL:
            raise HintPolicyError(
                "Hilfestufe muss zwischen "
                f"1 und {MAX_HINT_LEVEL} liegen"
            )

        return self.levels[str(hint_level)]