# Complex Sample Filters - Usage Guide

## Overview

Complex sample filters allow you to define sophisticated filtering rules that can be combined with AND logic to find specific subsets of samples. Each filter consists of multiple rules that can search for text, check for tag presence, or verify facet ratings.

## Creating Filters Programmatically

Since the filter management dialog is not yet implemented, filters must be created programmatically. Here's how:

### Basic Filter Creation

```python
from py_fade.dataset.sample_filter import SampleFilter

# Create a simple text search filter
filter_rules = [
    {"type": "string", "value": "important", "negated": False}
]

sample_filter = SampleFilter.create(
    dataset,
    name="Important Samples",
    description="Samples containing 'important' in title or prompt",
    filter_rules=filter_rules
)
dataset.commit()
```

### Filter Rule Types

#### 1. String Search Rule
Searches in sample title, group_path, and prompt text:

```python
{"type": "string", "value": "search term", "negated": False}
```

#### 2. Tag Rule
Matches samples that have a specific tag:

```python
from py_fade.dataset.tag import Tag

tag = Tag.get_by_name(dataset, "Done")
{"type": "tag", "value": tag.id, "negated": False}
```

#### 3. Facet Rule
Matches samples that have completions rated for a specific facet:

```python
from py_fade.dataset.facet import Facet

facet = Facet.get_by_name(dataset, "Quality")
{"type": "facet", "value": facet.id, "negated": False}
```

### Using NOT (Negation)

Set `"negated": True` to match samples that DON'T meet the criteria:

```python
# Match samples NOT tagged with "WIP"
tag_wip = Tag.get_by_name(dataset, "WIP")
{"type": "tag", "value": tag_wip.id, "negated": True}
```

### Complex Multi-Rule Example

```python
from py_fade.dataset.sample_filter import SampleFilter
from py_fade.dataset.tag import Tag
from py_fade.dataset.facet import Facet

# Get tags and facets
tag_done = Tag.get_by_name(dataset, "Done")
tag_wip = Tag.get_by_name(dataset, "WIP")
facet_quality = Facet.get_by_name(dataset, "Quality")

# Create filter: Important + Done + NOT WIP + Quality rated
filter_rules = [
    {"type": "string", "value": "important", "negated": False},
    {"type": "tag", "value": tag_done.id, "negated": False},
    {"type": "tag", "value": tag_wip.id, "negated": True},
    {"type": "facet", "value": facet_quality.id, "negated": False},
]

sample_filter = SampleFilter.create(
    dataset,
    name="Ready Important Items",
    description="Important samples that are done, not WIP, and quality-rated",
    filter_rules=filter_rules
)
dataset.commit()
```

## Using Filters

### In the Navigation Panel

1. Select "Samples by Filter" from the "Show:" dropdown
2. Select your saved filter from the "Filter:" dropdown
3. Toggle between flat and hierarchical view as needed
4. Samples matching ALL rules will be displayed

### Programmatically

```python
from py_fade.dataset.sample import Sample

# Get filter by name
sample_filter = SampleFilter.get_by_name(dataset, "Ready Important Items")

# Apply the filter
matching_samples = Sample.fetch_with_complex_filter(
    dataset, 
    sample_filter.get_rules()
)

print(f"Found {len(matching_samples)} matching samples")
for sample in matching_samples:
    print(f"  - {sample.title}")
```

## Managing Filters

### Update a Filter

```python
sample_filter = SampleFilter.get_by_name(dataset, "My Filter")

# Update name
sample_filter.update(dataset, name="New Name")

# Update description
sample_filter.update(dataset, description="New description")

# Update rules
new_rules = [
    {"type": "string", "value": "updated", "negated": False}
]
sample_filter.update(dataset, filter_rules=new_rules)
```

### Delete a Filter

```python
sample_filter = SampleFilter.get_by_name(dataset, "My Filter")
sample_filter.delete(dataset)
```

### List All Filters

```python
all_filters = SampleFilter.get_all(dataset, order_by_date=True)
for f in all_filters:
    print(f"{f.name}: {f.description}")
    print(f"  Rules: {len(f.get_rules())}")
```

## Filter Logic

- **AND Logic**: ALL rules in a filter must match for a sample to be included
- **Rule Evaluation**: Each rule is evaluated independently and returns True/False
- **Negation**: When `negated=True`, the rule result is inverted (True becomes False, False becomes True)
- **Empty Filters**: A filter with no rules matches all samples

## Example Scripts

### Create "High Priority Incomplete" Filter

```python
# Find samples that are:
# - Tagged "High Priority"
# - NOT tagged "Done"
# - Have "TODO" in title or prompt

tag_priority = Tag.get_by_name(dataset, "High Priority")
tag_done = Tag.get_by_name(dataset, "Done")

filter_rules = [
    {"type": "tag", "value": tag_priority.id, "negated": False},
    {"type": "tag", "value": tag_done.id, "negated": True},
    {"type": "string", "value": "TODO", "negated": False},
]

SampleFilter.create(
    dataset,
    name="High Priority Incomplete TODOs",
    description="Urgent incomplete tasks",
    filter_rules=filter_rules
)
dataset.commit()
```

### Create "Quality Approved" Filter

```python
# Find samples that:
# - Have Quality facet rating
# - Are tagged "Reviewed"
# - NOT in "Drafts" group path

facet_quality = Facet.get_by_name(dataset, "Quality")
tag_reviewed = Tag.get_by_name(dataset, "Reviewed")

filter_rules = [
    {"type": "facet", "value": facet_quality.id, "negated": False},
    {"type": "tag", "value": tag_reviewed.id, "negated": False},
    {"type": "string", "value": "Drafts", "negated": True},
]

SampleFilter.create(
    dataset,
    name="Quality Approved Final",
    description="Reviewed, quality-rated samples not in drafts",
    filter_rules=filter_rules
)
dataset.commit()
```

## Future Enhancements

A filter management dialog would provide:
- Visual rule builder with dropdowns and pickers
- Drag-and-drop rule ordering
- Preview of matching samples
- Duplicate/clone filters
- Import/export filter definitions

The underlying functionality is already complete and ready for such a UI.
