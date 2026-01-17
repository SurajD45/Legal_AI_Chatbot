#!/usr/bin/env python3
"""Quick test script - run this to verify offline mode works"""

import os
import sys

# CRITICAL: Set BEFORE imports
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1' 
os.environ['HF_HOME'] = '/models/huggingface'

print("✓ Environment variables set")
print(f"  HF_HOME: {os.environ.get('HF_HOME')}")
print(f"  HF_HUB_OFFLINE: {os.environ.get('HF_HUB_OFFLINE')}")
print(f"  TRANSFORMERS_OFFLINE: {os.environ.get('TRANSFORMERS_OFFLINE')}")

# NOW import
from sentence_transformers import SentenceTransformer

print("\n✓ Importing SentenceTransformer...")

try:
    print("\n✓ Loading model from cache...")
    model = SentenceTransformer(
        'intfloat/multilingual-e5-large',
        cache_folder='/models/huggingface'
    )
    print(f"\n✅ SUCCESS! Model loaded!")
    print(f"   Dimension: {model.get_sentence_embedding_dimension()}")
    
    # Test encoding
    print("\n✓ Testing encoding...")
    vec = model.encode("test", show_progress_bar=False)
    print(f"✅ Encoding works! Vector shape: {vec.shape}")
    
except Exception as e:
    print(f"\n❌ FAILED: {e}")
    import traceback
    traceback.print_exc()