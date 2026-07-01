"""Packaging regression tests — verify bundled data ships in the built artifacts.

Why this file exists
--------------------
Every other test in this suite runs against an *editable* install
(``pip install -e .``), which points at the source tree, so bundled resources
under ``pvValidatorUtils/data/`` are always found on disk. That masks a real
packaging bug: a proper ``pip install`` (wheel/sdist) that ships *without* the
data directory. The tool then silently falls back to ``_builtin_defaults()``
(see rule_loader.py), losing rule references and ``--explain`` data.

These tests build the actual distribution artifacts in-process and assert the
rule YAML is inside — the check that would have caught the missing
``data/**/*`` package-data glob. They are marked ``packaging`` so they can be
deselected in environments without a working build backend.
"""

import os
import pathlib
import tarfile
import zipfile

import pytest

# The project root is the directory that contains pyproject.toml (parent of test/).
PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
RULE_YAML = "pvValidatorUtils/data/rules/ess-0000757-rev10.yaml"
STD_PROPS_YAML = "pvValidatorUtils/data/standard_properties.yaml"

# setuptools ships its own build backend; skip cleanly if it is unavailable.
build_meta = pytest.importorskip("setuptools.build_meta")


def _build(kind: str, out_dir: pathlib.Path) -> str:
    """Build an sdist or wheel into ``out_dir`` and return the artifact filename.

    The build backend reads pyproject.toml from the current working directory,
    so we temporarily chdir into the project root and always restore it.
    """
    previous_cwd = os.getcwd()
    os.chdir(PROJECT_ROOT)
    try:
        if kind == "wheel":
            return build_meta.build_wheel(str(out_dir))
        return build_meta.build_sdist(str(out_dir))
    finally:
        os.chdir(previous_cwd)


@pytest.mark.packaging
def test_rule_yaml_included_in_wheel(tmp_path):
    """The wheel (controlled by package-data) must contain the rule YAML."""
    wheel_name = _build("wheel", tmp_path)
    with zipfile.ZipFile(tmp_path / wheel_name) as zf:
        names = zf.namelist()

    assert RULE_YAML in names, (
        "Rule YAML missing from wheel — the 'data/**/*' package-data glob is "
        "broken; a real `pip install` would ship without the ruleset."
    )
    assert STD_PROPS_YAML in names, "standard_properties.yaml missing from wheel"
    # packages.find must not pull test/ into the distribution.
    assert not any(
        n.startswith("test/") or n == "test" for n in names
    ), "test/ leaked into the wheel — constrain [tool.setuptools.packages.find]"


@pytest.mark.packaging
def test_rule_yaml_included_in_sdist(tmp_path):
    """The sdist (controlled by MANIFEST.in / include-package-data) must contain the rule YAML."""
    sdist_name = _build("sdist", tmp_path)
    with tarfile.open(tmp_path / sdist_name) as tf:
        names = tf.getnames()

    assert any(n.endswith(RULE_YAML) for n in names), (
        "Rule YAML missing from sdist — check MANIFEST.in / include-package-data."
    )
