"""Hall of Fame: positive all-time records with their top three holders."""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

from smash_stats.database import DEFAULT_DB_PATH, connect_db
from smash_stats.elo_history import (
    calculate_elo_history,
    get_elo_ranking_timeline,
)
from smash_stats.elo_rules import ELO_K_FACTOR, ELO_START_RATING


HALL_OF_FAME_TOP_N = 3
WIN_RATE_MINIMUM_SETS = 5

HALL_OF_FAME_GROUPS = (
    ("championships", "Championships"),
    ("performance", "Performance"),
    ("elo_ranking", "Elo Ranking"),
    ("rivalries", "Rivalries"),
)


def _tournament_label(tournament_number: int) -> str:
    return f"WC {int(tournament_number):02d}"


def _span_label(first: int, last: int) -> str:
    if first == last:
        return _tournament_label(first)
    return f"{_tournament_label(first)}–{_tournament_label(last)}"


def rank_candidates(
    candidates: Iterable[dict[str, Any]],
    *,
    top_n: int = HALL_OF_FAME_TOP_N,
) -> list[dict[str, Any]]:
    """
    Returns candidates with a positive value, ranked by value.

    Equal values share a rank (1, 1, 3). Every candidate whose rank is within
    ``top_n`` is kept, so a tie at the cut-off shows all tied holders. Ties
    are listed alphabetically by their sort name.
    """

    ordered = sorted(
        (candidate for candidate in candidates if candidate["value"] > 0),
        key=lambda candidate: (
            -candidate["value"],
            candidate["sort_name"].casefold(),
        ),
    )

    ranked: list[dict[str, Any]] = []
    previous_value = None
    rank = 0
    for position, candidate in enumerate(ordered, start=1):
        if candidate["value"] != previous_value:
            rank = position
            previous_value = candidate["value"]
        if rank > top_n:
            break
        entry = {key: value for key, value in candidate.items() if key != "sort_name"}
        entry["rank"] = rank
        ranked.append(entry)
    return ranked


