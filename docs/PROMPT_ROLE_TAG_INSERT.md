# Prompt Role Tag Insert Feature

## Overview

This feature enables users to easily insert multi-turn conversation role tags into prompts using the flat prefix template format.

## Features

### 1. Context Menu in Prompt Editor

Right-click anywhere in the prompt text area to access a context menu with the following options:

- **Insert System Tag at Cursor** - Inserts `<|system|>` at the current cursor position
- **Insert User Tag at Cursor** - Inserts `<|user|>` at the current cursor position
- **Insert Assistant Tag at Cursor** - Inserts `<|assistant|>` at the current cursor position
- **Insert System Tag at End** - Inserts `<|system|>` at the end of the text on a new line
- **Insert User Tag at End** - Inserts `<|user|>` at the end of the text on a new line
- **Insert Assistant Tag at End** - Inserts `<|assistant|>` at the end of the text on a new line

### 2. Quick Access Buttons

Three buttons are available in the prompt control panel:

- **S** - Inserts system tag
- **U** - Inserts user tag
- **A** - Inserts assistant tag

These buttons always insert tags at the end of the prompt text on a new line.

## Validation Rules

### System Tag Constraints

1. **Only one system tag allowed** - If you try to insert a second system tag, a warning dialog will appear
2. **Must be at beginning** - The system tag button always inserts at the beginning of the prompt text

### User and Assistant Tags

- Can be inserted multiple times
- Can be placed at any position in the prompt

## Tag Format

The feature uses the flat prefix template format:

- System: `<|system|>`
- User: `<|user|>`
- Assistant: `<|assistant|>`

## Example Usage

### Creating a Multi-Turn Conversation

1. Click the **S** button to insert a system tag at the beginning
2. Type your system prompt after the tag
3. Click the **U** button to insert a user tag on a new line
4. Type the user's message
5. Click the **A** button to insert an assistant tag
6. Type the assistant's response

Result:
```
<|system|>
You are a helpful assistant.
<|user|>
What is the capital of France?
<|assistant|>
The capital of France is Paris.
```

### Using Context Menu for Precise Placement

1. Right-click at any position in your prompt
2. Select "Insert User Tag at Cursor" to insert at that exact position
3. Or select "Insert User Tag at End" to append at the end

## Implementation Details

- Context menu is implemented in `PlainTextEdit` widget
- Role tag buttons are implemented in `WidgetSample` widget
- System tag validation prevents duplicates and enforces beginning placement
- All tags use the flat prefix template format defined in `py_fade/providers/flat_prefix_template.py`

## Testing

Comprehensive test coverage includes:

- 12 tests for PlainTextEdit role tag insertion methods
- 14 tests for WidgetSample role tag buttons
- All tests verify proper tag insertion, validation, and button functionality
