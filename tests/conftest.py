from pathlib import Path

import pytest

from wowhelper.texts import load_texts

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def texts():
    return load_texts(ROOT)
