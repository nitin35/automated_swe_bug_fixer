from src.config import load_config

def test_load_config():
    config = load_config()
    assert isinstance(config, dict)
    assert "models" in config
    assert "timeouts" in config
    assert "cost_weights" in config
    assert "paths" in config
    
    # Check specific fields
    assert config["models"]["lite"] == "llama3.2:1b"
    assert config["timeouts"]["lite"] == 30
    assert config["paths"]["cache_dir"] == "cache"
