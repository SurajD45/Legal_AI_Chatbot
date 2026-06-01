"""
Phase 3A — Negative Expansion Tests (Regression Guard)

Verifies that static query expansion does NOT corrupt queries that already pass.
Tests three categories:
1. Exact match queries — should not be expanded (short-circuited by detect_sections)
2. Passing semantic queries — expansion should be additive only or no-op
3. Edge case queries — should return unchanged
"""

import sys
sys.path.insert(0, ".")

from app.core.query_expander import expand_query

PASSED = 0
FAILED = 0


def assert_test(name: str, condition: bool, detail: str = ""):
    global PASSED, FAILED
    if condition:
        PASSED += 1
        print(f"  PASS  {name}")
    else:
        FAILED += 1
        print(f"  FAIL  {name}  {detail}")


print("=" * 60)
print("  Negative Expansion Tests — Regression Guard")
print("=" * 60)

# --------------------------------------------------
# Test 1: Exact match queries
# These are short-circuited by detect_sections() in retriever.py,
# but verify expand_query() itself doesn't corrupt them.
# --------------------------------------------------
print("\n--- Test 1: Exact Match Queries ---")

exact_queries = [
    "What is Section 302 of IPC?",
    "Explain Section 420 IPC",
    "What does Section 498A say?",
    "Section 304B of Indian Penal Code",
]

for q in exact_queries:
    expanded = expand_query(q)
    # Original query must be fully preserved at the start
    assert_test(
        f"'{q[:40]}...' preserves original",
        expanded.startswith(q),
        f"got: {expanded[:80]}",
    )

# --------------------------------------------------
# Test 2: Passing semantic queries
# These currently pass at Recall@5 = 1.0 or are partially passing.
# Expansion must be additive only (no token removal/rewriting).
# --------------------------------------------------
print("\n--- Test 2: Passing Semantic Queries ---")

passing_semantic = [
    ("punishment for murder in India", "murder"),
    ("what is the punishment for theft?", "theft"),
    ("punishment for attempt to murder", "murder"),
    ("kidnapping laws in IPC", "kidnapping"),
]

for q, expected_key in passing_semantic:
    expanded = expand_query(q)
    # Must preserve original
    assert_test(
        f"'{q[:40]}...' preserves original",
        expanded.startswith(q),
        f"got: {expanded[:80]}",
    )
    # Must contain original terms
    assert_test(
        f"'{q[:40]}...' still contains '{expected_key}'",
        expected_key in expanded.lower(),
        f"got: {expanded[:80]}",
    )

# --------------------------------------------------
# Test 3: Edge case queries (no expected sections)
# These should NOT be expanded — no dictionary keys match.
# --------------------------------------------------
print("\n--- Test 3: Edge Case Queries ---")

edge_cases = [
    "Is jaywalking a crime under IPC?",
    "income tax evasion IPC section",
]

for q in edge_cases:
    expanded = expand_query(q)
    assert_test(
        f"'{q[:40]}...' returns unchanged",
        expanded == q,
        f"got: {expanded[:80]}",
    )

# --------------------------------------------------
# Test 4: Target expansion queries (should expand correctly)
# These are the queries we EXPECT to improve.
# --------------------------------------------------
print("\n--- Test 4: Target Expansion Queries ---")

target_expansions = [
    ("chori ki saja kya hai?", ["theft", "punishment"]),
    ("dahej hatya kya hoti hai?", ["dowry", "murder"]),
    ("agar koi kisi ko blackmail kare toh kya section lagega?", ["extortion"]),
    ("domestic violence laws IPC", ["cruelty"]),
    ("patni par zulm karne par husband ko kya saza milti hai?", ["cruelty", "wife", "punishment"]),
]

for q, must_contain in target_expansions:
    expanded = expand_query(q)
    # Must preserve original
    assert_test(
        f"'{q[:40]}...' preserves original",
        expanded.startswith(q),
        f"got: {expanded[:80]}",
    )
    # Must contain expected expansion terms
    for term in must_contain:
        assert_test(
            f"'{q[:40]}...' contains '{term}'",
            term in expanded.lower(),
            f"got: {expanded}",
        )

# --------------------------------------------------
# Summary
# --------------------------------------------------
print(f"\n{'=' * 60}")
print(f"  Results: {PASSED} passed, {FAILED} failed")
print(f"{'=' * 60}")

if FAILED > 0:
    print("\n  REGRESSION DETECTED — Do NOT proceed to benchmark.")
    sys.exit(1)
else:
    print("\n  All tests passed — Safe to proceed to benchmark.")
    sys.exit(0)
