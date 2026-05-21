"""Smoke tests — verify the package imports and exposes __version__."""

import pytest

import data_type_primitives


@pytest.mark.unit
def test_package_importable() -> None:
    """Package can be imported without error."""
    assert data_type_primitives is not None


@pytest.mark.unit
def test_version_exposed() -> None:
    """__version__ is a non-empty string."""
    version = data_type_primitives.__version__
    assert isinstance(version, str)
    assert version != ""
