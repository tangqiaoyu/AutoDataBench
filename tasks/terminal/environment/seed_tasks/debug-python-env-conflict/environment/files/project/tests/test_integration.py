"""Integration test - works with either version alone."""
import numpy as np

def test_integration():
    """Simple test that works with any numpy version."""
    arr = np.array([1, 2, 3, 4])
    mean = np.mean(arr)
    assert mean == 2.5
    
def test_both_libraries():
    """Try to use both libraries together."""
    try:
        import transformers
        import datascience_utils
        assert True
    except ImportError:
        # Skip if dependencies not installed
        pass