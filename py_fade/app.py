"""Main entry point for the application.

Starts up the GUI, loads configuration, initializes providers, and coordinates dataset
access.
"""

from __future__ import annotations

import logging
import pathlib
import sys

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication, QWidget
from qt_material import apply_stylesheet

from py_fade.app_config import AppConfig
from py_fade.controllers.text_generation_controller import TextGenerationController
from py_fade.dataset.dataset import DatasetDatabase
from py_fade.dataset.prompt import PromptRevision
from py_fade.gui.auxillary.aux_google_icon_font import google_icon_font
from py_fade.gui.widget_dataset_top import WidgetDatasetTop
from py_fade.gui.widget_launcher import show_launcher
from py_fade.gui.widget_sample import WidgetSample
from py_fade.providers.providers_manager import InferenceProvidersManager, MappedModel


class PyFadeApp:
    """
    Faceted Alignment Dataset Editor application.
    Manages application-wide state, settings, and resources.
    """

    providers_manager: InferenceProvidersManager
    config: AppConfig
    available_models: list[str]
    current_dataset: DatasetDatabase | None = None
    cached_text_generation_controllers: dict[str, TextGenerationController]
    cached_text_generation_controllers_limit: int = 10
    cached_text_generation_controllers_list: list[TextGenerationController]
    launcher: QWidget | None
    widget: WidgetSample | None
    dataset_widget: WidgetDatasetTop | None
    q_app: QApplication | None
    debug_enabled: bool = False

    @classmethod
    def setup_logging(cls, is_debug: bool = False) -> None:
        """Configure logging for the application."""

        cls.debug_enabled = is_debug
        log_level = logging.DEBUG if is_debug else logging.INFO
        logging.basicConfig(
            level=log_level,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            handlers=[logging.StreamHandler(sys.stdout)],
        )
        logging.getLogger("ollama").setLevel(logging.WARNING)

    def __init__(
        self, config_path: str | pathlib.Path | None = None, is_debug: bool | None = None
    ) -> None:
        if is_debug is None:
            is_debug = self.debug_enabled
        self.is_debug = is_debug
        self.log = logging.getLogger("pyFadeApp")
        self.config = AppConfig("pyFade", debug=is_debug, config_path=config_path)
        self.providers_manager = InferenceProvidersManager(
            self.config.models,
            ollama_models_dir=self.config.ollama_models_dir,
            default_temperature=self.config.default_temperature,
            default_top_k=self.config.default_top_k,
        )
        self.available_models = list(self.providers_manager.model_provider_map.keys())
        self.cached_text_generation_controllers = {}
        self.cached_text_generation_controllers_list = []
        self.launcher = None
        self.widget = None
        self.dataset_widget = None
        self.q_app = None

    def create_new_dataset(self, path: str | pathlib.Path) -> pathlib.Path | None:
        """Create a new dataset at the given *path* and return its path on success."""
        path = pathlib.Path(path)
        if path.exists():
            self.log.error("Cannot create new dataset: file already exists at %s", path)
            return None
        try:
            dataset = DatasetDatabase(path)
            dataset.initialize()
            self.current_dataset = dataset
            self.log.info("Created new dataset at %s", path)
            self.config.update_recent_datasets(path)
            self.config.save()
            return path
        except (OSError, ValueError, RuntimeError) as exc:
            self.log.error("Failed to create new dataset at %s: %s", path, exc)
            return None

    def open_dataset(self, path: str | pathlib.Path, password: str) -> DatasetDatabase | None:
        """Open a dataset located at *path* using *password* and return it."""
        path = pathlib.Path(path)
        if not path.exists():
            self.log.error("Cannot open dataset: file does not exist at %s", path)
            return None
        if self.current_dataset and self.current_dataset.db_path == path:
            self.log.info("Dataset at %s is already open.", path)
            dataset = self.current_dataset
        else:
            dataset = DatasetDatabase(path, password=password)
            dataset.initialize()
            self.current_dataset = dataset

        # Direct .close() seem to be unsafe, schedule it on qt loop instead.
        if self.launcher is not None:
            QTimer.singleShot(0, self.close_launcher)

        self.config.update_recent_datasets(path)
        self.config.save()
        self.show_dataset_gui(dataset)
        return dataset

    def get_or_create_text_generation_controller(
        self,
        mapped_model: MappedModel | str,
        prompt_revision: PromptRevision | str,
        *,
        context_length: int | None = None,
        max_tokens: int | None = None,
        dataset: DatasetDatabase | None = None,
    ) -> TextGenerationController:
        """
        Get or create a TextGenerationController for the given model, dataset and prompt revision.
        """
        if dataset is None:
            if self.current_dataset is None:
                raise RuntimeError(
                    "No dataset is currently open. Please open a dataset first or provide a dataset parameter."
                )
            dataset = self.current_dataset

        # If mapped_model is str, expecting it's model_path, look it up in providers manager
        if isinstance(mapped_model, str):
            resolved_model = self.providers_manager.get_mapped_model(mapped_model)
            if resolved_model is None:
                raise ValueError(
                    f"Mapped model with name '{mapped_model}' not found in providers manager."
                )
            mapped_model = resolved_model

        if context_length is None:
            context_length = self.config.default_context_length
        if max_tokens is None:
            max_tokens = self.config.default_max_tokens

        # If prompt_revision is str, expecting it's prompt text. Look it up in dataset
        if isinstance(prompt_revision, str):
            prompt_revision = PromptRevision.get_or_create(
                dataset, prompt_revision, context_length, max_tokens
            )

        key = self._make_controller_cache_key(mapped_model, dataset, prompt_revision)
        if key not in self.cached_text_generation_controllers:
            controller = TextGenerationController(
                self,
                mapped_model,
                dataset,
                prompt_revision,
            )
            controller.load_cache()
            self.cached_text_generation_controllers[key] = controller
            self.cached_text_generation_controllers_list.append(controller)
            # Limit cache size to `cached_text_generation_controllers_limit` controllers
            if (
                len(self.cached_text_generation_controllers_list)
                > self.cached_text_generation_controllers_limit
            ):
                oldest = self.cached_text_generation_controllers_list.pop(0)
                oldest_key = self._make_controller_cache_key(
                    oldest.mapped_model, oldest.dataset, oldest.prompt_revision
                )
                del self.cached_text_generation_controllers[oldest_key]
        return self.cached_text_generation_controllers[key]

    def close_launcher(self) -> None:
        """Close the launcher window if it is open."""

        if self.launcher is not None:
            self.launcher.close()
            self.launcher = None

    def run_gui(self, sample_id: str | None = None) -> int:
        """Run the GUI application and return the Qt exit code."""

        self.log.info("Starting pyFade GUI application.")
        self.q_app = QApplication(sys.argv)
        google_icon_font.load()
        if sample_id:
            return self.run_single_sample_gui(sample_id)

        # If we don't have a sample ID, we run the main GUI
        self.launcher = show_launcher(self)
        q_app = self._require_q_app()
        apply_stylesheet(q_app, theme=self.config.theme)
        return q_app.exec()

    def run_single_sample_gui(self, sample_id: str) -> int:
        """Run the GUI for a single sample identified by *sample_id*."""

        self.log.info("Running GUI for single sample ID: %s", sample_id)
        self.widget = WidgetSample(parent=None, app=self, sample=None)
        q_app = self._require_q_app()
        apply_stylesheet(q_app, theme=self.config.theme)
        self.widget.show()
        return q_app.exec()

    def show_dataset_gui(self, dataset: DatasetDatabase) -> None:
        """Show the main dataset GUI for the given *dataset*."""

        self.log.info("Showing dataset GUI for dataset at %s", dataset.db_path)
        self.dataset_widget = WidgetDatasetTop(parent=None, app=self, dataset=dataset)
        q_app = self._require_q_app()
        apply_stylesheet(q_app, theme=self.config.theme)
        self.dataset_widget.show()

    def _make_controller_cache_key(
        self,
        mapped_model: MappedModel,
        dataset: DatasetDatabase,
        prompt_revision: PromptRevision,
    ) -> str:
        """Build a stable cache key for controller instances."""

        return "|".join(
            (
                mapped_model.model_id,
                mapped_model.provider.id,
                str(dataset.db_path),
                str(prompt_revision.id),
            )
        )

    def _require_q_app(self) -> QApplication:
        """Return the current QApplication instance or raise if it is missing."""

        if self.q_app is None:
            raise RuntimeError("QApplication must be initialised before entering the event loop.")
        return self.q_app


# Backwards compatibility for existing imports within the project.
pyFadeApp = PyFadeApp  # pylint: disable=invalid-name
