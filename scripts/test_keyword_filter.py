import sys
sys.path.insert(0, ".")

from app.core.query_condenser import _is_contextual_query

tests = [
    ("give me definition then", True),
    ("What is Section 420?", False),
    ("what is the punishment?", True),
    ("What is Section 302?", False),
    ("is it bailable?", True),
    ("What is theft?", False),
    ("what are the exceptions?", True),
    ("how many years imprisonment?", True),
    ("explain Section 379", False),
    ("tell me more about this offence", True),
]

all_pass = True
for query, expected in tests:
    result = _is_contextual_query(query)
    status = "PASS" if result == expected else "FAIL"
    if status == "FAIL":
        all_pass = False
    print(f"  [{status}] {repr(query):50} -> {result} (expected {expected})")

print()
print("All tests passed!" if all_pass else "SOME TESTS FAILED!")
