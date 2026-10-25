"""Evidence-based story candidates shared by profiles, recaps and outlooks."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from collections.abc import Sequence
from typing import Any

from smash_stats.database import connect_db


@dataclass(frozen=True)
class Story:
    priority: int
    theme: str
    text: str


def select_stories(stories: list[Story], limit: int = 3) -> list[str]:
    """Prefer significant evidence, retaining only one story per theme."""
    if limit <= 0:
        return []
    selected, themes = [], set()
    for story in sorted(stories, key=lambda item: (-item.priority, item.theme, item.text)):
        if story.theme not in themes:
            selected.append(story.text)
            themes.add(story.theme)
        if len(selected) >= limit:
            break
    return selected


def load_story_archive(db_path: str | Path) -> dict[str, Any]:
    """Read narrative evidence without persisting derived data."""
    with connect_db(db_path) as connection:
        events = [dict(row) for row in connection.execute(
            "SELECT t.tournament_id, t.tournament_number, t.tournament_date, t.winner_id, "
            "p.display_name AS winner FROM tournaments t "
            "LEFT JOIN players p ON p.player_id=t.winner_id "
            "ORDER BY t.tournament_date, t.tournament_number"
        )]
        appearances = [dict(row) for row in connection.execute(
            "SELECT tp.*, p.display_name AS player FROM tournament_participants tp "
            "JOIN players p USING(player_id)"
        )]
        matches = [dict(row) for row in connection.execute(
            "SELECT m.*, p1.display_name AS player_1, p2.display_name AS player_2, "
            "w.display_name AS winner FROM matches m "
            "JOIN tournaments t USING(tournament_id) "
            "JOIN players p1 ON p1.player_id=m.player_1_id "
            "JOIN players p2 ON p2.player_id=m.player_2_id "
            "JOIN players w ON w.player_id=m.winner_id "
            "WHERE COALESCE(m.walkover,0)=0 AND m.player_1_id!=m.player_2_id "
            "AND m.winner_id IN (m.player_1_id,m.player_2_id) "
            "ORDER BY t.tournament_date,t.tournament_number, "
            "m.completed_at IS NULL,m.completed_at, "
            "m.suggested_play_order IS NULL,m.suggested_play_order,m.match_id"
        )]
    return dict(events=events, appearances=appearances, matches=matches)


def _through(archive: dict[str, Any], number: int | None) -> dict[str, Any]:
    events = archive['events']
    if number is not None:
        index = next(i for i, row in enumerate(events) if row['tournament_number'] == number)
        events = events[:index + 1]
    ids = {row['tournament_id'] for row in events}
    return dict(events=events,
                appearances=[r for r in archive['appearances'] if r['tournament_id'] in ids],
                matches=[r for r in archive['matches'] if r['tournament_id'] in ids])


def _record(matches: list[dict[str, Any]], name: str) -> tuple[int, int]:
    own = [r for r in matches if name in (r['player_1'], r['player_2'])]
    wins = sum(r['winner'] == name for r in own)
    return wins, len(own) - wins


def _games(matches: list[dict[str, Any]], name: str) -> tuple[int, int] | None:
    if not matches or any(not r.get('score_known') or r.get('walkover') or
                          r.get('player_1_score') is None or r.get('player_2_score') is None
                          for r in matches):
        return None
    won = sum(r['player_1_score'] if r['player_1'] == name else r['player_2_score'] for r in matches)
    lost = sum(r['player_2_score'] if r['player_1'] == name else r['player_1_score'] for r in matches)
    return won, lost


def player_stories(archive: dict[str, Any], name: str, *,
                   ranking: Sequence[dict[str, Any]] = (),
                   timeline: Sequence[dict[str, Any]] = (),
                   through: int | None = None) -> list[Story]:
    """Find placement runs, opponent contrasts, debuts and recent trajectories."""
    data = _through(archive, through)
    events = data['events']
    by_id = {r['tournament_id']: i for i, r in enumerate(events)}
    own = sorted((r for r in data['appearances'] if r['player'] == name),
                 key=lambda r: by_id[r['tournament_id']])
    if not own:
        return []
    latest = own[-1]
    event = events[by_id[latest['tournament_id']]]
    label = f"WC {event['tournament_number']:02d}"
    matches = [r for r in data['matches'] if name in (r['player_1'], r['player_2'])]
    recent = [r for r in matches if r['tournament_id'] == latest['tournament_id']]
    stories = []
    runners = 0
    for row in reversed(own):
        if row.get('placement') != 2:
            break
        runners += 1
    titles = [r for r in events if r.get('winner') == name]
    if runners >= 3:
        text = f"{name} has finished runner-up at {runners} consecutive recorded appearances."
        if titles:
            text += f" The most recent title came at WC {titles[-1]['tournament_number']:02d}."
        stories.append(Story(100, 'placements', text))
    elif titles and event['tournament_id'] != titles[-1]['tournament_id']:
        since = [r for r in own if by_id[r['tournament_id']] > by_id[titles[-1]['tournament_id']]]
        if len(since) >= 4:
            stories.append(Story(65, 'placements', f"{name} has made {len(since)} recorded appearances "
                                 f"without another title since winning WC {titles[-1]['tournament_number']:02d}."))
    if len(own) == 1 and recent:
        w, l = _record(recent, name)
        place = latest.get('placement')
        field = sum(r['tournament_id'] == latest['tournament_id'] for r in data['appearances'])
        tied = sum(r["tournament_id"] == latest["tournament_id"] and r.get("placement") == place for r in data["appearances"]) > 1
        finish = f", finishing {'joint ' if tied else ''}#{place} in a field of {field}" if place else ''
        stories.append(Story(110, 'debut', f"{name} made a recorded World Championship debut at {label}{finish}, "
                             f"with a {w}–{l} set record. One event offers only an initial picture."))
    rank_by_name = {r['player']: r for r in ranking}
    rating = rank_by_name.get(name, {}).get('elo')
    for opponent in sorted({r['player_2'] if r['player_1'] == name else r['player_1'] for r in matches}):
        pair = [r for r in matches if opponent in (r['player_1'], r['player_2'])]
        w, l = _record(pair, name)
        other = rank_by_name.get(opponent, {}).get('elo')
        if rating is not None and other is not None and other - rating >= 100 and w > l and len(pair) >= 5:
            streak = 0
            for r in reversed(pair):
                if r['winner'] != name:
                    break
                streak += 1
            text = f"Despite a lower current Elo, {name} leads {opponent} {w}–{l} across their recorded meetings."
            if streak >= 3:
                text += f" {name} has also won their last {streak} sets."
            negative = []
            for rival in sorted({r['player_2'] if r['player_1'] == name else r['player_1'] for r in matches}):
                rival_rows = [r for r in matches if rival in (r['player_1'], r['player_2'])]
                rw, rl = _record(rival_rows, name)
                if len(rival_rows) >= 5 and rw / len(rival_rows) < .35:
                    negative.append((rw / len(rival_rows), -len(rival_rows), rival, rw, rl))
            if negative:
                _, _, rival, rw, rl = min(negative)
                text += f" In contrast, the record against {rival} is {rw}–{rl}."
            stories.append(Story(105, 'opponents', text))
    bracket = [r for r in recent if r.get('stage') in {'bracket', 'knockout'}]
    if len(own) == 1 and bracket:
        w, _ = _record(bracket, name)
        last = bracket[-1]
        games = _games([last], name)
        text = f"{name} recorded {w} bracket {'victory' if w == 1 else 'victories'} at {label}." if w else ''
        if last['winner'] != name and games and max(games) >= 2 and games[1] - games[0] == 1:
            opponent = last['winner']
            text = (
                f"The bracket run brought {w} {'victory' if w == 1 else 'victories'} before a "
                f"{games[0]}–{games[1]} deciding-game loss to {opponent}."
                if w else f"The run ended in a {games[0]}–{games[1]} deciding-game loss to {opponent}."
            )
        if text:
            stories.append(Story(95, 'debut_run', text.strip()))
    podium = {r['player'] for r in data['appearances']
              if r['tournament_id'] == latest['tournament_id'] and r.get('placement') in (1, 2, 3)}
    group_wins = {r['player_2'] if r['player_1'] == name else r['player_1']
                  for r in recent if r['winner'] == name and r.get('stage') in {'group', 'group_stage'}}
    beaten = sorted(podium & group_wins)
    if len(beaten) >= 2 and latest.get('placement') and latest['placement'] > 3:
        stories.append(Story(97, 'group_bracket', f"At {label}, {name} defeated "
                             f"{' and '.join(beaten)} in the Group Stage, both eventual podium finishers, "
                             f"but finished #{latest['placement']}."))

    own_start_losses = 0
    for row in recent:
        if row['winner'] == name:
            break
        own_start_losses += 1
    if event.get('winner') == name and own_start_losses >= 2 and all(
        r['winner'] == name for r in recent[own_start_losses:]
    ):
        stories.append(Story(108, 'comeback', f"At {label}, {name} recovered from a "
                             f"0–{own_start_losses} start with {len(recent) - own_start_losses} consecutive wins to take the title."))
    games = _games(bracket, name)
    if event.get('winner') == name and len(bracket) >= 3 and games and games[1] == 0:
        stories.append(Story(104, 'bracket', f"{name} won the {label} bracket without dropping a game, "
                             f"finishing with a {games[0]}–0 game record."))
    if latest.get('placement') == 2:
        wins = [r for r in bracket if r['winner'] == name]
        scores = [_games([r], name) for r in wins]
        if len(wins) >= 3 and all(g and max(g) >= 2 and g[0] - g[1] == 1 for g in scores):
            stories.append(Story(98, 'finalist_run', f"At {label}, {name} reached the final through "
                                 f"{len(wins)} deciding-game bracket victories."))
    # A broken opponent streak explains why an individual win mattered.
    for row in recent:
        if row['winner'] != name:
            continue
        opponent = row['player_2'] if row['player_1'] == name else row['player_1']
        earlier = []
        for meeting in matches:
            if meeting['match_id'] == row['match_id']:
                break
            if opponent in (meeting['player_1'], meeting['player_2']):
                earlier.append(meeting)
        losses = 0
        for meeting in reversed(earlier):
            if meeting['winner'] == name:
                break
            losses += 1
        if losses >= 4:
            stories.append(Story(99, 'revenge', f"A victory over {opponent} at {label} ended "
                                 f"{name}'s {losses}-set losing streak in their direct meetings."))

    podiums = 0
    for row in reversed(own):
        if row.get('placement') not in (1, 2, 3):
            break
        podiums += 1
    if podiums >= 4 and runners < 3:
        stories.append(Story(80, 'placements', f"{name} has reached the podium at {podiums} consecutive recorded appearances."))
    if len(timeline) >= 4:
        last, previous, baseline = timeline[-1], timeline[-2], timeline[-4]
        gain = float(last['elo_exact']) - float(baseline['elo_exact'])
        change = float(last['elo_exact']) - float(previous['elo_exact'])
        if gain >= 25:
            text = f"{name} gained {gain:.1f} Elo points across the last three archived tournaments"
            text += (f", although the latest event brought a {abs(change):.1f}-point drop." if change < -10 else '.')
            stories.append(Story(75, 'form', text))
    return stories


def tournament_stories(archive: dict[str, Any], number: int) -> list[Story]:
    """Describe only evidence available at the end of the selected event."""
    data = _through(archive, number)
    event = data['events'][-1]
    winner = event.get('winner')
    current = [r for r in data['matches'] if r['tournament_id'] == event['tournament_id']]
    stories = []
    if not winner:
        return stories
    own = [r for r in current if winner in (r['player_1'], r['player_2'])]
    start_losses = 0
    for r in own:
        if r['winner'] == winner:
            break
        start_losses += 1
    if start_losses >= 2 and all(r['winner'] == winner for r in own[start_losses:]):
        stories.append(Story(110, 'comeback', f"{winner} lost the opening {start_losses} sets, "
                             f"then won {len(own) - start_losses} consecutive sets to take the title."))
    bracket = [r for r in own if r.get('stage') in {'bracket', 'knockout'}]
    games = _games(bracket, winner)
    if len(bracket) >= 3 and games and games[1] == 0 and all(r['winner'] == winner for r in bracket):
        opponents = list(dict.fromkeys(r['player_2'] if r['player_1'] == winner else r['player_1'] for r in bracket))
        stories.append(Story(108, 'bracket', f"{winner} completed the bracket without dropping a game, "
                             f"going {games[0]}–0 against {' and '.join(opponents)}."))
    # Repeated final appearances and debut runs belong in recaps too.
    participants = [r for r in data['appearances'] if r['tournament_id'] == event['tournament_id']]
    for row in participants:
        name = row['player']
        candidates = player_stories(data, name)
        for candidate in candidates:
            if candidate.theme == 'placements' and candidate.priority >= 100:
                stories.append(candidate)
            elif candidate.theme == 'group_bracket':
                stories.append(candidate)
            elif candidate.theme == 'debut':
                own_bracket = [r for r in current if r.get('stage') in {'bracket', 'knockout'}
                               and r['winner'] == name]
                if own_bracket:
                    stories.append(Story(92, candidate.theme, candidate.text.split(" One event")[0]))
        recent = [r for r in current if name in (r['player_1'], r['player_2'])]
        run = [r for r in recent if r.get('stage') in {'bracket', 'knockout'} and r['winner'] == name]
        if row.get('placement') == 2 and len(run) >= 3:
            close = [_games([r], name) for r in run]
            if all(g and max(g) >= 2 and g[0] - g[1] == 1 for g in close):
                placement = next((s for s in stories if s.theme == 'placements' and s.text.startswith(name + ' ')), None)
                if placement:
                    stories.remove(placement)
                text = (placement.text + ' ') if placement else ''
                text += f"At WC {number:02d}, {name} reached the final through {len(run)} deciding-game bracket victories."
                stories.append(Story(106, 'finalist_run', text))
    return stories
