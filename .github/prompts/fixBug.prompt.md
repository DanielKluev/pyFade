---
mode: agent
description: Fix bug outlined in the module-level docstring, ensuring the code adheres to project conventions and passes all tests.
tools: ['edit', 'search', 'runCommands', 'usages', 'think', 'problems', 'runTests', 'pylanceDocuments', 'pylanceFileSyntaxErrors', 'pylanceImports', 'pylanceInstalledTopLevelModules', 'pylanceInvokeRefactoring', 'pylancePythonEnvironments', 'getPythonEnvironmentInfo', 'getPythonExecutableCommand']
---
Your task is to fix bugs in the current Python module and any related components as specified in the module-level docstring. Follow the project conventions and ensure that the code is clean, efficient, and maintainable.

First you must design new unit tests which reproduce the bug, if such tests do not already exist. Check result of `pytest` to see if any existing tests are failing. If no existing tests are failing, you must add new tests which reproduce the bug. Ensure that bug is properly reproduced by the tests you add. 

Then, plan your approach by carefully inspecting all related code to understand the root cause of the bug. Identify any related components in the codebase that may also require changes to ensure consistency and proper integration.

Make the necessary changes to the codebase, addressing all issues in the module-level docstring. Ensure that your changes adhere to PEP 8 style guidelines and follow the established project conventions.

Make sure that unit tests you added to reproduce the bug are passing, and that all existing tests pass successfully. Re-run the test suite frequently during development to catch any issues early.

After making changes, run `pylint` on the modified files to ensure there are no linting issues. Address any issues that arise, adhering to PEP 8 style guidelines and project conventions. Re-test after fixing linting issues to ensure stability.

Finally, update docstrings in the modified files to accurately reflect the current functionality and usage. Remove fixed problems from the module-level docstring.