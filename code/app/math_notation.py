"""Anzeige-Konvertierung von STACK-/Maxima-Eingabesyntax nach LaTeX.

Die Konvertierung dient ausschliesslich der HTML-Anzeige. Gespeicherte
Kontexte und Prompts bleiben unveraendert. Geparst wird nur eine
Whitelist von Ausdrucksformen ueber den stdlib-AST; jede Abweichung
liefert None, damit die Seite rohen Text zeigt. Kein eval, keine
mathematische Auswertung, keine neuen Abhaengigkeiten.
"""

import ast
import math
import re
from typing import Dict, Optional, Tuple

_MAX_TEXT_LENGTH = 5000
_MAX_CONSTANT_DIGITS = 30

_PLACEHOLDER = "__stack_notation_"
_EULER = _PLACEHOLDER + "euler"
_IMAGINARY = _PLACEHOLDER + "imag"

_GREEK_NAMES = (
    "alpha", "beta", "gamma", "delta", "epsilon", "zeta", "eta", "theta",
    "iota", "kappa", "lambda", "mu", "nu", "xi", "rho", "sigma", "tau",
    "phi", "chi", "psi", "omega",
)

_SINGLE_ARG_FUNCTIONS: Dict[str, str] = {
    "exp": "e^{%s}",
    "sqrt": "\\sqrt{%s}",
    "abs": "\\left|%s\\right|",
    "ln": "\\ln\\left(%s\\right)",
    "log": "\\ln\\left(%s\\right)",
    "sin": "\\sin\\left(%s\\right)",
    "cos": "\\cos\\left(%s\\right)",
    "tan": "\\tan\\left(%s\\right)",
    "sec": "\\sec\\left(%s\\right)",
    "csc": "\\csc\\left(%s\\right)",
    "cot": "\\cot\\left(%s\\right)",
    "asin": "\\arcsin\\left(%s\\right)",
    "acos": "\\arccos\\left(%s\\right)",
    "atan": "\\arctan\\left(%s\\right)",
    "sinh": "\\sinh\\left(%s\\right)",
    "cosh": "\\cosh\\left(%s\\right)",
    "tanh": "\\tanh\\left(%s\\right)",
    "factorial": "\\left(%s\\right)!",
}

_EQUATION_LEFT_PATTERN = re.compile(
    r"[A-Za-z][A-Za-z0-9_]*(\([A-Za-z0-9_,\s]*\))?"
)

_FACTORIAL_ATOM_PATTERN = re.compile(r"([0-9]+(?:\.[0-9]+)?|[A-Za-z])!")
_FACTORIAL_GROUP_PATTERN = re.compile(r"\(((?:[^()]|\([^()]*\))*)\)!")

_REPLACEMENTS: Dict[str, str] = {
    "%e": _EULER,
    "%i": _IMAGINARY,
    "%pi": _PLACEHOLDER + "pi",
}
for _greek in _GREEK_NAMES:
    _REPLACEMENTS["%" + _greek] = _PLACEHOLDER + _greek

_ADD_PRECEDENCE = 1
_UNARY_PRECEDENCE = 1.5
_MUL_PRECEDENCE = 2
_POW_PRECEDENCE = 3
_ATOM_PRECEDENCE = 4


def cas_to_latex(text: Optional[str]) -> Optional[str]:
    """Konvertiert einen reinen STACK-/Maxima-Ausdruck nach LaTeX.

    Gibt None zurueck, wenn der Text nicht als sicherer whitelisteter
    Ausdruck geparst werden kann; der Aufrufer zeigt dann rohen Text.
    Eine einzelne Gleichung der Form f(x)=Ausdruck wird mit uebersetzt.
    """
    if not isinstance(text, str):
        return None
    if not text.strip() or len(text) > _MAX_TEXT_LENGTH:
        return None

    if "=" in text:
        left, _, right = text.partition("=")
        if "=" in right or not _EQUATION_LEFT_PATTERN.fullmatch(left.strip()):
            return None
        right_latex = _expression_to_latex(right)
        if right_latex is None:
            return None
        return left.strip() + " = " + right_latex

    return _expression_to_latex(text)


def _expression_to_latex(text: str) -> Optional[str]:
    normalized = _normalize(text)
    if normalized is None:
        return None
    try:
        tree = ast.parse(normalized, mode="eval")
        if not _is_supported(tree.body):
            return None
        latex, _precedence = _emit(tree.body)
    except (SyntaxError, ValueError, TypeError, AttributeError,
            RecursionError, MemoryError):
        return None
    return latex


def _normalize(text: str) -> Optional[str]:
    cleaned = text.strip()
    if not cleaned:
        return None
    for token in sorted(_REPLACEMENTS, key=len, reverse=True):
        cleaned = cleaned.replace(token, _REPLACEMENTS[token])
    if "%" in cleaned:
        # Unbekannte %-Konstante oder Modulo: nicht unterstuetzt.
        return None
    if "!" in cleaned:
        if "!!" in cleaned:
            return None
        cleaned = _expand_factorials(cleaned)
        if cleaned is None:
            return None
    return cleaned.replace("^", "**")


def _expand_factorials(cleaned: str) -> Optional[str]:
    for _iteration in range(_MAX_TEXT_LENGTH):
        expanded = _FACTORIAL_ATOM_PATTERN.sub(
            r"factorial(\1)", cleaned
        )
        expanded = _FACTORIAL_GROUP_PATTERN.sub(
            r"factorial(\1)", expanded
        )
        if expanded == cleaned:
            return None if "!" in cleaned else cleaned
        cleaned = expanded
    return None


