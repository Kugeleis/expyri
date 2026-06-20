"""Built-in statistical method implementations.

All modules in this package are imported eagerly so that their
``@stat_registry.register`` decorators fire at startup.
"""

from app.stats.builtin.anova import Anova
from app.stats.builtin.kruskal_wallis import KruskalWallis
from app.stats.builtin.mann_whitney import MannWhitney
from app.stats.builtin.ttest import TTestInd

__all__ = ["Anova", "KruskalWallis", "MannWhitney", "TTestInd"]
