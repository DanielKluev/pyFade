---
mode: agent
description: Analyze task definition in the module-level docstring, identifying key requirements and components.
tools: ['edit', 'search', 'runCommands', 'usages', 'think', 'problems', 'runTests', 'pylanceDocuments', 'pylanceFileSyntaxErrors', 'pylanceImports', 'pylanceInstalledTopLevelModules', 'pylanceInvokeRefactoring', 'pylancePythonEnvironments', 'getPythonEnvironmentInfo', 'getPythonExecutableCommand']
---
Your task is to analyze the task definition provided in the module-level docstring of the current Python module. Identify and outline the key requirements, components, and any specific functionalities that need to be implemented or addressed.
Carefully read through the docstring to understand the context and objectives of the task. Break down the task into smaller, manageable parts if necessary, and highlight any dependencies or related components that may be affected. Study related files if needed to get a full understanding of the task.

Try to plan how you would approach implementing the task, considering best practices and project conventions.
If you identify any ambiguities or areas that require clarification, make note of them for further investigation.

Document your analysis clearly, providing a structured overview of the task definition and your proposed approach to addressing it. 
Separately provide section on any potential missing design or architectural choices, requirements and explanations required for high quality implementation of the task. Request that major changes to other components, which block implementation of this task should be clearly outlined in the task definition docstring.

Finally, compile thorough and comprehensive task definition that could be used for new GitHub Issue:
 - Issue draft should be in markdown format, fenced with triple backticks and `markdown` language tag.
 - Issue draft should be self-contained, with all details and nuances from original TODO items, docstrings, and your analysis included.
 - Issue draft should contain preliminary implementation plan and list of related components that may be affected by the changes.
 - Issue draft should contain all instructions from the relevant prompt files from `.github/prompts/*.prompt.md`, especially regarding project conventions, testing, linting, and documentation updates.
 - Double-check that the Issue draft is thorough and contains all necessary information, assume it will be handed off to a developer unfamiliar with the project or AI assistant.