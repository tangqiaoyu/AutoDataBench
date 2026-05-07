"""
Mock datascience-utils library that has incompatible numpy requirements.
In reality, this would be installed via pip.
"""

import numpy as np

class DataLoader:
    def load(self, path):
        return np.array([1, 2, 3])

# Simulate a module that breaks with numpy>=1.24.0
try:
    # This import would fail in real datascience-utils with new numpy
    from numpy.lib.stride_tricks import sliding_window_view
    optimized_loader = sliding_window_view
except ImportError:
    optimized_loader = None

# Package metadata
__version__ = "2.1.0"
__numpy_version__ = "<1.24.0"  # Requires older numpy