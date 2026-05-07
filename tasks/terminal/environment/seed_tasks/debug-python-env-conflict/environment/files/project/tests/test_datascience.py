"""Test datascience-utils - requires numpy<1.24.0"""
import numpy as np
from datascience_utils import DataLoader

def test_datascience_loader():
    """Uses optimized_loader which breaks with numpy>=1.24.0"""
    loader = DataLoader()
    
    # optimized_loader was removed in numpy 1.24.0
    try:
        from datascience_utils.core import optimized_loader
        data = optimized_loader("test")
        assert data is not None
    except ImportError as e:
        if "optimized_loader" in str(e):
            raise ImportError("numpy too new for datascience-utils")
        raise

def test_legacy_numpy():
    """Tests legacy numpy behavior."""
    arr = np.array([[1, 2], [3, 4]])
    
    # Old numpy behavior changed in 1.24.0
    result = np.linalg.matrix_power(arr, 2)
    assert result.shape == (2, 2)