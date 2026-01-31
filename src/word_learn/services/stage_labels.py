"""Stage labels for spaced repetition system."""

STAGE_LABELS = {
    0: "Unknown",
    1: "Just learned",
    2: "Learning",
    3: "Getting familiar",
    4: "Familiar",
    5: "Confident",
    6: "Well known",
}

MAX_LABELED_STAGE = 7
KNOW_BY_HEART_LABEL = "Know by heart"


def get_stage_label(stage: int) -> str:
    """Get human-readable label for a stage number.

    Args:
        stage: The stage number (0+)

    Returns:
        Human-readable stage label
    """
    if stage >= MAX_LABELED_STAGE:
        return KNOW_BY_HEART_LABEL
    return STAGE_LABELS.get(stage, KNOW_BY_HEART_LABEL)
