## Quick task receipt

This file helps a code-writing agent onboard the pyFade repository quickly. It contains a concise summary of the project, reproducible environment and build/run/validation steps tested for this repository, a short layout map pointing to the important files, and common pitfalls to avoid. Trust these instructions; only search the repository if something here is missing or clearly out of date.

---

## 1) High-level summary

- Purpose: pyFADE is a desktop GUI for curating faceted alignment datasets. It provides an IDE-style PyQt6 workspace for browsing samples, facets, tags, beam searches, and export templates backed by a SQLite database plus extensible inference providers.
- Primary language/runtime: Python (code and pyc files indicate usage with CPython 3.11). The GUI uses PyQt6 and qt_material for styling.
- Repo scale: small project (dozens of Python modules, no large binary assets). Optional ML downloads (sentence-transformers, spaCy) are only needed for helper scripts.

## 2) Project type, frameworks, and notable dependencies

- Python 3.11 (project produced `.pyc` files target CPython 3.11). Target OS examples use Windows paths but the code is cross-platform.
- GUI: PyQt6 with qt_material theming.
- Config: `AppConfig` persists YAML under the user config directory (recent datasets, provider models, per-dataset state).
- Providers: deterministic mock provider (default), Ollama integration (`ollama` package), optional local llama.cpp backend (`llama-cpp-python`).
- Persistence: SQLAlchemy ORM backed by SQLite files.
- Core runtime dependencies are listed in `requirements.txt`: PyQt6, qt-material, SQLAlchemy, numpy, tiktoken, ollama.
- Optional extras: sentence-transformers, scikit-learn, spaCy (for `detect_boundary.py`), llama-cpp-python (for GGUF models).
- Tests are written with `pytest` and run in Qt offscreen mode.

## 3) Code style
- Follows PEP 8 style guidelines.
- **ALWAYS** use 4 spaces for indentation. **NEVER** use tabs.
- Type hints are used extensively.
- Keep code documented with docstrings and comments. **NEVER** remove comments, instead update them if they are out of date.
- Line length limit is 140 characters. Do not split function signatures or calls across multiple lines unless absolutely necessary.
- All modules, classes, and functions should have docstrings. Docstrings should start on new line after triple double quotes. Docstrings for class should describe the purpose of the class and any important details. Docstrings for methods should describe the purpose of the method, its parameters, return values, and any important details. Test docstrings should describe what is being tested and the expected outcome.
- Use `logging` module for logging, do not use print statements. Use appropriate log levels (DEBUG, INFO, WARNING, ERROR, CRITICAL). Use per-class loggers via `self.log = logging.getLogger(CLASS_NAME)`. Use lazy evaluation of log messages via `%` of the logger methods, e.g. `logger.debug("Message: %s", variable)` whenever possible.
- Do not use local imports unless absolutely necessary to avoid circular dependencies, prefer module-level imports.
- Use f-strings for string formatting, except in logging calls where lazy evaluation via `%` is preferred.
- UI classes should have separate setup_ui() method that builds the UI components and set_XXX() methods for setting data and populating the UI with values.
- UI set_XXX() methods should branch on single if statement to handle None/new object vs existing object, one branch for new object with empty/default values, another branch for existing object with real values.
- SQLAlchemy ORM is used for database models and queries, orchestrated via DatasetDatabase class.
- Following Google Material Design principles for UI layout and behavior, using qt_material for theming.

Example of correct code style:
```python
"""
`ModuleName` is providing implementation for XYZ.
Key classes: `ClassName1`, `ClassName2`
"""
class ClassName1:
    """
    ClassName1 does XYZ.
    """
    attribute1: int
    attribute2: str

    def method_name(self, param1: int, param2: str) -> bool:
        """
        Do something important.

        Uses `param1` to do X and `param2` to do Y.

        Returns the return value.
        """
        # First, log the method call with parameters
        self.log.debug("Executing method_name with param1=%d, param2=%s", param1, param2)
        # Method implementation here
        return True
```

## 4) Testing, build, and run instructions
- For testing, scripts in `tests/` can be created or modified to test various components, functionality, and performance. Use `pytest` framework for unit tests.
- By default, tests should use only the `mock-echo-model` provider to avoid dependencies on external model backends and high computational requirements. Tests for real LLM providers should be isolated and clearly marked, ensuring they do not interfere with the main test suite and never get run by default.
- Tests that involve mock or real generation should use FLAT_PREFIX_SYSTEM/FLAT_PREFIX_USER/FLAT_PREFIX_ASSISTANT markers for system/user/assistant messages, as defined in `py_fade.providers.flat_prefix_template`. Provider implementations will call `flat_prefix_template_to_messages()` with prompt and prefill to convert these flat prefixes to common Messages API format.
- For debugging purposes, you **MUST** improve and expand unit tests, adding state logging as nessesary, with log-level DEBUG and running tests with debug output enabled. When debugging, plan for the future, make changes to unit tests reusable for future development, not just current debug session. Run `pytest --log-cli-level=DEBUG` to see debug output, possibly targeting specific test modules or classes.
- When not debugging, ensure tests run cleanly without debug output, and that they are efficient and reliable, managing verbosity and debug logging via appropriate `logging` module configurations.
- To run the application, use `python run.py` from the project root. This will launch the GUI.
- To run entire test suite, use `pytest` from the project root (PyQt6 must be installed for the widgets).
- Regularly run `pylint` on the codebase to ensure there are no linting issues. Address any issues that arise, adhering to PEP 8 style guidelines and project conventions.
- You are **NOT** allowed to run arbitrary python code or add temporary debug scripts. All testing and debugging **ONLY** as described above, via unit tests and logging.
- **NEVER** log sensitive information such as passwords or API keys. Ensure that any logging of data is done in a way that does not expose sensitive information.

## 5) UI
- Follows Google Material Design principles for UI layout and behavior, using qt_material for theming.
- For buttons and icons, using Google Material Symbols font, accessible from `py_fade.gui.aux_google_icon_font` module, with `google_icon_font` singleton instance.
- Facets, Tags, Export Templates are managed via sidebar navigation, details for view/edit in separate widgets.

## 6) Project layout (short map to important files and their purpose)

Top-level files (root):
- `README.md` — project overview and features.
- `requirements.txt` — core runtime dependencies (PyQt6, qt-material, SQLAlchemy, numpy, tiktoken, ollama).
- `run.py` — application entrypoint; parses args and starts `py_fade.app.py`.
- `Changelog.md` — summary of notable updates.

Python package `py_fade/` (important modules):
- `py_fade/app.py` — main app class `pyFadeApp`, GUI launcher, config wiring; note the hardcoded DB path.
- `py_fade/app_config.py` — dynaconf wrapper, default settings, and config file location behavior.
- `py_fade/gui/` — GUI widgets and launchers (e.g., `widget_launcher.py`, `widget_sample.py`, `widget_completion.py`). Modify GUI components here.
- `py_fade/gui/components/` — reusable GUI components (e.g., `widget_token_picker.py`).
- `py_fade/dataset/` — dataset management and persistence code.
- `py_fade/providers/` — provider implementations for model backends (e.g., `ollama.py`, `base_provider.py`); For testing there's `mock_echo_model.py` that simulates a model by echoing the prompt.
- `tests/` — scripts to test various components, functionality, and performance.

---

If you find this file is out of date, update it and include the commands you ran and the observed outputs briefly.
