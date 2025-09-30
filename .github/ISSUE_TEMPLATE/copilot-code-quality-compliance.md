---
name: Code Quality Compliance (Copilot)
about: Run Code Quality Compliance task
title: Code Quality Compliance iteration (Copilot)
labels: quality
assignees: ''

---

This is task for managing code quality and technical debt.

Some technical debt has been recently introduced in the codebase. This task is to iteratively improve the code quality till all acceptance goals are achieved.

# Acceptance goals
1. `pytest` **MUST** return zero failed tests.
2. `pylint py_fade` **MUST** return zero issues.
3. `pylint tests` **MUST** return zero issues.

# Task
Iterate over the codebase till all Acceptance goals are achieved.