def build_hall_of_fame(
    *,
    players: dict[str, dict[str, Any]],
    tournaments: list[dict[str, Any]],
    participants: list[dict[str, Any]],
    history: list[dict[str, Any]],
    timeline: list[dict[str, Any]],
    top_n: int = HALL_OF_FAME_TOP_N,
    minimum_win_rate_sets: int = WIN_RATE_MINIMUM_SETS,
) -> list[dict[str, Any]]:
    """
    Builds the Hall of Fame records from already loaded archive data.

    ``players`` maps eligible player IDs to ``{"player": name}``; records only
    rank these players, while the Elo history keeps all rated Sets.
    ``history`` is the chronological output of ``calculate_elo_history`` and
    ``timeline`` that of ``get_elo_ranking_timeline``. Each record has a
    ``key``, ``group``, ``title``, ``unit`` and ranked ``entries``; every entry
    lists its ``players`` (two for rivalries), a ``value`` and a ``detail``.
    """

    def name(player_id: str) -> str:
        return str(players[player_id]["player"])

    def single(player_id: str, value: Any, detail: str = "") -> dict[str, Any]:
        return {
            "players": [{"player_id": player_id, "player": name(player_id)}],
            "value": value,
            "detail": detail,
            "sort_name": name(player_id),
        }

    def pair(
        first_id: str,
        second_id: str,
        value: Any,
        detail: str = "",
    ) -> dict[str, Any]:
        return {
            "players": [
                {"player_id": first_id, "player": name(first_id)},
                {"player_id": second_id, "player": name(second_id)},
            ],
            "value": value,
            "detail": detail,
            "sort_name": f"{name(first_id)} {name(second_id)}",
        }

    def record(
        key: str,
        group: str,
        title: str,
        unit: str,
        candidates: Iterable[dict[str, Any]],
    ) -> dict[str, Any]:
        return {
            "key": key,
            "group": group,
            "title": title,
            "unit": unit,
            "entries": rank_candidates(candidates, top_n=top_n),
        }

    # Championships: titles from the tournament winner, finals and podiums
    # from the archived placements.
    titles: Counter[str] = Counter(
        str(tournament["winner_id"])
        for tournament in tournaments
        if tournament["winner_id"] is not None
        and str(tournament["winner_id"]) in players
    )
    finals: Counter[str] = Counter()
    podiums: Counter[str] = Counter()
    appearances: Counter[str] = Counter()
    for participant in participants:
        player_id = str(participant["player_id"])
        if player_id not in players:
            continue
        appearances[player_id] += 1
        placement = participant["placement"]
        if placement is not None and int(placement) <= 2:
            finals[player_id] += 1
        if placement is not None and int(placement) <= 3:
            podiums[player_id] += 1

    # Performance and rivalries from the rated Sets in chronological order.
    wins: Counter[str] = Counter()
    sets_played: Counter[str] = Counter()
    peak_elo: dict[str, tuple[float, int]] = {}
    best_gain: dict[str, tuple[float, str, int]] = {}
    win_streaks: dict[str, tuple[int, int, int]] = {}
    current_streak: dict[str, tuple[int, int]] = {}
    pair_sets: Counter[tuple[str, str]] = Counter()
    pair_wins: Counter[tuple[str, str]] = Counter()
    h2h_streaks: dict[tuple[str, str], tuple[int, int, int]] = {}
    current_h2h: dict[tuple[str, str], tuple[str, int, int]] = {}

    for event in history:
        winner_id = str(event["winner_id"])
        loser_id = str(event["loser_id"])
        tournament_number = int(event["tournament_number"])

        for player_id, won, after in (
            (winner_id, True, float(event["winner_rating_after"])),
            (loser_id, False, float(event["loser_rating_after"])),
        ):
            sets_played[player_id] += 1
            if player_id not in peak_elo or after > peak_elo[player_id][0]:
                peak_elo[player_id] = (after, tournament_number)

            if won:
                wins[player_id] += 1
                length, start = current_streak.get(player_id, (0, tournament_number))
                if length == 0:
                    start = tournament_number
                length += 1
                current_streak[player_id] = (length, start)
                if length > win_streaks.get(player_id, (0, 0, 0))[0]:
                    win_streaks[player_id] = (length, start, tournament_number)
            else:
                current_streak[player_id] = (0, tournament_number)

        gain = float(event["rating_change"])
        if winner_id not in best_gain or gain > best_gain[winner_id][0]:
            best_gain[winner_id] = (gain, loser_id, tournament_number)

        pair_key = tuple(sorted((winner_id, loser_id)))
        pair_sets[pair_key] += 1
        pair_wins[(winner_id, loser_id)] += 1

        streak_holder, length, start = current_h2h.get(
            pair_key,
            (winner_id, 0, tournament_number),
        )
        if streak_holder != winner_id or length == 0:
            streak_holder, length, start = winner_id, 0, tournament_number
        length += 1
        current_h2h[pair_key] = (streak_holder, length, start)
        streak_key = (winner_id, loser_id)
        if length > h2h_streaks.get(streak_key, (0, 0, 0))[0]:
            h2h_streaks[streak_key] = (length, start, tournament_number)

    win_rate_candidates = []
    for player_id in players:
        played = sets_played[player_id]
        if played >= minimum_win_rate_sets:
            win_rate_candidates.append(
                single(
                    player_id,
                    round(wins[player_id] / played * 100, 1),
                    f"{wins[player_id]}–{played - wins[player_id]} in Sets",
                )
            )

    # Elo ranking after each tournament among the visible players.
    elo_rank_one: Counter[str] = Counter()
    elo_top_three: Counter[str] = Counter()
    by_tournament: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for snapshot in timeline:
        player_id = str(snapshot["player_id"])
        if player_id not in players:
            continue
        by_tournament[int(snapshot["tournament_number"])].append(snapshot)
        if int(snapshot["rank"]) == 1:
            elo_rank_one[player_id] += 1
        if int(snapshot["rank"]) <= 3:
            elo_top_three[player_id] += 1

    best_lead: dict[str, tuple[float, str, int]] = {}
    for tournament_number, snapshots in by_tournament.items():
        ordered = sorted(snapshots, key=lambda snapshot: int(snapshot["rank"]))
        if len(ordered) < 2:
            continue
        leader_id = str(ordered[0]["player_id"])
        lead = round(float(ordered[0]["elo"]) - float(ordered[1]["elo"]), 1)
        if leader_id not in best_lead or lead > best_lead[leader_id][0]:
            best_lead[leader_id] = (
                lead,
                str(ordered[1]["player_id"]),
                tournament_number,
            )

    def eligible(player_ids: Iterable[str]) -> bool:
        return all(player_id in players for player_id in player_ids)

    return [
        record(
            "most_titles",
            "championships",
            "Most Titles",
            "titles",
            (single(player_id, count) for player_id, count in titles.items()),
        ),
        record(
            "most_finals",
            "championships",
            "Most Finals",
            "finals",
            (single(player_id, count) for player_id, count in finals.items()),
        ),
        record(
            "most_podiums",
            "championships",
            "Most Podiums",
            "podiums",
            (single(player_id, count) for player_id, count in podiums.items()),
        ),
        record(
            "most_set_wins",
            "performance",
            "Most Set Wins",
            "wins",
            (
                single(player_id, count)
                for player_id, count in wins.items()
                if eligible([player_id])
            ),
        ),
        record(
            "most_sets_played",
            "performance",
            "Most Sets Played",
            "Sets",
            (
                single(player_id, count)
                for player_id, count in sets_played.items()
                if eligible([player_id])
            ),
        ),
        record(
            "most_appearances",
            "performance",
            "Most Appearances",
            "appearances",
            (single(player_id, count) for player_id, count in appearances.items()),
        ),
        record(
            "highest_win_rate",
            "performance",
            f"Highest Win Rate (min. {minimum_win_rate_sets} Sets)",
            "%",
            win_rate_candidates,
        ),
        record(
            "highest_peak_elo",
            "performance",
            "Highest Peak Elo",
            "Elo",
            (
                single(player_id, round(elo, 1), _tournament_label(number))
                for player_id, (elo, number) in peak_elo.items()
                if eligible([player_id])
            ),
        ),
        record(
            "longest_win_streak",
            "performance",
            "Longest Win Streak",
            "Set wins",
            (
                single(player_id, length, _span_label(start, end))
                for player_id, (length, start, end) in win_streaks.items()
                if eligible([player_id])
            ),
        ),
        record(
            "biggest_set_elo_gain",
            "performance",
            "Biggest Elo Gain in One Set",
            "Elo",
            (
                single(
                    player_id,
                    round(gain, 1),
                    f"vs {name(opponent_id)} · {_tournament_label(number)}"
                    if opponent_id in players
                    else _tournament_label(number),
                )
                for player_id, (gain, opponent_id, number) in best_gain.items()
                if eligible([player_id])
            ),
        ),
        record(
            "most_elo_rank_one",
            "elo_ranking",
            "Most Tournaments as Elo #1",
            "tournaments",
            (single(player_id, count) for player_id, count in elo_rank_one.items()),
        ),
        record(
            "most_elo_top_three",
            "elo_ranking",
            "Most Tournaments in Elo Top 3",
            "tournaments",
            (single(player_id, count) for player_id, count in elo_top_three.items()),
        ),
        record(
            "biggest_elo_lead",
            "elo_ranking",
            "Biggest Elo Lead at #1",
            "Elo",
            (
                single(
                    player_id,
                    lead,
                    f"ahead of {name(runner_up_id)} · {_tournament_label(number)}",
                )
                for player_id, (lead, runner_up_id, number) in best_lead.items()
            ),
        ),
        record(
            "most_played_matchup",
            "rivalries",
            "Most Played Matchup",
            "Sets",
            (
                pair(
                    first_id,
                    second_id,
                    count,
                    f"{pair_wins[(first_id, second_id)]}:"
                    f"{pair_wins[(second_id, first_id)]}",
                )
                for (first_id, second_id), count in pair_sets.items()
                if eligible([first_id, second_id])
            ),
        ),
        record(
            "longest_h2h_streak",
            "rivalries",
            "Longest Head-to-Head Win Streak",
            "Set wins in a row",
            (
                pair(winner_id, loser_id, length, _span_label(start, end))
                for (winner_id, loser_id), (length, start, end) in h2h_streaks.items()
                if eligible([winner_id, loser_id])
            ),
        ),
    ]


