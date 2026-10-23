import ast
from pathlib import Path

from pulselens.analysis import reason_text

ANALYSIS = Path(reason_text.__file__).parent


def _emitted_codes() -> set[str]:
    """Every string literal in the analysis package that looks like one of our reason codes."""
    codes = set()
    for path in ANALYSIS.rglob("*.py"):
        if path.name == "reason_text.py":
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                v = node.value
                if v.startswith(reason_text.PREFIXES) and " " not in v and v.count(".") == 1 and v.islower():
                    codes.add(v)
    return codes


def test_every_emitted_code_has_text() -> None:
    missing = _emitted_codes() - set(reason_text.REASON_TEXT) - {spec for spec in _check_ids()}
    assert not missing, f"add to analysis/reason_text.py: {sorted(missing)}"


def _check_ids() -> set[str]:
    from pulselens.analysis import specs

    return {s.check_id for s in specs.ALL}


def test_every_code_uses_an_analysis_prefix_and_has_a_sentence() -> None:
    for code, sentence in reason_text.REASON_TEXT.items():
        assert code.startswith(reason_text.PREFIXES), code
        assert sentence.endswith(".") and len(sentence) > 10, code
