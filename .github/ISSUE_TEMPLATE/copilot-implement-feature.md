---
name: Implement Feature (Copilot)
about: Delegate feature implementation to Copilot, requiring acceptance tests to pass.
title: Implement Feature X (Copilot)
labels: enhancement
assignees: ''

---

This is task to implement feature: X

# Context

# Feature Overview

# Important Feature Details

# Key steps
1. Analyze the task and all related components which may be involved. Pay attention to existing unit tests, docstrings, and comments.
2. Create a plan for implementing the task, breaking it down into manageable steps, starting with most independent parts.
3. Plan for testing of each part and step.
4. Implement the task in small steps, running tests and linting after each step.
5. Update documentation and docstrings as needed.
6. Ensure all acceptance goals are met.

# Tools
- `yapf` for code formatting, configured in `pyproject.toml`. Run `yapf -i <file>` to format a file in place. Consider `yapf` to be the source of truth for formatting. Run it on changed files before committing.
- `pytest` for unit tests. Use `pytest-qt` for testing PyQt6 widgets. Tests should run in Qt offscreen mode to avoid GUI popups.
- `pylint` for static code analysis.

# References
- `.github/copilot-instructions.md` - instructions for Copilot

# Acceptance goals
1. Described feature is fully implemented as per the specifications.
2. All changed code must be extensively covered by `pytest` unit tests.
3. `pytest` **MUST** return zero failed tests.
4. `pylint py_fade` **MUST** return zero issues.
5. `pylint tests` **MUST** return zero issues.