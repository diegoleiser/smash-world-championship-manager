"""Achievements: lasting positive awards per player, computed from the archive."""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

from smash_stats.database import (
    DEFAULT_DB_PATH,
    KNOWN_PARTICIPANTS_SQL,
    connect_db,
)
from smash_stats.elo_history import (
    calculate_elo_history,
    get_elo_ranking_timeline,
)
from smash_stats.elo_rules import ELO_K_FACTOR, ELO_START_RATING
from smash_stats.upsets import find_upsets
from text_format import format_elo_change, format_ordinal
from tournament.archived_bracket import build_archived_bracket_matches


RARE_MAXIMUM_HOLDERS = 2
GROUP_STAGES = {"group", "group_stage"}
PODIUM_PLACE = 3
PODIUM_STREAK_LENGTH = 3
PERFECT_GROUP_MINIMUM_SETS = 3
CURSE_MINIMUM_LOSSES = 3
SEED_BUSTER_MINIMUM_GAP = 4
TIER_NAMES = ("Bronze", "Silver", "Gold")

ACHIEVEMENT_GROUPS = (
    ("sets", "Sets"),
    ("championships", "Championships"),
    ("bracket", "Bracket"),
    ("elo", "Elo"),
    ("career", "Career"),
)

# Catalogue in display order. A tiered achievement unlocks each tier once at
# its threshold; a repeatable one counts every occurrence; all others unlock
# once. ``{threshold}`` in a description is filled in per tier.
ACHIEVEMENTS: tuple[dict[str, Any], ...] = (
    {"key": "top_three_scalp", "group": "sets", "title": "Top 3 Scalp",
     "description": "Beat a player who was in the Elo top 3 after the previous tournament."},
    {"key": "curse_breaker", "group": "sets", "title": "Curse Breaker",
     "description": "Beat an opponent after losing at least 3 rated Sets in a row to them.",
     "repeatable": True},
    {"key": "seed_buster", "group": "sets", "title": "Seed Buster",
     "description": "Beat a player seeded at least 4 places higher at the same tournament.",
     "repeatable": True},
    {"key": "game_off_the_champion", "group": "sets", "title": "Game off the Champion",
     "description": "Won a game against the eventual champion of the tournament."},
    {"key": "first_title", "group": "championships", "title": "First Title",
     "description": "Won a World Championship for the first time."},
    {"key": "title_defense", "group": "championships", "title": "Title Defense",
     "description": "Won the World Championship again right after winning it.",
     "repeatable": True},
    {"key": "three_peat", "group": "championships", "title": "Three-Peat",
     "description": "Won three World Championships in a row."},
    {"key": "first_final", "group": "championships", "title": "First Final",
     "description": "Finished in the top 2 for the first time."},
    {"key": "first_podium", "group": "championships", "title": "First Podium",
     "description": "Finished in the top 3 for the first time."},
    {"key": "flawless_champion", "group": "championships", "title": "Flawless Champion",
     "description": "Won a World Championship without losing a rated Set.",
     "repeatable": True},
    {"key": "podium_streak", "group": "championships", "title": "Podium Streak",
     "description": "Finished in the top 3 at three World Championships in a row."},
    {"key": "underdog_podium", "group": "championships", "title": "Underdog Podium",
     "description": "Finished in the top 3 after being seeded in the bottom half.",
     "repeatable": True},
    {"key": "perfect_group_stage", "group": "championships", "title": "Perfect Group Stage",
     "description": "Won every rated Set of a Group Stage (at least 3).",
     "repeatable": True},
    {"key": "losers_run", "group": "bracket", "title": "Losers Run",
     "description": "Reached the Grand Final from the Losers Bracket.",
     "repeatable": True},
    {"key": "comeback_champion", "group": "bracket", "title": "Comeback Champion",
     "description": "Won a World Championship from the Losers Bracket.",
     "repeatable": True},
    {"key": "giant_killer", "group": "elo", "title": "Giant Killer",
     "description": "Won a rated Set against a player rated at least 150 Elo higher.",
     "repeatable": True},
    {"key": "elo_rank_one", "group": "elo", "title": "Elo #1",
     "description": "Led the Elo ranking after a tournament for the first time."},
    {"key": "elo_top_three", "group": "elo", "title": "Elo Top 3",
     "description": "Reached the Elo top 3 after a tournament for the first time."},
    {"key": "elo_peak", "group": "elo", "title": "Elo Peak",
     "description": "Reached an Elo rating of {threshold} after a rated Set.",
     "tiers": ((1100, "Elo 1100"), (1150, "Elo 1150"), (1200, "Elo 1200"))},
    {"key": "breakthrough", "group": "career", "title": "Breakthrough",
     "description": "Finished better than ever before (not at the debut).",
     "repeatable": True},
    {"key": "appearances", "group": "career", "title": "Appearances",
     "description": "Played {threshold} World Championships.",
     "tiers": ((3, "Regular"), (5, "Mainstay"), (10, "Veteran"))},
    {"key": "set_wins", "group": "career", "title": "Set Wins",
     "description": "Won {threshold} rated Sets (walkovers do not count).",
     "tiers": ((25, "25 Set Wins"), (50, "50 Set Wins"), (100, "100 Set Wins"))},
)

