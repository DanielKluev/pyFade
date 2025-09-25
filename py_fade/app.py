"""
Main entry point for the application. Starts up GUI if needed, loads configs, databases and so on.
"""
import pathlib, logging, yaml, json, sys, os
from py_fade.app_config import AppConfig

## Dataset / DB
from py_fade.dataset.dataset import DatasetDatabase
from py_fade.dataset.prompt import PromptRevision
from py_fade.dataset.sample import Sample

## Providers
from py_fade.providers.base_provider import BasePrefillAwareProvider
from py_fade.providers.providers_manager import InferenceProvidersManager, MappedModel
from py_fade.providers.ollama import PrefillAwareOllama

## Controllers
from py_fade.controllers.text_generation_controller import TextGenerationController

## UI
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
from qt_material import apply_stylesheet
from py_fade.gui.widget_launcher import show_launcher
from py_fade.gui.auxillary.aux_google_icon_font import google_icon_font
from py_fade.gui.widget_sample import WidgetSample
from py_fade.gui.widget_dataset_top import WidgetDatasetTop


_global_debug_flag = False

class pyFadeApp:
    """
    Faceted Alignment Dataset Editor application.
    Manages application-wide state, settings, and resources.
    """
    providers_manager: InferenceProvidersManager
    config: AppConfig
    available_models: list[str]
    current_dataset: DatasetDatabase|None = None
    cached_text_generation_controllers: dict[str, TextGenerationController]
    cached_text_generation_controllers_limit: int = 10
    @classmethod
    def setup_logging(cls, is_debug: bool = False):
        global _global_debug_flag
        _global_debug_flag = is_debug
        log_level = logging.DEBUG if is_debug else logging.INFO
        logging.basicConfig(
            level=log_level,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            handlers=[logging.StreamHandler(sys.stdout)],
        )
        logging.getLogger("ollama").setLevel(logging.WARNING)

    def __init__(self, config_path: str | pathlib.Path | None = None, is_debug: bool | None = None):
        if is_debug is None:
            is_debug = _global_debug_flag
        self.is_debug = is_debug
        self.log = logging.getLogger("pyFadeApp")
        self.config = AppConfig("pyFade", debug=is_debug, config_path=config_path)
        self.providers_manager = InferenceProvidersManager(self.config.models, ollama_models_dir=self.config.ollama_models_dir, default_temperature=self.config.default_temperature, default_top_k=self.config.default_top_k)
        self.available_models = list(self.providers_manager.model_provider_map.keys())
        self.cached_text_generation_controllers = {}
        self.cached_text_generation_controllers_list = []

    def create_new_dataset(self, path: str | pathlib.Path) -> pathlib.Path | None:
        """
        Create a new dataset at the given path. Returns the path if successful, None otherwise.
        """
        path = pathlib.Path(path)
        if path.exists():
            self.log.error(f"Cannot create new dataset: file already exists at {path}")
            return None
        try:
            dataset = DatasetDatabase(path)
            dataset.initialize()
            self.current_dataset = dataset
            self.log.info(f"Created new dataset at {path}")
            self.config.update_recent_datasets(path)
            self.config.save()
            return path
        except Exception as e:
            self.log.error(f"Failed to create new dataset at {path}: {e}")
            return None
        
    def open_dataset(self, path: str | pathlib.Path, password: str) -> DatasetDatabase | None:
        """
        Open an existing dataset at the given path with the given password. Returns the DatasetDatabase if successful, None otherwise.
        """
        path = pathlib.Path(path)
        if not path.exists():
            self.log.error(f"Cannot open dataset: file does not exist at {path}")
            return None
        if self.current_dataset and self.current_dataset.db_path == path:
            self.log.info(f"Dataset at {path} is already open.")
        else:
            dataset = DatasetDatabase(path, password=password)
            dataset.initialize()
            self.current_dataset = dataset

        # Direct .close() seem to be unsafe, schedule it on qt loop instead.
        if self.launcher:
            QTimer.singleShot(0, self.close_launcher)

        self.config.update_recent_datasets(path)
        self.config.save()
        self.show_dataset_gui(self.current_dataset)


    def get_or_create_text_generation_controller(self, mapped_model: "MappedModel|str", prompt_revision: "PromptRevision|str", context_length: int|None = None, max_tokens: int|None = None, dataset: "DatasetDatabase|None" = None) -> "TextGenerationController":
        """
        Get or create a TextGenerationController for the given model, dataset and prompt revision.
        """
        if dataset is None:
            if self.current_dataset is None:
                raise RuntimeError("No dataset is currently open. Please open a dataset first or provide a dataset parameter.")
            dataset = self.current_dataset

        # If mapped_model is str, expecting it's model_path, look it up in providers manager
        if isinstance(mapped_model, str):
            mapped_model = self.providers_manager.get_mapped_model(mapped_model) # type: ignore
            if not isinstance(mapped_model, MappedModel):
                raise ValueError(f"Mapped model with name '{mapped_model}' not found in providers manager.")
            
        if context_length is None:
            context_length = self.config.default_context_length
        if max_tokens is None:
            max_tokens = self.config.default_max_tokens

        # If prompt_revision is str, expecting it's prompt text. Look it up in dataset
        if isinstance(prompt_revision, str):
            prompt_revision = PromptRevision.get_or_create(dataset, prompt_revision, context_length, max_tokens)
            
        key = f"{mapped_model.model_id}|{mapped_model.provider.id}|{dataset.db_path}|{prompt_revision.id}"
        if not key in self.cached_text_generation_controllers:
            controller = TextGenerationController(self, mapped_model, dataset, prompt_revision)
            controller.load_cache()
            self.cached_text_generation_controllers[key] = controller
            self.cached_text_generation_controllers_list.append(controller)
            # Limit cache size to `cached_text_generation_controllers_limit` controllers
            if len(self.cached_text_generation_controllers_list) > self.cached_text_generation_controllers_limit:
                oldest = self.cached_text_generation_controllers_list.pop(0)
                oldest_key = f"{oldest.mapped_model.model_id}|{oldest.mapped_model.provider.id}|{oldest.dataset.db_path}|{oldest.prompt_revision.id}"
                del self.cached_text_generation_controllers[oldest_key]
        return self.cached_text_generation_controllers[key]

    def close_launcher(self):
        if self.launcher:
            self.launcher.close()
            self.launcher = None

    def run_gui(self, sample_id: str | None = None):
        """
        Run the GUI application.
        """
        self.log.info("Starting pyFade GUI application.")
        self.q_app = QApplication(sys.argv)
        google_icon_font.load()
        if sample_id:
            return self.run_single_sample_gui(sample_id)

        # If we don't have a sample ID, we run the main GUI
        self.launcher = show_launcher(self)
        apply_stylesheet(self.q_app, theme=self.config.theme)
        return self.q_app.exec()

    def run_single_sample_gui(self, sample_id: str):
        """
        Run the GUI application for a single sample ID.
        """
        self.log.info(f"Running GUI for single sample ID: {sample_id}")
        self.widget = WidgetSample(parent=None, app=self, sample=None)
        apply_stylesheet(self.q_app, theme=self.config.theme)
        self.widget.show()
        return self.q_app.exec()
    
    def show_dataset_gui(self, dataset: DatasetDatabase):
        """
        Show the main dataset GUI for the given dataset.
        """
        self.log.info(f"Showing dataset GUI for dataset at {dataset.db_path}")
        self.dataset_widget = WidgetDatasetTop(parent=None, app=self, dataset=dataset)
        apply_stylesheet(self.q_app, theme=self.config.theme)
        self.dataset_widget.show()
