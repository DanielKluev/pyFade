---
mode: agent
description: Run pylint on the project and fix all issues, ensuring the code adheres to PEP 8 and project conventions.
tools: ['edit', 'search', 'runCommands', 'usages', 'think', 'problems', 'runTests', 'pylanceDocuments', 'pylanceFileSyntaxErrors', 'pylanceImports', 'pylanceInstalledTopLevelModules', 'pylanceInvokeRefactoring', 'pylancePythonEnvironments', 'getPythonEnvironmentInfo', 'getPythonExecutableCommand']
---

Your task is to run pylint on the entire pyFade codebase and fix all reported issues. Ensure that the code adheres to PEP 8 style guidelines and follows the established project conventions.

Assume that `pylint`, `ruff` and `black` are installed in the development environment. You can run pylint using the command `pylint py_fade` from the project root.

Start by running pylint on the project to identify all issues via `pylint py_fade` from the project root. Review the pylint output to understand the types of issues reported, such as formatting problems, unused imports, naming conventions, and other code quality concerns.
Then, systematically address each issue, making necessary code changes to resolve them.

Ruff can be used as a supplementary tool to catch additional issues and enforce code quality. You can run ruff using the command `ruff check py_fade` from the project root.

Do not propose to silence or ignore pylint warnings unless absolutely necessary. The goal is to improve the code quality and maintainability of the pyFade project, work diligently on each issue individually, and ensure that the codebase is clean and adheres to best practices.
Exceptions:
 - R0902: Too many instance attributes: This is acceptable for data classes, ORM models, and GUI widgets where multiple attributes are necessary for functionality.
 - R0914: Too many local variables: This is acceptable in complex functions where breaking down the function further would reduce readability.
 - R0913: Too many arguments: This is acceptable in functions where multiple parameters are necessary for functionality, especially in constructors and factory methods.
 - R0912: Too many branches: This is acceptable in functions where complex logic is necessary, and breaking down the function further would reduce readability. One such case is form validation functions.


Make sure all changes are covered by existing or new unit tests. If you add new tests, ensure they follow the project's testing conventions and are efficient and reliable. Re-run the test suite to confirm that all tests pass successfully after your changes.