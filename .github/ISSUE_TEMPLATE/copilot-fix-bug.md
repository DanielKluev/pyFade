---
name: Fix Bug (Copilot)
about: Delegate bug fixing to Copilot, requiring acceptance tests to pass.
title: "Bug: X (Copilot)"
labels: bug
assignees: ''

---

This is task to fix bug outlined below.

### Steps to reproduce

1. Open dataset
2. Perform action Y
3. Observe issue Z

### Expected behavior

XXX

### Task

Investigate and fix the bug described above. Follow key steps below.

# Key steps
1. Analyze described bug and all related components which may be involved. Pay attention to existing unit tests, docstrings, and comments.
2. Design new unit test which reproduce the bug, if such tests do not already exist. Check result of `pytest` to see if any existing tests are failing. If no existing tests are failing, you must add new tests which reproduce the bug. Ensure that bug is properly reproduced by the tests you add.
3. Create a plan for implementing the task, breaking it down into manageable steps, starting with most independent parts.
4. Plan for testing of each part and step.
5. Make the necessary changes to the codebase to fix root cause of the issue and all other issues you spot during code inspection and problem analysis. 
6. Make sure that unit tests you added to reproduce the bug are passing, and that all existing tests pass successfully. Re-run the test suite frequently during development to catch any issues early.
7. Update documentation and docstrings as needed.
8. Ensure all acceptance goals are met.

# Tools
- `yapf` for code formatting, configured in `pyproject.toml`. Run `yapf -i <file>` to format a file in place. Consider `yapf` to be the source of truth for formatting. Run it on changed files before committing.
- `pytest` for unit tests. Use `pytest-qt` for testing PyQt6 widgets. Tests should run in Qt offscreen mode to avoid GUI popups.
- `pylint` for static code analysis.

# References
- `.github/copilot-instructions.md` - instructions for Copilot

# Acceptance goals
1. Described problem is fixed, application behaves as expected.
2. All changed code must be extensively covered by `pytest` unit tests.
3. `pytest` **MUST** return zero failed tests.
4. `pylint py_fade` **MUST** return zero issues.
5. `pylint tests` **MUST** return zero issues.