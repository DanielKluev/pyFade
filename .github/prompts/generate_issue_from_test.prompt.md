---
mode: agent
description: Implement feature from pytest unit tests, using unit tests as specification.
model: Auto (copilot)
tools: ['edit', 'search', 'runCommands', 'usages', 'think', 'problems', 'runTests', 'pylanceDocuments', 'pylanceFileSyntaxErrors', 'pylanceImports', 'pylanceInstalledTopLevelModules', 'pylanceInvokeRefactoring', 'pylancePythonEnvironments', 'getPythonEnvironmentInfo', 'getPythonExecutableCommand']
---
Your task is to producde high quality GitHub Issue draft in markdown format, fenced with triple backticks and `markdown` language tag, for implementing all needed features and changes in order to make the pytest unit tests pass.

Use the unit tests as the primary specification for the required functionality. Carefully read through the test cases to understand the expected behavior and outcomes. Identify any missing functionality or components that need to be implemented or modified in order to satisfy the test cases.

Identify all relevant modules and files that are important to the implementation of the task or need changes in order to implement the task. Study related files if needed to get a full understanding of the task.

Plan major steps and approach for implementing the task, considering best practices and project conventions.

Include all information you have identified in your analysis in the GitHub Issue draft. Ensure that the draft is self-contained and provides a clear and comprehensive overview of the task, including any dependencies or related components that may be affected.
Include path to target test file in top level overview of the issue and then in the implementation plan section and references section of the issue draft.

Request to run tests, linting and all other QA steps during and after implementation of the task.

Finally, compile thorough and comprehensive task definition that could be used for new GitHub Issue:
 - Issue draft should be in markdown format, fenced with triple backticks and `markdown` language tag.
 - Issue draft should be self-contained, with all details and nuances from original TODO items, docstrings, and your analysis included.
 - Issue draft should contain preliminary implementation plan and list of related components that may be affected by the changes.
 - Issue draft should contain all instructions from the relevant prompt files from `.github/prompts/*.prompt.md`, especially regarding project conventions, testing, linting, and documentation updates.
 - Double-check that the Issue draft is thorough and contains all necessary information, assume it will be handed off to a developer unfamiliar with the project or AI assistant.