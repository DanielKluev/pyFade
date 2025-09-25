---
mode: agent
description: Update a pyFade Python module so its UI matches the module-level docstring while following project conventions.
tools: ['edit', 'search', 'runCommands', 'usages', 'think', 'problems', 'runTests', 'pylanceDocuments', 'pylanceFileSyntaxErrors', 'pylanceImports', 'pylanceInstalledTopLevelModules', 'pylanceInvokeRefactoring', 'pylancePythonEnvironments', 'getPythonEnvironmentInfo', 'getPythonExecutableCommand']
---
Your task is to implement UI changes and related changes in other codebase files as specified in the module-level docstrings of the provided Python module. Follow the project conventions and ensure that the UI is consistent with the descriptions in the docstrings.

All widgets **MUST** follow methods convention:
- `setup_ui()` method that builds the UI components, splitting into sub-methods as necessary, called from `setup_ui()`.
- `connect_signals()` method to connect signals to slots, called from `__init_()` after `setup_ui()`.
- `set_XXX()` methods for setting data and populating the UI with values, e.g. `set_sample(self, sample: Sample|None)`. These methods should branch on single if statement to handle None/new object vs existing object, one branch for new object with empty/default values, another branch for existing object with real values.

Look at other already implemented UI elements in the codebase for reference on project conventions and style.

Reuse existing components and theming from the pyFade project.

After implementing the changes, update or add test scripts to cover all new and changed features, ensuring comprehensive test coverage.

For debugging purposes, you **MUST** improve and expand unit tests, adding state logging as nessesary, with log-level DEBUG and running tests with debug output enabled. When debugging, plan for the future, make changes to unit tests reusable for future development, not just current debug session. 

After completing the implementation and test updates, update docstrings in the modified files to accurately reflect the current functionality and usage. Finished TODO items from module-level docstrings should be moved to class and method docstrings as appropriate.