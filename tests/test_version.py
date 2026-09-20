import pathlib
import tomllib
import unittest

from src.core.version import __version__


class TestVersionIsSingleSourced(unittest.TestCase):
    """`pyproject.toml` carries its own version literal and nothing derives it.

    Packaging metadata is read before any of this code is importable, so the duplication is
    unavoidable — see the docstring in `src/core/version.py`. What is avoidable is the two drifting
    apart, which has already happened once: `pyproject.toml` said `0.1.0` while the API reported
    `1.0.0`, so a developer reading the packaging metadata and an API consumer reading the OpenAPI
    schema saw different answers.
    """

    def test_pyproject_matches_version_module(self):
        pyproject = pathlib.Path(__file__).resolve().parent.parent / "pyproject.toml"
        packaged = tomllib.loads(pyproject.read_text())["project"]["version"]

        self.assertEqual(
            packaged,
            __version__,
            "pyproject.toml and src/core/version.py disagree — bump both when releasing",
        )


if __name__ == "__main__":
    unittest.main()
