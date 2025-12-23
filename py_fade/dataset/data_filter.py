"""Helper objects for filtering dataset queries."""

from sqlalchemy.orm import Query
from sqlalchemy import or_


class DataFilter:
    """
    Wrapper around various simple and chained filters to apply to datasets.

    Supports text search on title, prompt text, and ID (if search value is a valid integer).
    """

    filters: list[dict]

    def __init__(self, filters: list[dict]):
        self.filters = filters

    def apply_to_query(self, query: Query) -> Query:
        """
        Apply the filters to the given SQLAlchemy query object.

        For text_search filters on Sample queries, searches title, prompt_text, and ID fields (if search value is a valid integer).
        For text_search filters on PromptRevision queries, searches prompt_text field.
        """
        # pylint: disable=import-outside-toplevel  # Avoid circular import
        from py_fade.dataset.sample import Sample
        from py_fade.dataset.prompt import PromptRevision

        for criteria in self.filters:
            if criteria.get("type") == "text_search":
                search_value = str(criteria.get("value", "")).strip().lower()
                if not search_value:
                    continue

                # Check if search value is a valid integer for ID filtering
                try:
                    search_id = int(search_value)
                    is_valid_id = True
                except ValueError:
                    search_id = None
                    is_valid_id = False

                # Check if this is a Sample or PromptRevision query by inspecting the query's column descriptions
                if hasattr(query, 'column_descriptions'):
                    entity_types = [desc['type'] for desc in query.column_descriptions if 'type' in desc]

                    if Sample in entity_types:
                        # For Sample queries, filter on title, prompt_text, and ID (if search value is a valid integer)
                        # Join with PromptRevision to enable filtering on prompt_text
                        query = query.join(Sample.prompt_revision)

                        # Build OR conditions for title and prompt_text
                        conditions = [Sample.title.ilike(f"%{search_value}%"), PromptRevision.prompt_text.ilike(f"%{search_value}%")]

                        # Add ID condition if search value is a valid integer
                        if is_valid_id:
                            conditions.append(Sample.id == search_id)

                        query = query.filter(or_(*conditions))

                    elif PromptRevision in entity_types:
                        # For PromptRevision queries, filter on prompt_text
                        query = query.filter(PromptRevision.prompt_text.ilike(f"%{search_value}%"))

        return query

    def is_empty(self) -> bool:
        """Return ``True`` when no filter definitions are configured."""

        return not self.filters
