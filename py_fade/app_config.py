"""
Wrapper around dynaconf for user configuration management.
"""
import os, pathlib, sys, logging, yaml
from dynaconf import Dynaconf
from typing import Optional

class AppConfig:
    """
    Application configuration management.
    """
    theme: str = "light_blue.xml"    
    default_model_id: str = "gemma3:1b-it-q4_K_M"
    default_temperature: float = 0.0
    default_top_k: int = 1
    default_context_length: int = 1024
    default_max_tokens: int = 128
    recent_datasets: list[str] = []  # List of recent dataset paths
    ollama_models_dir: str|None = None  # Path to Ollama models directory, if used
    models: list[dict] = []  # Models configurations
    hip_visible_devices: str|None = None  # Comma-separated list of HIP_VISIBLE_DEVICES for AMD GPUs
    dataset_preferences: dict[str, dict[str, int|str|None]] = {}  # Per-dataset persisted UI selections
    def __init__(self, appname: str = "pyFade", debug: bool = False, config_path: Optional[str|pathlib.Path] = None):
        # Compile list of attributes of the class, excluding methods and private attributes
        self._attributes = [key for key in self.__class__.__annotations__.keys() if not key.startswith("_")]    
        self.log = logging.getLogger("AppConfig")
        self.appname = appname
        self.debug = debug
        if self.debug:
            self.app_dir = f"{appname}_debug"
            self.log.warning("Debug mode is enabled. Configuration will be saved in a separate directory.")
        else:
            self.app_dir = appname
        self.base_dir = pathlib.Path.home() / self.app_dir

        if isinstance(config_path, str):
            config_path = pathlib.Path(config_path)
        if config_path:
            if config_path.is_absolute():
                self.config_file = config_path
            else:
                self.config_file = self.base_dir / config_path
        else:
            self.config_file = self.base_dir / "config.yaml"
        self.log.info(f"Using config file: {self.config_file}")
        self.load()

    def update_recent_datasets(self, path: pathlib.Path | str):
        """
        Update recent datasets list with the given path.
        """
        path = str(pathlib.Path(path).resolve())
        if path in self.recent_datasets:
            self.recent_datasets.remove(path)
        self.recent_datasets.insert(0, path)
        # Limit to 10 entries
        self.recent_datasets = self.recent_datasets[:10]

    def load(self):
        """
        Load configuration from file.
        """
        if not self.config_file.exists():
            self.log.warning(f"Config file does not exist at {self.config_file}. Using defaults.")
            return
        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            if not isinstance(data, dict):
                self.log.error(f"Config file {self.config_file} is not a valid YAML dictionary. Using defaults.")
                return
            for key in self._attributes:
                if key in data:
                    setattr(self, key, data[key])
            self.log.info(f"Configuration loaded from {self.config_file}")
        except Exception as e:
            self.log.error(f"Failed to load config file {self.config_file}: {e}. Using defaults.")
        if not isinstance(self.dataset_preferences, dict):
            self.dataset_preferences = {}
        if self.hip_visible_devices:
            os.environ['HIP_VISIBLE_DEVICES'] = self.hip_visible_devices
            self.log.info(f"Set HIP_VISIBLE_DEVICES to {self.hip_visible_devices}")

    def save(self):
        """
        Save current configuration to file.
        """
        if not self.base_dir.exists():
            os.makedirs(self.base_dir, exist_ok=True)

        data = {}
        for key in self._attributes:
            data[key] = getattr(self, key)

        with open(self.config_file, "w", encoding="utf-8") as f:
            yaml.dump(data, f)
        self.log.info(f"Configuration saved to {self.config_file}")