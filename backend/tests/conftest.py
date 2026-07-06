import pytest

from celltwin.model.registry import load_all_toxins, load_cell


@pytest.fixture(scope="session")
def cell():
    return load_cell("hepatocyte")


@pytest.fixture(scope="session")
def toxins():
    return load_all_toxins()
