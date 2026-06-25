"""Built-in filter implementations.

All modules in this package are imported eagerly so that their
``@filter_registry.register`` decorators fire at startup.
"""

from app.filters.builtin.category_filter import CategoryFilter
from app.filters.builtin.cluster_exclusion import ClusterExclusionFilter
from app.filters.builtin.numeric_range import NumericRangeFilter

__all__ = ["CategoryFilter", "NumericRangeFilter", "ClusterExclusionFilter"]
