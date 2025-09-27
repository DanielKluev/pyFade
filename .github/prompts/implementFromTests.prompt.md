---
mode: agent
description: Implement feature from pytest unit tests, using unit tests as specification.
tools: ['edit', 'search', 'runCommands', 'usages', 'think', 'problems', 'runTests', 'pylanceDocuments', 'pylanceFileSyntaxErrors', 'pylanceImports', 'pylanceInstalledTopLevelModules', 'pylanceInvokeRefactoring', 'pylancePythonEnvironments', 'getPythonEnvironmentInfo', 'getPythonExecutableCommand']
---
Your task is to implement code changes and related changes in other codebase files in order to make the pytest unit tests pass.
Use the unit tests as the primary specification for the required functionality. Carefully read through the test cases to understand the expected behavior and outcomes. Identify any missing functionality or components that need to be implemented or modified in order to satisfy the test cases.

Plan your approach by breaking down the task into smaller, manageable parts if necessary. Consider any dependencies or related components that may also require changes to ensure consistency and proper integration.

Make the necessary changes to the codebase, ensuring that your implementations adhere to PEP 8 style guidelines and follow the established project conventions.

If changes to the codebase introduce new functionality or modify existing behavior beyond existing tests, add new test cases to cover these changes. Ensure that all tests follow the project's testing conventions and are efficient and reliable. Before making changes to the codebase, run the existing test suite to confirm that all tests pass successfully. Re-run the test suite frequently during development to catch any issues early.

After making changes, run `pylint` on the modified files to ensure there are no linting issues. Address any issues that arise, adhering to PEP 8 style guidelines and project conventions. Re-test after fixing linting issues to ensure stability.

Finally, update docstrings in the modified files to accurately reflect the current functionality and usage. Remove completed TODO items from the module-level docstrings.