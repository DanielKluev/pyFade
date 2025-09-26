---
mode: agent
description: Refactor current module and related components according to TODO items in module-level docstring, following project conventions.
tools: ['edit', 'search', 'runCommands', 'usages', 'think', 'problems', 'runTests', 'pylanceDocuments', 'pylanceFileSyntaxErrors', 'pylanceImports', 'pylanceInstalledTopLevelModules', 'pylanceInvokeRefactoring', 'pylancePythonEnvironments', 'getPythonEnvironmentInfo', 'getPythonExecutableCommand']
---
Your task is to refactor the current Python module and any related components as specified in the module-level docstring. Follow the project conventions and ensure that the code is clean, efficient, and maintainable.

First plan your approach by carefully reading the module-level docstring to understand the intended functionality and any TODO items that need to be addressed. Identify any related components in the codebase that may also require changes to ensure consistency and proper integration.

Then, examine existing unit tests to check if all current functionality is adequately covered. If there are gaps in test coverage, add new tests to cover the changes you plan to make, check that they work for current functionality. Ensure that all tests follow the project's testing conventions and are efficient and reliable. Before making changes to the codebase, run the existing test suite to confirm that all tests pass successfully. Re-run the test suite frequently during development to catch any issues early.

Make the necessary changes to the codebase, addressing all TODO items in the module-level docstring. Ensure that your changes adhere to PEP 8 style guidelines and follow the established project conventions.

After completing the refactoring, update or add test scripts to cover all new and changed features, ensuring comprehensive test coverage. Run the entire test suite again to confirm that all tests pass successfully and that the codebase remains stable.

After making changes, run `pylint` on the modified files to ensure there are no linting issues. Address any issues that arise, adhering to PEP 8 style guidelines and project conventions. Re-test after fixing linting issues to ensure stability.

Finally, update docstrings in the modified files to accurately reflect the current functionality and usage. Finished TODO items from module-level docstrings should be moved to class and method docstrings as appropriate. Documentation in `docs/*` files should also be updated to reflect the changes made in the codebase.