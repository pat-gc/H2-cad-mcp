"""Fail before collection when pytest would exercise another H2 checkout."""

from pathlib import Path

import pytest


def pytest_sessionstart(session: pytest.Session) -> None:
    expected = Path(__file__).resolve().parents[1] / "src" / "h2cad" / "__init__.py"
    try:
        import h2cad
    except ModuleNotFoundError as exc:
        if exc.name != "h2cad":
            raise
        raise pytest.UsageError(
            f"H2 CAD is not installed from this checkout. Expected {expected.resolve()}; "
            "install this checkout editably before running tests."
        ) from exc
    actual = Path(h2cad.__file__).resolve()
    if actual != expected.resolve():
        raise pytest.UsageError(
            f"Tests would import another H2 CAD checkout. Expected {expected.resolve()}; "
            f"actual {actual}. Install this checkout editably before running tests."
        )
