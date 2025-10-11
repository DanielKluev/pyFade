"""
Tests for AppConfig class.

Tests cover:
- Default configuration values
- Configuration loading from YAML
- Configuration saving to YAML
- Recent datasets list management
- Debug mode handling
- Config file path resolution (absolute vs relative)
- Error handling for invalid YAML
- HIP_VISIBLE_DEVICES environment variable setting
- Dataset preferences management
"""
import logging
import os
import pathlib

import pytest
import yaml

from py_fade.app_config import AppConfig


class TestAppConfigDefaults:
    """Test default configuration values."""

    def test_default_values(self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """
        Test that AppConfig initializes with correct default values.
        
        Tests default values for theme, model settings, and other configuration parameters.
        """
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        monkeypatch.setattr(pathlib.Path, "home", lambda: fake_home)

        config = AppConfig(appname="test_app")

        assert config.theme == "light_blue.xml"
        assert config.default_model_id == "gemma3:1b-it-q4_K_M"
        assert config.default_temperature == 0.0
        assert config.default_top_k == 1
        assert config.default_context_length == 1024
        assert config.default_max_tokens == 128
        assert len(config.recent_datasets) == 0
        assert config.ollama_models_dir is None
        assert len(config.models) == 0
        assert config.hip_visible_devices is None
        assert len(config.dataset_preferences) == 0

    def test_appname_sets_directory(self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """
        Test that appname parameter correctly sets the configuration directory.
        
        Tests directory naming for both normal and debug modes.
        """
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        monkeypatch.setattr(pathlib.Path, "home", lambda: fake_home)

        config = AppConfig(appname="custom_app")
        assert config.app_dir == "custom_app"
        assert config.base_dir == fake_home / "custom_app"


class TestAppConfigDebugMode:
    """Test debug mode configuration."""

    def test_debug_mode_changes_directory(self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch,
                                          caplog: pytest.LogCaptureFixture) -> None:
        """
        Test that debug mode appends '_debug' to configuration directory.
        
        Tests directory naming and warning log message in debug mode.
        """
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        monkeypatch.setattr(pathlib.Path, "home", lambda: fake_home)

        with caplog.at_level(logging.WARNING):
            config = AppConfig(appname="test_app", debug=True)

        assert config.debug is True
        assert config.app_dir == "test_app_debug"
        assert config.base_dir == fake_home / "test_app_debug"
        assert "Debug mode is enabled" in caplog.text


class TestAppConfigPathHandling:
    """Test configuration file path resolution."""

    def test_default_config_path(self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """
        Test default config file path when no config_path is provided.
        
        Tests that config file defaults to 'config.yaml' in base_dir.
        """
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        monkeypatch.setattr(pathlib.Path, "home", lambda: fake_home)

        config = AppConfig(appname="test_app")
        expected_path = fake_home / "test_app" / "config.yaml"
        assert config.config_file == expected_path

    def test_absolute_config_path(self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """
        Test that absolute config_path is used directly.
        
        Tests both string and pathlib.Path absolute paths.
        """
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        monkeypatch.setattr(pathlib.Path, "home", lambda: fake_home)

        absolute_path = tmp_path / "custom_config.yaml"
        config = AppConfig(appname="test_app", config_path=absolute_path)
        assert config.config_file == absolute_path

        # Test with string path
        config_string_path = AppConfig(appname="test_app", config_path=str(absolute_path))
        assert config_string_path.config_file == absolute_path

    def test_relative_config_path(self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """
        Test that relative config_path is resolved relative to base_dir.
        
        Tests relative path resolution for both string and pathlib.Path.
        """
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        monkeypatch.setattr(pathlib.Path, "home", lambda: fake_home)

        config = AppConfig(appname="test_app", config_path="subdir/config.yaml")
        expected_path = fake_home / "test_app" / "subdir" / "config.yaml"
        assert config.config_file == expected_path


class TestAppConfigLoadSave:
    """Test configuration loading and saving."""

    def test_save_creates_directory(self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """
        Test that save() creates the base_dir if it doesn't exist.
        
        Tests directory creation and file writing when directory is missing.
        """
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        monkeypatch.setattr(pathlib.Path, "home", lambda: fake_home)

        config = AppConfig(appname="test_app")
        assert not config.base_dir.exists()

        config.save()
        assert config.base_dir.exists()
        assert config.config_file.exists()

    def test_save_writes_all_attributes(self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """
        Test that save() writes all configuration attributes to YAML.
        
        Tests complete serialization of all config attributes to YAML format.
        """
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        monkeypatch.setattr(pathlib.Path, "home", lambda: fake_home)

        config = AppConfig(appname="test_app")
        config.theme = "dark_theme.xml"
        config.default_temperature = 0.8
        config.recent_datasets = ["/path/to/dataset1"]
        config.save()

        with open(config.config_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        assert data['theme'] == "dark_theme.xml"
        assert data['default_temperature'] == 0.8
        assert data['recent_datasets'] == ["/path/to/dataset1"]

    def test_load_nonexistent_file_uses_defaults(self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch,
                                                 caplog: pytest.LogCaptureFixture) -> None:
        """
        Test that load() handles non-existent config file gracefully.
        
        Tests warning log and default values when config file doesn't exist.
        """
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        monkeypatch.setattr(pathlib.Path, "home", lambda: fake_home)

        with caplog.at_level(logging.WARNING):
            config = AppConfig(appname="test_app")

        assert "Config file does not exist" in caplog.text
        assert config.theme == "light_blue.xml"  # Default value

    def test_load_existing_file(self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """
        Test that load() reads configuration from existing YAML file.
        
        Tests full load cycle: save config, create new instance, verify loaded values.
        """
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        monkeypatch.setattr(pathlib.Path, "home", lambda: fake_home)

        # Create and save config
        config1 = AppConfig(appname="test_app")
        config1.theme = "custom_theme.xml"
        config1.default_temperature = 0.9
        config1.recent_datasets = ["/dataset1", "/dataset2"]
        config1.save()

        # Load in new instance
        config2 = AppConfig(appname="test_app")
        assert config2.theme == "custom_theme.xml"
        assert config2.default_temperature == 0.9
        assert config2.recent_datasets == ["/dataset1", "/dataset2"]

    def test_load_invalid_yaml_uses_defaults(self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch,
                                             caplog: pytest.LogCaptureFixture) -> None:
        """
        Test that load() handles invalid YAML gracefully.
        
        Tests error handling and default values when YAML file is malformed.
        """
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        monkeypatch.setattr(pathlib.Path, "home", lambda: fake_home)

        # Create invalid YAML
        config_dir = fake_home / "test_app"
        config_dir.mkdir()
        config_file = config_dir / "config.yaml"
        with open(config_file, 'w', encoding='utf-8') as f:
            f.write("invalid: yaml: content: [")

        with caplog.at_level(logging.ERROR):
            config = AppConfig(appname="test_app")

        assert "Failed to load config file" in caplog.text
        assert config.theme == "light_blue.xml"  # Default value

    def test_load_non_dict_yaml_uses_defaults(self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch,
                                              caplog: pytest.LogCaptureFixture) -> None:
        """
        Test that load() handles non-dictionary YAML content.
        
        Tests error handling when YAML contains a list or string instead of a dictionary.
        """
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        monkeypatch.setattr(pathlib.Path, "home", lambda: fake_home)

        # Create YAML with non-dict content
        config_dir = fake_home / "test_app"
        config_dir.mkdir()
        config_file = config_dir / "config.yaml"
        with open(config_file, 'w', encoding='utf-8') as f:
            yaml.dump(["list", "not", "dict"], f)

        with caplog.at_level(logging.ERROR):
            config = AppConfig(appname="test_app")

        assert "not a valid YAML dictionary" in caplog.text
        assert config.theme == "light_blue.xml"  # Default value


class TestRecentDatasets:
    """Test recent datasets list management."""

    def test_update_recent_datasets_adds_new(self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """
        Test adding a new path to recent datasets list.
        
        Tests that new dataset path is added to the front of the list.
        """
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        monkeypatch.setattr(pathlib.Path, "home", lambda: fake_home)

        config = AppConfig(appname="test_app")
        config.update_recent_datasets("/path/to/dataset1")

        assert config.recent_datasets == [str(pathlib.Path("/path/to/dataset1").resolve())]

    def test_update_recent_datasets_moves_existing_to_front(self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """
        Test that updating with existing path moves it to front.
        
        Tests re-ordering behavior when path already exists in list.
        """
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        monkeypatch.setattr(pathlib.Path, "home", lambda: fake_home)

        config = AppConfig(appname="test_app")
        config.recent_datasets = ["/path1", "/path2", "/path3"]
        config.update_recent_datasets("/path2")

        assert config.recent_datasets[0] == str(pathlib.Path("/path2").resolve())
        assert len(config.recent_datasets) == 3

    def test_update_recent_datasets_limits_to_ten(self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """
        Test that recent datasets list is limited to 10 entries.
        
        Tests that oldest entries are removed when limit is exceeded.
        """
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        monkeypatch.setattr(pathlib.Path, "home", lambda: fake_home)

        config = AppConfig(appname="test_app")
        # Add 11 datasets
        for i in range(11):
            config.update_recent_datasets(f"/path{i}")

        assert len(config.recent_datasets) == 10
        # Most recent should be first
        assert config.recent_datasets[0] == str(pathlib.Path("/path10").resolve())
        # Oldest (/path0) should be gone
        assert str(pathlib.Path("/path0").resolve()) not in config.recent_datasets

    def test_update_recent_datasets_accepts_pathlib_path(self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """
        Test that update_recent_datasets accepts both str and pathlib.Path.
        
        Tests type flexibility for path arguments.
        """
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        monkeypatch.setattr(pathlib.Path, "home", lambda: fake_home)

        config = AppConfig(appname="test_app")
        path = pathlib.Path("/path/to/dataset")
        config.update_recent_datasets(path)

        assert str(path.resolve()) in config.recent_datasets


class TestDatasetPreferences:
    """Test dataset preferences management."""

    def test_dataset_preferences_default_empty(self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """
        Test that dataset_preferences defaults to empty dict.
        
        Tests default initialization of dataset preferences.
        """
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        monkeypatch.setattr(pathlib.Path, "home", lambda: fake_home)

        config = AppConfig(appname="test_app")
        assert len(config.dataset_preferences) == 0

    def test_dataset_preferences_persist(self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """
        Test that dataset preferences are saved and loaded correctly.
        
        Tests full persistence cycle for dataset preferences.
        """
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        monkeypatch.setattr(pathlib.Path, "home", lambda: fake_home)

        config1 = AppConfig(appname="test_app")
        config1.dataset_preferences = {"dataset1": {"facet_id": 1, "model_id": "test-model"}, "dataset2": {"facet_id": 2}}
        config1.save()

        config2 = AppConfig(appname="test_app")
        assert config2.dataset_preferences == config1.dataset_preferences

    def test_invalid_dataset_preferences_resets(self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch,
                                                caplog: pytest.LogCaptureFixture) -> None:
        """
        Test that invalid dataset_preferences in config file is reset to empty dict.
        
        Tests error handling when dataset_preferences is not a dictionary.
        """
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        monkeypatch.setattr(pathlib.Path, "home", lambda: fake_home)

        # Create config with invalid dataset_preferences
        config_dir = fake_home / "test_app"
        config_dir.mkdir()
        config_file = config_dir / "config.yaml"
        with open(config_file, 'w', encoding='utf-8') as f:
            yaml.dump({"dataset_preferences": "not-a-dict"}, f)

        with caplog.at_level(logging.WARNING):
            config = AppConfig(appname="test_app")

        assert "Invalid dataset preferences found" in caplog.text
        assert len(config.dataset_preferences) == 0


class TestHIPVisibleDevices:
    """Test HIP_VISIBLE_DEVICES environment variable handling."""

    def test_hip_visible_devices_sets_env_var(self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """
        Test that hip_visible_devices config sets HIP_VISIBLE_DEVICES environment variable.
        
        Tests environment variable setting during config load.
        """
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        monkeypatch.setattr(pathlib.Path, "home", lambda: fake_home)

        # Clear env var first
        if "HIP_VISIBLE_DEVICES" in os.environ:
            monkeypatch.delenv("HIP_VISIBLE_DEVICES")

        config1 = AppConfig(appname="test_app")
        config1.hip_visible_devices = "0,1"
        config1.save()

        # Clear env var again before loading
        if "HIP_VISIBLE_DEVICES" in os.environ:
            del os.environ["HIP_VISIBLE_DEVICES"]

        _ = AppConfig(appname="test_app")
        assert os.environ.get("HIP_VISIBLE_DEVICES") == "0,1"

    def test_hip_visible_devices_none_does_not_set_env(self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """
        Test that None hip_visible_devices does not set environment variable.
        
        Tests that env var is not set when config value is None.
        """
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        monkeypatch.setattr(pathlib.Path, "home", lambda: fake_home)

        # Clear env var first
        if "HIP_VISIBLE_DEVICES" in os.environ:
            monkeypatch.delenv("HIP_VISIBLE_DEVICES")

        config = AppConfig(appname="test_app")
        assert config.hip_visible_devices is None
        assert "HIP_VISIBLE_DEVICES" not in os.environ
