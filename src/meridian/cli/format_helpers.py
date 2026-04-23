"""Re-export shim — formatting primitives now live in lib.core.formatting.

Kept for backwards compatibility with any CLI-layer code that imports
from this path.
"""

from meridian.lib.core.formatting import kv_block, tabular

__all__ = ["kv_block", "tabular"]
