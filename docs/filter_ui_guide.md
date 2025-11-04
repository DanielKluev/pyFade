# Sample Filter Management UI

## Overview

The Sample Filter Management UI provides a complete graphical interface for creating, editing, and managing complex sample filters. It follows the same Material Design patterns as Tags and Facets widgets.

## UI Components

### 1. WidgetSampleFilter - Main Filter Editor

**Location**: Opens in a tab when:
- Clicking "New Sample Filter" button in navigation
- Selecting a filter from "Sample Filters" view

**Features**:
- **Header**: Purple theme (#9C27B0) with "filter_list" icon
- **Name Field**: Required, must be unique across all filters
- **Description Field**: Multi-line text area for filter purpose
- **Date Created**: Read-only, shows when filter was created
- **Filter Rules List**: Visual display of all rules with human-readable text
- **Rule Management Buttons**:
  - `Add Rule`: Opens DialogFilterRule to create new rule
  - `Edit Rule`: Opens DialogFilterRule to modify selected rule
  - `Remove Rule`: Deletes selected rule with confirmation
- **CRUD Buttons**:
  - `Save`: Creates or updates the filter in database
  - `Cancel`: Closes tab (closes unsaved changes)
  - `Delete`: Removes filter with confirmation (only for existing filters)

**Validation**:
- Name must be unique
- Description must be 5-2000 characters
- Shows error messages above buttons
- Save button disabled when validation fails

### 2. DialogFilterRule - Rule Editor Dialog

**Opens when**: User clicks "Add Rule" or "Edit Rule" in WidgetSampleFilter

**Features**:
- **Rule Type Selector**: Dropdown with three options:
  - `String Search`: Matches text in title, group path, or prompt
  - `Tag`: Matches samples with specific tag
  - `Facet`: Matches samples with ratings for specific facet
  
- **Value Input** (changes based on type):
  - String: Text input field
  - Tag: Dropdown populated with available tags
  - Facet: Dropdown populated with available facets
  
- **NOT Checkbox**: "NOT (negate this rule)"
  - When checked, matches samples that DON'T meet the criteria
  - Example: "NOT Tag Done" = samples without Done tag
  
- **Help Text**: Explains each rule type with examples

- **Buttons**:
  - `OK`: Saves rule and closes dialog
  - `Cancel`: Discards changes and closes dialog

### 3. Navigation Integration

#### "Samples by Filter" View
- **Purpose**: Show samples that match a selected filter's rules
- **Filter Selector**: Dropdown showing all saved filters
- **View Toggle**: Flat list vs grouped by path
- **Behavior**: Updates sample list when filter selection changes

#### "Sample Filters" View
- **Purpose**: List all available sample filters for management
- **Display Format**: "FilterName (N rules)" with description tooltip
- **Click Action**: Opens filter in editor tab
- **New Button**: "New Sample Filter" creates blank filter
- **Sorted**: Newest filters first (by creation date)

## Usage Workflows

### Creating a New Filter

1. Navigate to "Sample Filters" view
2. Click "New Sample Filter" button
3. Enter filter name and description
4. Click "Add Rule" to add first rule:
   - Select rule type
   - Configure value (text, tag, or facet)
   - Check "NOT" if negating
   - Click OK
5. Repeat for additional rules (all combined with AND logic)
6. Click "Save" to create filter

### Editing an Existing Filter

1. Navigate to "Sample Filters" view
2. Click on the filter to edit
3. Opens in new tab
4. Modify name, description, or rules:
   - Select rule and click "Edit Rule" to change
   - Click "Remove Rule" to delete
   - Click "Add Rule" to add more
5. Click "Save" to update

### Deleting a Filter

1. Open filter in editor tab
2. Click "Delete" button (red)
3. Confirm deletion in dialog
4. Filter removed from database
5. Tab closes automatically

### Using a Filter to View Samples

1. Navigate to "Samples by Filter" view
2. Select filter from dropdown
3. Samples matching ALL rules are displayed
4. Toggle flat/grouped view as needed
5. Click sample to open in editor

## UI Design Patterns

**Follows pyFade Standards**:
- Material Design principles
- Consistent with Tag and Facet widgets
- Purple theme (#9C27B0) for sample filters
- Standard button icons and layouts
- Material Symbols icon font
- Validation error messages above buttons
- Delete button only visible for existing items

**Tab Integration**:
- Opens in WidgetDatasetTop tabs
- Tab title: "SF: FilterName" or "New Sample Filter"
- Saves/deletes trigger sidebar refresh
- Cancel closes tab if unsaved

## Examples

### Example 1: High Priority Incomplete Tasks

**Filter Name**: "High Priority TODOs"
**Rules**:
1. Tag "High Priority" (not negated)
2. NOT Tag "Done" (negated)
3. String "TODO" (not negated)

**Result**: Shows samples that are tagged "High Priority", NOT tagged "Done", and contain "TODO" in title/prompt/path.

### Example 2: Quality Reviewed Finals

**Filter Name**: "Quality Approved Final"
**Rules**:
1. Facet "Quality" (not negated)
2. Tag "Reviewed" (not negated)
3. NOT String "Draft" (negated)

**Result**: Shows samples with Quality ratings, tagged "Reviewed", and NOT containing "Draft".

## Technical Details

- **Save Location**: SQLite database in `sample_filters` table
- **Rules Storage**: JSON-encoded in `filter_rules` column
- **Signals**: Emits `sample_filter_saved`, `sample_filter_deleted`, `sample_filter_cancelled`
- **Base Class**: Extends `CrudFormWidget` for consistent behavior
- **Session Management**: Uses SQLAlchemy session from DatasetDatabase

## Testing

All UI components are covered by pytest tests in:
- `tests/test_ui/test_widget_sample_filter.py` (6 tests)
- Tests cover creation, editing, deletion, validation, and rule management
- All tests use Qt offscreen mode to avoid GUI popups
