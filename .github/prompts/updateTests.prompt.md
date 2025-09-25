---
mode: agent
description: Update pyFade test scripts to cover all new and changed features, ensuring comprehensive test coverage.
tools: ['edit', 'search', 'runCommands', 'usages', 'think', 'problems', 'runTests', 'pylanceDocuments', 'pylanceFileSyntaxErrors', 'pylanceImports', 'pylanceInstalledTopLevelModules', 'pylanceInvokeRefactoring', 'pylancePythonEnvironments', 'getPythonEnvironmentInfo', 'getPythonExecutableCommand']
---
Your task is to do thorough maintenance of the pyFade test scripts and `pytest` unit tests to ensure they cover all new and changed features in the codebase, providing comprehensive test coverage. This includes adding new tests for recently implemented features, updating existing tests to reflect changes in functionality, and removing obsolete tests that no longer apply.

Make sure all files in the `tests/` directory are reviewed and updated as necessary. Ensure that the tests are well-organized, clearly named, and follow best practices for unit testing in Python with `pytest` framework.

For debugging purposes, you *MUST* improve and expand unit tests, adding state logging as nessesary, with log-level DEBUG and running tests with debug output enabled. When debugging, plan for the future, make changes to unit tests reusable for future development, not just current debug session.

When not debugging, ensure tests run cleanly without debug output, and that they are efficient and reliable, managing verbosity and debug logging via appropriate `logging` module configurations.