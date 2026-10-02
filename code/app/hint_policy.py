import json
import os
from pathlib import Path
from typing import Dict, Optional

from app.config import (
    HINT_LEVELS_PATH,
    MAX_HINT_LEVEL,
    MIN_HINT_LEVEL
)


class HintPolicyError(ValueError):
    pass


class HintPolicy:
    def __init__(
        self,
        path: Optional[Path] = None
    ) -> None:
        self.path = Path(path or HINT_LEVELS_PATH)
        self.levels = self._load()

    def _load(self) -> Dict[str, Dict]:
        if not self.path.exists():
            raise HintPolicyError(
                f"Hint-Policy nicht gefunden: {self.path}"
            )

        try:
            with self.path.open("r", encoding="utf-8") as file:
                levels = json.load(file)
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise HintPolicyError(
                f"Hint-Policy kann nicht als JSON gelesen werden: {self.path}"
            ) from exc

        if not isinstance(levels, dict):
            raise HintPolicyError(
                "Hint-Policy muss ein JSON-Objekt sein"
            )

        required = {
            "name",
            "goal",
            "max_words",
            "may_include",
            "must_not_include",
            "include_solution_steps",
            "max_solution_steps",
            "include_final_answer"
        }
        for key, config in levels.items():
            if not key.isascii() or not key.isdecimal() or str(int(key)) != key:
                raise HintPolicyError(f"Ungueltige Hilfestufe: {key}")
            if not isinstance(config, dict):
                raise HintPolicyError(f"Hilfestufe {key} muss ein JSON-Objekt sein")

        # Overrides are data, never templates; individual fields take precedence.
        raw_override = os.getenv("TUTOR_HINT_POLICY_JSON", "").strip()
        if raw_override:
            try:
                overrides = json.loads(raw_override)
            except json.JSONDecodeError as exc:
                raise HintPolicyError("TUTOR_HINT_POLICY_JSON muss gueltiges JSON sein") from exc
            if not isinstance(overrides, dict):
                raise HintPolicyError("TUTOR_HINT_POLICY_JSON muss ein JSON-Objekt sein")
            for key, override in overrides.items():
                if key not in levels:
                    raise HintPolicyError(f"TUTOR_HINT_POLICY_JSON: Hilfestufe {key} existiert nicht")
                if not isinstance(override, dict):
                    raise HintPolicyError(f"TUTOR_HINT_POLICY_JSON: Hilfestufe {key} muss ein Objekt sein")
                levels[key].update(override)

        for variable, raw in sorted(os.environ.items()):
            if not variable.startswith("TUTOR_LEVEL_"):
                continue
            key, separator, suffix = variable[len("TUTOR_LEVEL_"):].partition("_")
            field = suffix.lower()
            if not separator or key not in levels or field not in required:
                raise HintPolicyError(f"Unbekannter Hint-Policy-Override: {variable}")
            raw = raw.strip()
            if field in {"name", "goal"}:
                value = raw
            elif field in {"include_solution_steps", "include_final_answer"}:
                if raw.lower() in {"1", "true", "yes", "on"}:
                    value = True
                elif raw.lower() in {"0", "false", "no", "off"}:
                    value = False
                else:
                    raise HintPolicyError(f"{variable} muss ein boolescher Wert sein")
            elif field in {"may_include", "must_not_include"}:
                try:
                    value = json.loads(raw)
                except json.JSONDecodeError as exc:
                    if raw.startswith(("[", "{", '"')):
                        raise HintPolicyError(f"{variable} muss gueltiges JSON sein") from exc
                    value = [
                        item.strip() for item in raw.replace(";", ",").split(",") if item.strip()
                    ]
            else:
                try:
                    value = json.loads(raw)
                except json.JSONDecodeError as exc:
                    raise HintPolicyError(f"{variable} muss gueltiges JSON sein") from exc
            levels[key][field] = value

        for level in range(MIN_HINT_LEVEL, MAX_HINT_LEVEL + 1):
            if str(level) not in levels:
                raise HintPolicyError(
                    f"Hilfestufe {level} fehlt"
                )

        for key, config in levels.items():
            missing = required - set(config.keys())
            if missing:
                raise HintPolicyError(
                    f"Hilfestufe {key}: "
                    f"Felder fehlen: {sorted(missing)}"
                )
            unknown = set(config.keys()) - required
            if unknown:
                raise HintPolicyError(f"Hilfestufe {key}: unbekannte Felder: {sorted(unknown)}")
            for field in ("name", "goal"):
                if not isinstance(config[field], str) or not config[field].strip():
                    raise HintPolicyError(f"Hilfestufe {key}: {field} muss nichtleerer Text sein")
            if type(config["max_words"]) is not int or config["max_words"] <= 0:
                raise HintPolicyError(f"Hilfestufe {key}: max_words muss eine positive Ganzzahl sein")
            for field in ("may_include", "must_not_include"):
                if not isinstance(config[field], list) or any(
                    not isinstance(item, str) or not item.strip() for item in config[field]
                ):
                    raise HintPolicyError(f"Hilfestufe {key}: {field} muss eine Liste von Texten sein")
            for field in ("include_solution_steps", "include_final_answer"):
                if type(config[field]) is not bool:
                    raise HintPolicyError(f"Hilfestufe {key}: {field} muss ein boolescher Wert sein")

            limit = config["max_solution_steps"]
            if limit is not None and (type(limit) is not int or limit < 0):
                raise HintPolicyError(
                    f"Hilfestufe {key}: max_solution_steps muss "
                    "eine nichtnegative Ganzzahl oder null sein"
                )

        return {str(level): levels[str(level)] for level in range(MIN_HINT_LEVEL, MAX_HINT_LEVEL + 1)}

    def get(
        self,
        hint_level: int
    ) -> Dict:
        if type(hint_level) is not int or str(hint_level) not in self.levels:
            raise HintPolicyError(
                "Hilfestufe muss zwischen "
                f"{MIN_HINT_LEVEL} und {MAX_HINT_LEVEL} liegen"
            )

        return self.levels[str(hint_level)]
