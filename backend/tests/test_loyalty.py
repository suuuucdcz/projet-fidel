"""Unit tests for the pure loyalty logic — no DB, no network."""
from loyalty import compute_scan_result, next_objective

TIERS = [{"threshold": 5, "reward": "Café"}, {"threshold": 10, "reward": "Viennoiserie"}]


# --- points / stamps -------------------------------------------------------
def test_points_increment():
    assert compute_scan_result("points", 0, 3, "Réduction", []) == (1, False, None)


def test_points_reward_and_reset():
    assert compute_scan_result("points", 2, 3, "Réduction", []) == (0, True, "Réduction")


def test_stamps_behaves_like_points():
    assert compute_scan_result("stamps", 4, 5, "Boisson", []) == (0, True, "Boisson")


# --- tiers ------------------------------------------------------------------
def test_tiers_intermediate_reward_no_reset():
    # reaching 5 unlocks Café, balance stays at 5
    assert compute_scan_result("tiers", 4, 0, "", TIERS) == (5, True, "Café")


def test_tiers_between_tiers_no_reward():
    assert compute_scan_result("tiers", 5, 0, "", TIERS) == (6, False, None)


def test_tiers_top_reward_resets():
    # reaching the top tier (10) unlocks Viennoiserie and resets to 0
    assert compute_scan_result("tiers", 9, 0, "", TIERS) == (0, True, "Viennoiserie")


def test_tiers_unsorted_input_is_handled():
    unsorted = [{"threshold": 10, "reward": "B"}, {"threshold": 5, "reward": "A"}]
    assert compute_scan_result("tiers", 4, 0, "", unsorted) == (5, True, "A")


def test_tiers_empty_falls_through():
    assert compute_scan_result("tiers", 3, 0, "", []) == (4, False, None)


# --- next_objective ---------------------------------------------------------
def test_next_objective_points():
    assert next_objective("points", 2, 8, "Réduction", []) == (8, "Réduction")


def test_next_objective_tiers_first():
    assert next_objective("tiers", 0, 0, "", TIERS) == (5, "Café")


def test_next_objective_tiers_after_first():
    assert next_objective("tiers", 5, 0, "", TIERS) == (10, "Viennoiserie")
