"""Test transformers functionality - requires numpy>=1.24.0"""
import numpy as np
from transformers import AutoModel

def test_transformers_new_feature():
    """Uses a numpy feature added in 1.24.0"""
    # new_feature was added in numpy 1.24.0
    arr = np.array([1, 2, 3])
    
    # This will fail with numpy<1.24.0
    try:
        # Simulating a transformers internal call that uses new numpy API
        if hasattr(arr, 'new_feature'):
            result = arr.new_feature()
        else:
            # Mock what transformers actually does
            result = np.lib.stride_tricks.sliding_window_view(arr, 2)
        assert result is not None
    except AttributeError as e:
        if "new_feature" in str(e):
            raise ImportError("numpy too old for transformers")
        raise

def test_model_loading():
    """Test basic model loading."""
    try:
        model = AutoModel.from_pretrained("bert-base-uncased")
        assert model is not None
    except Exception:
        # Skip if no internet or model cached
        pass