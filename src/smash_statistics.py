"""Compatibility facade for the statistics services in ``smash_stats``.

Dashboard pages, narratives and tests import from here; the calculations live
in the focused ``smash_stats`` modules.
"""

from __future__ import annotations

from smash_stats.database import (
    DEFAULT_DB_PATH,
    KNOWN_PARTICIPANTS_SQL,
    PlayerNotFoundError,
    connect_db,
    resolve_player,
)
from smash_stats.elo_rules import (
    ELO_K_FACTOR,
    ELO_MAX_MARGIN_MULTIPLIER,
    ELO_START_RATING,
    calculate_elo_change,
    calculate_expected_score,
    calculate_margin_multiplier,
)
from smash_stats.elo_history import (
    calculate_elo_history,
    get_elo_ranking,
    get_elo_ranking_timeline,
    get_player_elo_history,
    get_player_elo_summary,
    get_player_elo_timeline,
)
from smash_stats.achievements import (
    ACHIEVEMENT_CATALOGUE,
    ACHIEVEMENT_GROUPS,
    get_achievements,
    summarize_achievements,
)
from smash_stats.hall_of_fame import HALL_OF_FAME_GROUPS, get_hall_of_fame
from smash_stats.upsets import (
    UPSET_MINIMUM_ELO_GAP,
    UPSET_MINIMUM_PRIOR_SETS,
    find_upsets,
    get_upsets,
)
from smash_stats.head_to_head import get_head_to_head
from smash_stats.player_stats import (
    get_player_history,
    get_player_stats,
)