def _is_supported(node: ast.expr) -> bool:
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            return False
        if isinstance(node.value, int):
            try:
                digits = len(str(abs(node.value)))
            except ValueError:
                return False
            return digits <= _MAX_CONSTANT_DIGITS
        return math.isfinite(node.value)
    if isinstance(node, ast.Name):
        return node.id.isascii() and node.id.isidentifier()
    if isinstance(node, ast.UnaryOp):
        return (
            isinstance(node.op, (ast.USub, ast.UAdd))
            and _is_supported(node.operand)
        )
    if isinstance(node, ast.BinOp):
        return (
            isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow))
            and _is_supported(node.left)
            and _is_supported(node.right)
        )
    if isinstance(node, ast.Call):
        return (
            isinstance(node.func, ast.Name)
            and node.func.id in _SINGLE_ARG_FUNCTIONS
            and not node.keywords
            and len(node.args) == 1
            and _is_supported(node.args[0])
        )
    return False


def _emit(node: ast.expr) -> Tuple[str, int]:
    if isinstance(node, ast.Constant):
        return _format_number(node.value), _ATOM_PRECEDENCE
    if isinstance(node, ast.Name):
        return _format_name(node.id), _ATOM_PRECEDENCE
    if isinstance(node, ast.Call):
        inner, _ = _emit(node.args[0])
        if node.func.id == "factorial":
            return "\\left(" + inner + "\\right)!", _ATOM_PRECEDENCE
        return _SINGLE_ARG_FUNCTIONS[node.func.id] % inner, _ATOM_PRECEDENCE
    if isinstance(node, ast.UnaryOp):
        if isinstance(node.operand, ast.Constant) and isinstance(
            node.operand.value, (int, float)
        ):
            value = node.operand.value
            if isinstance(node.op, ast.USub):
                value = -value
            return _format_number(value), _ATOM_PRECEDENCE
        operand, precedence = _emit(node.operand)
        if isinstance(node.op, ast.UAdd):
            return operand, precedence
        if precedence <= _ADD_PRECEDENCE or isinstance(node.operand, ast.UnaryOp):
            operand = "\\left(" + operand + "\\right)"
        return "-" + operand, _UNARY_PRECEDENCE
    if isinstance(node, ast.BinOp):
        left, left_precedence = _emit(node.left)
        right, right_precedence = _emit(node.right)
        if isinstance(node.op, (ast.Add, ast.Sub)):
            sign = " + " if isinstance(node.op, ast.Add) else " - "
            return left + _signed_tail(
                node.op, node.right, right, right_precedence, sign
            ), _ADD_PRECEDENCE
        if isinstance(node.op, ast.Mult):
            if left_precedence < _MUL_PRECEDENCE:
                left = "\\left(" + left + "\\right)"
            if right_precedence < _MUL_PRECEDENCE:
                right = "\\left(" + right + "\\right)"
            return left + " \\cdot " + right, _MUL_PRECEDENCE
        if isinstance(node.op, ast.Div):
            return "\\frac{" + left + "}{" + right + "}", _MUL_PRECEDENCE
        if not _is_pow_atom_base(node.left):
            left = "\\left(" + left + "\\right)"
        return left + "^{" + right + "}", _POW_PRECEDENCE
    raise ValueError("Nicht unterstuetzter Ausdrucksknoten")


def _signed_tail(
    operator: ast.operator,
    right_node: ast.expr,
    right: str,
    right_precedence: int,
    sign: str,
) -> str:
    if isinstance(right_node, ast.UnaryOp) and isinstance(
        right_node.op, (ast.USub, ast.UAdd)
    ):
        inner, inner_precedence = _emit(right_node.operand)
        if inner_precedence <= _ADD_PRECEDENCE or isinstance(
            right_node.operand, ast.UnaryOp
        ):
            inner = "\\left(" + inner + "\\right)"
        flip = isinstance(right_node.op, ast.USub)
        subtract = isinstance(operator, ast.Sub)
        return (" - " if flip != subtract else " + ") + inner
    if right_precedence <= _ADD_PRECEDENCE:
        return sign + "\\left(" + right + "\\right)"
    return sign + right


def _is_pow_atom_base(node: ast.expr) -> bool:
    if isinstance(node, ast.Name):
        return True
    if isinstance(node, ast.Constant):
        return (
            not isinstance(node.value, bool)
            and isinstance(node.value, (int, float))
            and node.value >= 0
        )
    if isinstance(node, ast.Call):
        return node.func.id != "exp"
    return False


def _format_number(value) -> str:
    if isinstance(value, int):
        return str(value)
    if abs(value) < 1e16 and value == int(value):
        return str(int(value))
    rendered = format(value, ".12g")
    if "e" in rendered:
        mantissa, _, exponent = rendered.partition("e")
        return mantissa + " \\cdot 10^{" + str(int(exponent)) + "}"
    return rendered


def _format_name(name: str) -> str:
    if name == _EULER:
        return "e"
    if name == _IMAGINARY:
        return "\\mathrm{i}"
    if name.startswith(_PLACEHOLDER):
        return "\\" + name[len(_PLACEHOLDER):]
    if len(name) > 1:
        return "\\mathit{" + name + "}"
    return name
