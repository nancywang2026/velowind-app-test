import pytest
from pathlib import Path
from velowind_api.config import load_config

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def config():
    data = load_config(Path(__file__).parent / "fixtures/scenario.json", Path(__file__).parent / "fixtures/environment.json", environ={})
    data["execution"]["request_interval_seconds"] = 0
    return data
