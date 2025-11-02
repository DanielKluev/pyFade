# UI Layout Change: Role Tag Buttons Relocated

## Before (Original Layout)

```
┌─────────────────────────────────────┬─────────────────────────────┐
│                                     │  Controls Panel             │
│  Prompt Area                        │  ┌─────────────────────┐   │
│  (Text Editor)                      │  │ Sample ID: ...      │   │
│                                     │  │ Title: ...          │   │
│                                     │  │ Group Path: ...     │   │
│                                     │  │ Notes: ...          │   │
│                                     │  │ Tags: ...           │   │
│                                     │  │ Context: ... Max: ..│   │
├─────────────────────────────────────┤  │ Role Tag: [S][U][A] │ ← Old location
│  Tokens: Prompt: 0 | Response: 0   │  │ Actions: [💾][📋][🔍]│   │
│  | Total: 0 / 0                     │  │ ☑ Show archived     │   │
└─────────────────────────────────────┴─────────────────────────────┘
```

## After (New Layout)

```
┌─────────────────────────────────────┬─────────────────────────────┐
│                                     │  Controls Panel             │
│  Prompt Area                        │  ┌─────────────────────┐   │
│  (Text Editor)                      │  │ Sample ID: ...      │   │
│                                     │  │ Title: ...          │   │
│                                     │  │ Group Path: ...     │   │
│                                     │  │ Notes: ...          │   │
├─────────────────────────────────────┤  │ Tags: ...           │   │
│  Tokens: Prompt: 0 | Response: 0   │  │ Context: ... Max: ..│   │
│  | Total: 0 / 0   [S] [U] [A] ←NEW │  │ Actions: [💾][📋][🔍]│   │
└─────────────────────────────────────┴──│ ☑ Show archived     │   │
                                         └─────────────────────┘   │
```

## Key Changes

1. **Role tag buttons moved** from controls panel to prompt area
2. **New horizontal layout** under the prompt area with:
   - Token usage label on the **left**
   - Flexible spacer in the **middle** 
   - Three role buttons (S, U, A) on the **right**
3. **Controls panel simplified** - Role tag row removed

## Benefits

- Role buttons are now **immediately below** the prompt where they are used
- More **logical grouping** - all prompt-related controls together
- **Improved workflow** - buttons are closer to the text area they affect
- **Cleaner controls panel** - reduced clutter in the right-side panel