def get_hall_of_fame(
    db_path: str | Path = DEFAULT_DB_PATH,
    *,
    active_only: bool = False,
    top_n: int = HALL_OF_FAME_TOP_N,
    start_rating: float = ELO_START_RATING,
    k_factor: float = ELO_K_FACTOR,
) -> list[dict[str, Any]]:
    """
    Returns the Hall of Fame records of the archive.

    Records cover all archived World Championship tournaments. Walkovers are
    not rated Sets and do not count. With ``active_only=True`` only active
    players can hold a record; Elo values still come from the full history.
    """

    with connect_db(db_path) as connection:
        player_rows = connection.execute(
            "SELECT player_id, display_name, active FROM players"
        ).fetchall()
        tournament_rows = connection.execute(
            "SELECT tournament_number, winner_id FROM tournaments"
        ).fetchall()
        participant_rows = connection.execute(
            """
            SELECT t.tournament_number, tp.player_id, tp.placement
            FROM tournament_participants AS tp
            JOIN tournaments AS t
              ON t.tournament_id = tp.tournament_id
            """
        ).fetchall()

    players = {
        str(row["player_id"]): {"player": row["display_name"]}
        for row in player_rows
        if not active_only or row["active"]
    }

    return build_hall_of_fame(
        players=players,
        tournaments=[dict(row) for row in tournament_rows],
        participants=[dict(row) for row in participant_rows],
        history=calculate_elo_history(
            db_path,
            start_rating=start_rating,
            k_factor=k_factor,
        ),
        timeline=get_elo_ranking_timeline(
            db_path,
            active_only=active_only,
            start_rating=start_rating,
            k_factor=k_factor,
        ),
        top_n=top_n,
    )
