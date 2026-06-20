import yaml
from pathlib import Path

CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"

def load_config(path=CONFIG_PATH) -> dict:
    """Load configuration from config.yaml."""
    with open(path, "r") as f:
        return yaml.safe_load(f)
