## Quick task receipt

This file helps a code-writing agent onboard the pyFade repository quickly. It contains a concise summary of the project, reproducible environment and build/run/validation steps tested for this repository, a short layout map pointing to the important files, and common pitfalls to avoid. Trust these instructions; only search the repository if something here is missing or clearly out of date.

---

## 1) High-level summary

- Purpose: pyFADE is a desktop GUI application for creating and managing faceted alignment datasets (SFT/DPO/PPO exports, ranking, token-level inspection, prefill-aware generation). It bundles a Qt6 GUI, providers for local model backends (e.g., Ollama), dataset management, and helper scripts like a boundary detector.
- Primary language/runtime: Python (code and pyc files indicate usage with CPython 3.11). The GUI uses PyQt6 and qt_material for styling.
- Repo scale: small project (dozens of Python modules, no large binary assets). Expect transient model downloads (sentence-transformers, spaCy) that may take minutes.

## 2) Project type, frameworks, and notable dependencies

- Python 3.11 (project produced .pyc files tagged cpython-311). Target OS examples use Windows paths.
- GUI: PyQt6, qt_material.
- Config: custom AppConfig class, all defaults set as class attributes, overridden by `config.yaml` in user config dir.
- Providers: integration with Ollama (`ollama` Python package) — requires Ollama runtime/daemon if used at runtime. `mock-echo-model` added for testing without a real model backend.
- Database and persistence: SQLAlchemy ORM, using SQLite or SQLCipher.
- ML utilities: sentence-transformers, scikit-learn (cosine similarity), spaCy, numpy.
- Other modules referenced: qt_material, ollama, dynaconf.
- Note: `requirements.txt` contains only `PyQt6>=6.6`. The code imports more packages; see Build/Install steps below.

## 3) Code style
- Follows PEP 8 style guidelines.
- ALWAYS use 4 spaces for indentation (no tabs).
- Type hints are used extensively.
- UI classes should have separate setup_ui() method that builds the UI components and set_XXX() methods for setting data and populating the UI with values.
- UI set_XXX() methods should branch on single if statement to handle None/new object vs existing object, one branch for new object with empty/default values, another branch for existing object with real values.
- SQLAlchemy ORM is used for database models and queries, orchestrated via DatasetDatabase class.
- Following Google Material Design principles for UI layout and behavior, using qt_material for theming.

## 4) Testing, build, and run instructions
 - Special `mock-echo-model` can be used to test generation without needing a real model backend. It simply echoes the prompt back.
 - For testing, scripts in `tests/` can be created or modified to test various components, functionality, and performance.

## 5) UI
 - Follows Google Material Design principles for UI layout and behavior, using qt_material for theming.
 - For buttons and icons, using Google Material Symbols font, accessible from `py_fade.gui.aux_google_icon_font` module, with `google_icon_font` singleton instance.
 - Facets, Tags, Export Templates are managed via sidebar navigation, details for view/edit in separate widgets.

## 6) Project layout (short map to important files and their purpose)

Top-level files (root):
- `README.md` — project overview and features.
- `requirements.txt` — currently only `PyQt6>=6.6` (incomplete).
- `run.py` — application entrypoint; parses args and starts `py_fade.app.py`.
- `detect_boundary.py` — standalone script that uses sentence-transformers and spaCy.

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
