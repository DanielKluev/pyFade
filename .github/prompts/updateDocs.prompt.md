---
mode: agent
description: Update project documentation, .github/copilot-instructions.md and so on to keep it accurate and up to date.
tools: ['edit', 'search', 'runCommands', 'usages', 'think', 'problems', 'runTests', 'pylanceDocuments', 'pylanceFileSyntaxErrors', 'pylanceImports', 'pylanceInstalledTopLevelModules', 'pylanceInvokeRefactoring', 'pylancePythonEnvironments', 'getPythonEnvironmentInfo', 'getPythonExecutableCommand']
---
Your task is to update the project documentation files, including README.md, .github/copilot-instructions.md, and any other relevant documentation files, to ensure they accurately reflect the current state of the codebase. This includes updating descriptions of features, installation instructions, usage guidelines, and any other relevant information.

Cross-check between items which are still yet to be implemented and the documentation, ensuring that all features are documented and any discrepancies are resolved. Non-implemented features should be clearly marked as TODO items in roadmaps, and implemented features should be fully documented.

Make sure `requirements.txt` file is up to date with all dependencies used in the codebase, and that installation instructions in the documentation reflect the current setup process. Do not pin versions unless absolutely necessary.

For `.github/copilot-instructions.md`, check current project structure, dependencies, and setup instructions to ensure they are accurate and up to date, as well as current practices and conventions used in the codebase.