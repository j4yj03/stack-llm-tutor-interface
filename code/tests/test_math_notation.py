"""Whitelist-Konvertierung von STACK-/Maxima-Eingabesyntax nach LaTeX.

Die Konvertierung ist rein anzeigeseitig: kein eval, keine mathematische
Auswertung, keine neuen Abhaengigkeiten. Nicht erkannte Eingaben liefern
None, damit die HTML-Anzeige rohen Text faellt.
"""

from app.math_notation import cas_to_latex


def test_common_stack_expressions_convert_to_latex():
    conversions = {
        "6*x^5": "6 \\cdot x^{5}",
        "-5*exp(x^2-2*exp(x))": "-5 \\cdot e^{x^{2} - 2 \\cdot e^{x}}",
        "2*%e^(x^6-6*%e^x)": "2 \\cdot e^{x^{6} - 6 \\cdot e^{x}}",
        "x^2*sin(x)": "x^{2} \\cdot \\sin\\left(x\\right)",
        "7*%e^(x^3-3*%e^x)+1": "7 \\cdot e^{x^{3} - 3 \\cdot e^{x}} + 1",
        "1/2": "\\frac{1}{2}",
        "x^(y+1)": "x^{y + 1}",
        "(a+b)*c": "\\left(a + b\\right) \\cdot c",
        "a-(b+c)": "a - \\left(b + c\\right)",
        "x^-1": "x^{-1}",
        "sqrt(x^2+1)": "\\sqrt{x^{2} + 1}",
        "abs(-x)": "\\left|-x\\right|",
        "-6*%e^x": "-6 \\cdot e^{x}",
        "log(x)": "\\ln\\left(x\\right)",
        "2*%i*%pi": "2 \\cdot \\mathrm{i} \\cdot \\pi",
        "%alpha^2": "\\alpha^{2}",
        "3*exp(2*x+1)": "3 \\cdot e^{2 \\cdot x + 1}",
    }
    for source, expected in conversions.items():
        assert cas_to_latex(source) == expected, source


def test_equations_keep_their_left_side():
    assert cas_to_latex("f(x)=2*%e^(x^6-6*%e^x)") == (
        "f(x) = 2 \\cdot e^{x^{6} - 6 \\cdot e^{x}}"
    )
    assert cas_to_latex("y=6*x^5") == "y = 6 \\cdot x^{5}"


def test_factorial_postfix_is_supported_for_numbers_and_single_letters():
    assert cas_to_latex("3!") == "\\left(3\\right)!"
    assert cas_to_latex("n!") == "\\left(n\\right)!"
    assert cas_to_latex("(n+1)!") == "\\left(n + 1\\right)!"
    assert cas_to_latex("(x!+1)!") == "\\left(\\left(x\\right)! + 1\\right)!"


def test_prose_and_unsupported_syntax_fall_back_to_none():
    unsupported = [
        None,
        "",
        "   ",
        "Das ist Prosa?",
        "Warum brauche ich die innere Ableitung?",
        "Danke!",
        "2x",
        "x%2",
        "%unbekannt",
        "x!!",
        "__import__('os')",
        "sin(x,y)",
        "x[1]",
        "a==b",
        "f(x)",
        "x +\n 1",
        "(x+1",
        "x^2; import os",
        "lambda x: x",
        "π^2",
        "9" * 40,
    ]
    for source in unsupported:
        assert cas_to_latex(source) is None, source


def test_conversion_is_deterministic_and_never_evaluates():
    assert cas_to_latex("6*x^5") == cas_to_latex(" 6*x^5 ")
    assert cas_to_latex("9**9**9") == "9^{9^{9}}"
    assert cas_to_latex("factorial(9)") == "\\left(9\\right)!"
