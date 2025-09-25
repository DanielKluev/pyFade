class DataFilter:
    """
    Wrapper around various simple and chained filters to apply to datasets.

    Currently just limit to simple str search.
    """
    filters: list[dict]
    def __init__(self, filters: list[dict]):
        self.filters = filters

    def apply_to_query(self, query):
        """
        Apply the filters to the given SQLAlchemy query object.
        """
        return query