ACHIEVEMENT_CATALOGUE: dict[str, dict[str, Any]] = {
    achievement["key"]: achievement for achievement in ACHIEVEMENTS
}
_CATALOGUE_ORDER = {
    achievement["key"]: index for index, achievement in enumerate(ACHIEVEMENTS)
}


def _chronological(tournaments: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Orders tournaments by date, then number; undated ones last."""

    return sorted(
        tournaments,
        key=lambda tournament: (
            not tournament.get("tournament_date"),
            tournament.get("tournament_date") or "",
            int(tournament["tournament_number"]),
        ),
    )


def tier_title(key: str, tier: int | None) -> str:
    """Returns the title of an achievement, or of one of its tiers."""

    achievement = ACHIEVEMENT_CATALOGUE[key]
    if tier is None:
        return str(achievement["title"])
    return str(achievement["tiers"][tier - 1][1])


def tier_description(key: str, tier: int | None) -> str:
    """Returns the description, with the tier threshold filled in."""

    achievement = ACHIEVEMENT_CATALOGUE[key]
    if tier is None:
        return str(achievement["description"])
    threshold = achievement["tiers"][tier - 1][0]
    return str(achievement["description"]).format(threshold=threshold)


def losers_side_finalist(bracket_matches: list[dict[str, Any]]) -> str | None:
    """
    Returns the Grand Final player who came from the Losers Bracket.

    ``bracket_matches`` is the output of ``build_archived_bracket_matches``.
    The Losers Final winner is that player; without a Losers Final, it is the
    Grand Final player who did not win the Winners Final. ``None`` when the
    bracket has no Grand Final or the side cannot be told.
    """

    by_type = {match["match_type"]: match for match in bracket_matches}
    grand_final = by_type.get("grand_final")
    if grand_final is None:
        return None

    finalists = {
        str(player_id)
        for player_id in (grand_final["player_1_id"], grand_final["player_2_id"])
        if player_id is not None
    }
    losers_final = by_type.get("losers_final")
    if losers_final is not None and losers_final["winner_id"] is not None:
        winner_id = str(losers_final["winner_id"])
        return winner_id if winner_id in finalists else None

    winners_final = by_type.get("winners_final")
    if winners_final is not None and winners_final["winner_id"] is not None:
        others = finalists - {str(winners_final["winner_id"])}
        if len(others) == 1 and len(finalists) == 2:
            return others.pop()
    return None


def build_achievements(
    *,
    players: dict[str, dict[str, Any]],
    tournaments: list[dict[str, Any]],
    participants: list[dict[str, Any]],
    history: list[dict[str, Any]],
    timeline: list[dict[str, Any]],
    losers_finalists: dict[int, str] | None = None,
) -> list[dict[str, Any]]:
    """
    Builds every achievement unlock from already loaded archive data.

    ``players`` maps player IDs to ``{"player": name}``. ``tournaments`` have
    ``tournament_number``, ``tournament_date`` and ``winner_id``;
    ``participants`` have ``tournament_number``, ``player_id``,
    ``placement`` and optionally ``seed`` and ``recorded`` (0 for a champion
    known only from the tournament, see ``KNOWN_PARTICIPANTS_SQL``).
    ``history`` is the chronological output of ``calculate_elo_history``
    (rated Sets only, no walkovers) and ``timeline`` that of
    ``get_elo_ranking_timeline`` over all players.
    ``losers_finalists`` maps a tournament number to the Grand Final player
    from the Losers Bracket.

    Each unlock has the catalogue ``key``, ``tier`` (1-based, or ``None``) and
    ``occurrence`` (the n-th time for repeatable achievements, else 1), plus
    player, tournament, date and ``detail``. The result is chronological.
    """

    losers_finalists = losers_finalists or {}
    ordered_tournaments = _chronological(tournaments)
    position = {
        int(tournament["tournament_number"]): index
        for index, tournament in enumerate(ordered_tournaments)
    }
    dates = {
        int(tournament["tournament_number"]): tournament.get("tournament_date")
        for tournament in ordered_tournaments
    }

    unlocks: list[dict[str, Any]] = []
    seen: set[tuple[str, str, int | None]] = set()
    occurrences: Counter[tuple[str, str]] = Counter()

    def unlock(
        key: str,
        player_id: str,
        tournament_number: int,
        detail: str = "",
        *,
        tier: int | None = None,
        sequence: int = 0,
    ) -> None:
        if player_id not in players:
            return
        if ACHIEVEMENT_CATALOGUE[key].get("repeatable"):
            occurrences[(key, player_id)] += 1
            occurrence = occurrences[(key, player_id)]
        elif (key, player_id, tier) in seen:
            return
        else:
            occurrence = 1
        seen.add((key, player_id, tier))
        achievement = ACHIEVEMENT_CATALOGUE[key]
        unlocks.append(
            {
                "key": key,
                "group": achievement["group"],
                "title": tier_title(key, tier),
                "description": tier_description(key, tier),
                "tier": tier,
                "occurrence": occurrence,
                "player_id": player_id,
                "player": str(players[player_id]["player"]),
                "tournament_number": int(tournament_number),
                "tournament_date": dates.get(int(tournament_number)),
                "detail": detail,
                "_sequence": sequence,
            }
        )

    # Championships, placements and bracket runs, tournament by tournament.
    placements: dict[int, dict[str, int | None]] = defaultdict(dict)
    seeds: dict[int, dict[str, int]] = defaultdict(dict)
    # Tournaments with recorded participants; elsewhere only the champion is known.
    recorded_field: set[int] = set()
    for participant in participants:
        number = int(participant["tournament_number"])
        player_id = str(participant["player_id"])
        placement = participant["placement"]
        placements[number][player_id] = int(placement) if placement is not None else None
        if participant.get("seed") is not None:
            seeds[number][player_id] = int(participant["seed"])
        if participant.get("recorded", 1):
            recorded_field.add(number)

    # Rated Set records per tournament: any loss, and the Group Stage record.
    lost_at: set[tuple[int, str]] = set()
    group_records: dict[tuple[int, str], list[int]] = defaultdict(lambda: [0, 0])
    for event in history:
        number = int(event["tournament_number"])
        lost_at.add((number, str(event["loser_id"])))
        if str(event.get("stage") or "") in GROUP_STAGES:
            group_records[(number, str(event["winner_id"]))][0] += 1
            group_records[(number, str(event["loser_id"]))][1] += 1

    appearances: Counter[str] = Counter()
    appearance_tiers = ACHIEVEMENT_CATALOGUE["appearances"]["tiers"]
    title_streak: tuple[str | None, int] = (None, 0)
    podium_runs: Counter[str] = Counter()
    best_placement: dict[str, int] = {}
    for tournament in ordered_tournaments:
        number = int(tournament["tournament_number"])
        winner_id = (
            str(tournament["winner_id"])
            if tournament["winner_id"] is not None
            else None
        )

        if winner_id is not None:
            unlock("first_title", winner_id, number)
            holder, length = title_streak
            length = length + 1 if holder == winner_id else 1
            title_streak = (winner_id, length)
            if length >= 2:
                unlock("title_defense", winner_id, number)
            if length == 3:
                unlock("three_peat", winner_id, number)
            if (number, winner_id) not in lost_at and any(
                int(event["tournament_number"]) == number for event in history
            ):
                unlock("flawless_champion", winner_id, number)
        else:
            title_streak = (None, 0)

        field = placements[number]
        if number in recorded_field:
            # Only a tournament with recorded participants breaks a run; where
            # just the champion is known, nobody else's result is assumed.
            for player_id in list(podium_runs):
                if (field.get(player_id) or PODIUM_PLACE + 1) > PODIUM_PLACE:
                    podium_runs[player_id] = 0

        for player_id, placement in sorted(field.items()):
            appearances[player_id] += 1
            for tier, (threshold, _title) in enumerate(appearance_tiers, start=1):
                if appearances[player_id] == threshold:
                    unlock("appearances", player_id, number, tier=tier)
            if placement is not None:
                previous_best = best_placement.get(player_id)
                if previous_best is not None and placement < previous_best:
                    unlock(
                        "breakthrough",
                        player_id,
                        number,
                        f"Finished {format_ordinal(placement)} "
                        f"(previous best {format_ordinal(previous_best)})",
                    )
                best_placement[player_id] = min(placement, previous_best or placement)
            if placement is not None and placement <= 2:
                unlock("first_final", player_id, number)
            if placement is not None and placement <= PODIUM_PLACE:
                unlock("first_podium", player_id, number)
                podium_runs[player_id] += 1
                if podium_runs[player_id] == PODIUM_STREAK_LENGTH:
                    unlock("podium_streak", player_id, number)
                seed = seeds[number].get(player_id)
                if seed is not None and seed > len(field) / 2:
                    unlock(
                        "underdog_podium",
                        player_id,
                        number,
                        f"Seed {seed} of {len(field)} · finished {format_ordinal(placement)}",
                    )
            wins_and_losses = group_records.get((number, player_id))
            if (
                wins_and_losses is not None
                and wins_and_losses[1] == 0
                and wins_and_losses[0] >= PERFECT_GROUP_MINIMUM_SETS
            ):
                unlock(
                    "perfect_group_stage",
                    player_id,
                    number,
                    f"{wins_and_losses[0]}–0 in Sets",
                )

        losers_finalist = losers_finalists.get(number)
        if losers_finalist is not None:
            unlock("losers_run", losers_finalist, number)
            if losers_finalist == winner_id:
                unlock("comeback_champion", losers_finalist, number)

    # Elo top 3 after the previous tournament, for Top 3 Scalp.
    ranks_after: dict[int, dict[str, int]] = defaultdict(dict)
    for snapshot in timeline:
        ranks_after[int(snapshot["tournament_number"])][
            str(snapshot["player_id"])
        ] = int(snapshot["rank"])
    previous_ranks: dict[int, dict[str, int]] = {}
    last_ranks: dict[str, int] = {}
    for tournament in ordered_tournaments:
        number = int(tournament["tournament_number"])
        previous_ranks[number] = last_ranks
        if ranks_after.get(number):
            last_ranks = ranks_after[number]

    # Rated Sets in chronological order.
    wins: Counter[str] = Counter()
    win_tiers = ACHIEVEMENT_CATALOGUE["set_wins"]["tiers"]
    elo_tiers = ACHIEVEMENT_CATALOGUE["elo_peak"]["tiers"]
    # Consecutive rated Set losses of the first player against the second.
    losing_runs: Counter[tuple[str, str]] = Counter()
    champions = {
        int(tournament["tournament_number"]): str(tournament["winner_id"])
        for tournament in ordered_tournaments
        if tournament["winner_id"] is not None
    }
    for event in history:
        winner_id = str(event["winner_id"])
        loser_id = str(event["loser_id"])
        number = int(event["tournament_number"])
        sequence = int(event["sequence"])
        versus = f"vs {event['loser']}"

        wins[winner_id] += 1
        if losing_runs[(winner_id, loser_id)] >= CURSE_MINIMUM_LOSSES:
            unlock(
                "curse_breaker",
                winner_id,
                number,
                f"{versus} after {losing_runs[(winner_id, loser_id)]} losses in a row",
                sequence=sequence,
            )
        losing_runs[(winner_id, loser_id)] = 0
        losing_runs[(loser_id, winner_id)] += 1

        winner_seed = seeds[number].get(winner_id)
        loser_seed = seeds[number].get(loser_id)
        if (
            winner_seed is not None
            and loser_seed is not None
            and winner_seed - loser_seed >= SEED_BUSTER_MINIMUM_GAP
        ):
            unlock(
                "seed_buster",
                winner_id,
                number,
                f"{versus} (Seed {winner_seed} vs {loser_seed})",
                sequence=sequence,
            )

        if (
            winner_id == champions.get(number)
            and event.get("score_known")
            and (event.get("loser_score") or 0) >= 1
        ):
            unlock(
                "game_off_the_champion",
                loser_id,
                number,
                f"{event['loser_score']}–{event['winner_score']} vs {event['winner']}",
                sequence=sequence,
            )

        for tier, (threshold, _title) in enumerate(elo_tiers, start=1):
            if float(event["winner_rating_after"]) >= threshold:
                unlock("elo_peak", winner_id, number, tier=tier, sequence=sequence)
        loser_rank = previous_ranks.get(number, {}).get(loser_id)
        if loser_rank is not None and loser_rank <= 3:
            unlock(
                "top_three_scalp",
                winner_id,
                number,
                f"{versus} (Elo #{loser_rank})",
                sequence=sequence,
            )
        for tier, (threshold, _title) in enumerate(win_tiers, start=1):
            if wins[winner_id] == threshold:
                unlock("set_wins", winner_id, number, tier=tier, sequence=sequence)

    for upset in sorted(find_upsets(history), key=lambda upset: upset["sequence"]):
        unlock(
            "giant_killer",
            str(upset["winner_id"]),
            int(upset["tournament_number"]),
            f"vs {upset['loser']} · {format_elo_change(upset['elo_gap'])} Elo",
            sequence=int(upset["sequence"]),
        )

    # Elo ranking after each tournament.
    for snapshot in timeline:
        rank = int(snapshot["rank"])
        player_id = str(snapshot["player_id"])
        number = int(snapshot["tournament_number"])
        if rank == 1:
            unlock("elo_rank_one", player_id, number)
        if rank <= 3:
            unlock("elo_top_three", player_id, number)

    unlocks.sort(
        key=lambda entry: (
            position.get(entry["tournament_number"], len(position)),
            entry["_sequence"],
            _CATALOGUE_ORDER[entry["key"]],
            entry["tier"] or 0,
            entry["player"].casefold(),
        )
    )
    for entry in unlocks:
        del entry["_sequence"]
    return unlocks


def summarize_achievements(
    unlocks: list[dict[str, Any]],
    *,
    rare_maximum_holders: int = RARE_MAXIMUM_HOLDERS,
) -> list[dict[str, Any]]:
    """
    Condenses unlocks into one badge per player and achievement.

    A badge carries the highest tier reached, the ``count`` of occurrences,
    the ``first`` and ``latest`` unlock, and ``holders``: how many players
    hold this achievement (at this tier). ``rare`` marks badges held by at
    most ``rare_maximum_holders`` players. Badges keep catalogue order.
    """

    by_badge: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for entry in unlocks:
        by_badge[(entry["player_id"], entry["key"])].append(entry)

    badges: list[dict[str, Any]] = []
    for (player_id, key), entries in by_badge.items():
        top_tier = max((entry["tier"] or 0 for entry in entries), default=0) or None
        latest = max(
            (entry for entry in entries if entry["tier"] == top_tier),
            key=lambda entry: entry["occurrence"],
        )
        badges.append(
            {
                "key": key,
                "group": entries[0]["group"],
                "title": tier_title(key, top_tier),
                "description": tier_description(key, top_tier),
                "tier": top_tier,
                "tier_name": TIER_NAMES[top_tier - 1] if top_tier else None,
                "count": max(entry["occurrence"] for entry in entries),
                "player_id": player_id,
                "player": entries[0]["player"],
                "first": entries[0],
                "latest": latest,
            }
        )

    holders: Counter[tuple[str, int | None]] = Counter(
        (badge["key"], badge["tier"]) for badge in badges
    )
    for badge in badges:
        # A higher tier also counts as holding every lower tier.
        badge["holders"] = sum(
            count
            for (key, tier), count in holders.items()
            if key == badge["key"] and (tier or 0) >= (badge["tier"] or 0)
        )
        badge["rare"] = badge["holders"] <= rare_maximum_holders

    badges.sort(
        key=lambda badge: (
            _CATALOGUE_ORDER[badge["key"]],
            badge["player"].casefold(),
        )
    )
    return badges


def _load_losers_finalists(connection: Any) -> dict[int, str]:
    rows = connection.execute(
        """
        SELECT
            t.tournament_number,
            m.match_id,
            m.stage,
            m.round_label,
            m.challonge_identifier,
            m.challonge_round,
            m.suggested_play_order,
            m.player_1_id,
            p1.display_name AS player_1,
            m.player_2_id,
            p2.display_name AS player_2,
            m.winner_id,
            winner.display_name AS winner,
            m.player_1_score,
            m.player_2_score,
            m.score_known,
            m.walkover
        FROM matches AS m
        JOIN tournaments AS t ON t.tournament_id = m.tournament_id
        LEFT JOIN players AS p1 ON p1.player_id = m.player_1_id
        LEFT JOIN players AS p2 ON p2.player_id = m.player_2_id
        LEFT JOIN players AS winner ON winner.player_id = m.winner_id
        WHERE m.stage IN ('bracket', 'knockout')
        """
    ).fetchall()

    matches_by_tournament: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        matches_by_tournament[int(row["tournament_number"])].append(dict(row))

    finalists: dict[int, str] = {}
    for number, matches in matches_by_tournament.items():
        finalist = losers_side_finalist(build_archived_bracket_matches(matches))
        if finalist is not None:
            finalists[number] = finalist
    return finalists


def get_achievements(
    db_path: str | Path = DEFAULT_DB_PATH,
    *,
    start_rating: float = ELO_START_RATING,
    k_factor: float = ELO_K_FACTOR,
) -> list[dict[str, Any]]:
    """
    Returns every achievement unlock of the archive, oldest first.

    Achievements belong to the player, so inactive players keep theirs and
    the Elo ranking achievements use the ranking over all players.
    """

    with connect_db(db_path) as connection:
        player_rows = connection.execute(
            "SELECT player_id, display_name FROM players"
        ).fetchall()
        tournament_rows = connection.execute(
            "SELECT tournament_number, tournament_date, winner_id FROM tournaments"
        ).fetchall()
        participant_rows = connection.execute(
            """
            SELECT t.tournament_number, tp.player_id, tp.placement, tp.seed,
                tp.recorded
            FROM (""" + KNOWN_PARTICIPANTS_SQL + """) AS tp
            JOIN tournaments AS t
              ON t.tournament_id = tp.tournament_id
            """
        ).fetchall()
        losers_finalists = _load_losers_finalists(connection)

    return build_achievements(
        players={
            str(row["player_id"]): {"player": row["display_name"]}
            for row in player_rows
        },
        tournaments=[dict(row) for row in tournament_rows],
        participants=[dict(row) for row in participant_rows],
        history=calculate_elo_history(
            db_path,
            start_rating=start_rating,
            k_factor=k_factor,
        ),
        timeline=get_elo_ranking_timeline(
            db_path,
            active_only=False,
            start_rating=start_rating,
            k_factor=k_factor,
        ),
        losers_finalists=losers_finalists,
    )
