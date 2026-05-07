"""Main project module - demonstrates the conflicting usage patterns."""

import numpy as np
from transformers import AutoModel
from datascience_utils import DataLoader

def process_data():
    """Process data using both libraries."""
    # transformers expects newer numpy features
    model = AutoModel.from_pretrained("bert-base-uncased")
    
    # datascience-utils uses older numpy patterns
    loader = DataLoader()
    data = loader.load("sample.csv")
    
    return model, data

if __name__ == "__main__":
    try:
        model, data = process_data()
        print("Success: Both libraries work together")
    except Exception as e:
        print(f"Conflict detected: {e}")