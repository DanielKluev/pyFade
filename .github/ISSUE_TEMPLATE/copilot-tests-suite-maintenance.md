---
name: Tests Suite Maintenance (Copilot)
about: Run Tests Suite Maintenance task
title: Tests Suite Maintenance iteration (Copilot)
labels: quality
assignees: ''

---

This is task for managing quality of the tests suite.

# Goals
- Structure of tests should match codebase one to one, each test module named as `test_<module_under_test>.py` and replicating directory structure of the codebase.
- All tests should use shared helpers and fixtures to initialize common objects. Goal to have each test be easy to read and understand, utility code should be factored out.
- Test docstrings should describe flow that is being tested and explicitly list edge cases being covered.
- Analyze codebase for untested edge cases and add tests for them.
- Tests should be aggressively merged together unless contradicting each other. If test A tests first part of flow, and test B tests second part of flow, they should be merged into one test that tests the whole flow.
- Check coverage and add missing tests for uncovered code.

# Important Limitations
- **NEVER** add new ignores to pyproject.toml.
- Code duplication should be handled by refactoring, **NOT** by adding ignores.

# Acceptance goals
1. `pytest` **MUST** return zero failed tests.
2. `pylint py_fade` **MUST** return zero issues.
3. `pylint tests` **MUST** return zero issues.
4. Coverage **MUST** be equal to or higher than starting coverage, aiming for 90%+.

# Task
Iterate over the codebase till all Acceptance goals are achieved.
