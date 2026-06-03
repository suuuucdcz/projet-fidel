"""Pure loyalty computation (no DB / no network) so the scan logic is unit-testable.

Loyalty types:
- "points" / "stamps": a single threshold. Reward fires at the threshold, then the
  card resets to 0. ("stamps" is presentation-only — same mechanics as points.)
- "tiers": several (threshold, reward) milestones. A reward fires when the balance
  reaches a tier's threshold; the card resets to 0 once the top tier is reached.
"""
from typing import Optional


def _sorted_tiers(tiers):
    return sorted(
        (t for t in (tiers or []) if t and t.get("threshold")),
        key=lambda t: t["threshold"],
    )


def compute_scan_result(loyalty_type, current_points, reward_threshold, reward_description, tiers):
    """Apply a single +1 scan.

    Returns (new_points, reward_triggered, reward_desc) where reward_desc is the
    just-unlocked reward when reward_triggered is True, else None.
    """
    new_points = current_points + 1

    if loyalty_type == "tiers":
        st = _sorted_tiers(tiers)
        if not st:
            return new_points, False, None
        max_threshold = st[-1]["threshold"]
        reward_triggered = False
        reward_desc = None
        for t in st:
            if new_points == t["threshold"]:
                reward_triggered = True
                reward_desc = t["reward"]
        if new_points >= max_threshold:
            new_points = 0
        return new_points, reward_triggered, reward_desc

    # points / stamps
    if reward_threshold and new_points >= reward_threshold:
        return 0, True, reward_description
    return new_points, False, None


def next_objective(loyalty_type, points, reward_threshold, reward_description, tiers):
    """Return (next_threshold, next_reward) describing the upcoming goal, for the
    card's "X points to go" display."""
    if loyalty_type == "tiers":
        st = _sorted_tiers(tiers)
        if st:
            for t in st:
                if t["threshold"] > points:
                    return t["threshold"], t["reward"]
            # Past the top tier (shouldn't happen since we reset) -> show the top one.
            return st[-1]["threshold"], st[-1]["reward"]
    return reward_threshold, reward_description
