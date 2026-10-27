"""Hall of Fame page: all-time records and recently reached milestones."""

from __future__ import annotations

import html
from typing import Any, Callable

import streamlit as st

from dashboard_pages.navigation_routes import (
    player_profile_url,
    tournament_archive_url,
)
from dashboard_pages.ui_components import (
    dashboard_table_html,
    internal_dashboard_link,
)
from smash_stats.hall_of_fame import HALL_OF_FAME_GROUPS
from text_format import format_date, format_elo


RECENT_MILESTONE_TOURNAMENTS = 3
VISIBLE_RUNNERS_UP = 3

SINGULAR_UNITS = {
    "titles": "title",
    "finals": "final",
    "podiums": "podium",
    "wins": "win",
    "Sets": "Set",
    "appearances": "appearance",
    "Set wins": "Set win",
    "Set wins in a row": "Set win in a row",
    "tournaments": "tournament",
}

HALL_OF_FAME_CAPTION = (
    "All-time records of the World Championship archive with the top three "
    "for each. Ties share a place. Walkovers are not rated Sets. Elo ranking "
    "records count the Elo standings after each tournament, not placements."
)


def record_value_text(value: Any, unit: str) -> str:
    """Return a record value with its unit, e.g. "5 titles" or "1299.7 Elo"."""

    if unit == "Elo":
        return f"{format_elo(value)} Elo"
    if unit == "%":
        return f"{float(value):.1f}%"
    unit_text = SINGULAR_UNITS.get(unit, unit) if value == 1 else unit
    return f"{value} {unit_text}"


def _player_link(player: dict[str, Any]) -> str:
    return internal_dashboard_link(
        str(player["player"]),
        player_profile_url(str(player["player_id"])),
        class_name="hof-link",
    )


def _players_html(entry: dict[str, Any], *, record_key: str) -> str:
    links = [_player_link(player) for player in entry["players"]]
    if len(links) == 1:
        return links[0]

    # A win streak belongs to its first player; a matchup to both.
    second_class = "hof-regular" if record_key == "longest_h2h_streak" else ""
    return (
        f"{links[0]}"
        ' <span class="hof-muted">vs</span> '
        f'<span class="{second_class}">{links[1]}</span>'
    )


def _detail_text(entry: dict[str, Any], record_key: str) -> str:
    detail = str(entry.get("detail") or "")
    if record_key == "most_played_matchup" and detail:
        return f"H2H {detail}"
    return detail


def _rank_groups(entries: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """Group ranked entries by rank; tied single holders without detail merge."""

    groups: list[list[dict[str, Any]]] = []
    for entry in entries:
        if groups and groups[-1][0]["rank"] == entry["rank"]:
            groups[-1].append(entry)
        else:
            groups.append([entry])

    merged: list[list[dict[str, Any]]] = []
    for group in groups:
        if all(len(entry["players"]) == 1 and not entry["detail"] for entry in group):
            merged.append(group)
        else:
            merged.extend([entry] for entry in group)
    return merged


def _group_players_html(group: list[dict[str, Any]], record_key: str) -> str:
    return ", ".join(_players_html(entry, record_key=record_key) for entry in group)


def _holder_line(group: list[dict[str, Any]], record: dict[str, Any]) -> str:
    detail = _detail_text(group[0], record["key"])
    return (
        '<div class="hof-line hof-holder">'
        f'<div class="hof-name">{_group_players_html(group, record["key"])}</div>'
        '<div class="hof-value">'
        f'{html.escape(record_value_text(group[0]["value"], record["unit"]))}'
        "</div>"
        + (f'<div class="hof-subline">{html.escape(detail)}</div>' if detail else "")
        + "</div>"
    )


def _runner_up_line(group: list[dict[str, Any]], record: dict[str, Any]) -> str:
    detail = _detail_text(group[0], record["key"])
    value = record_value_text(group[0]["value"], record["unit"])
    suffix = f"{value} · {detail}" if detail else value
    return (
        '<div class="hof-line hof-runner-up">'
        '<div class="hof-name">'
        f'<span class="hof-muted">{group[0]["rank"]}.</span> '
        f'{_group_players_html(group, record["key"])}</div>'
        f'<div class="hof-subline">{html.escape(suffix)}</div>'
        "</div>"
    )


def _collapsed_lines(lines: list[str]) -> str:
    """Keep up to VISIBLE_RUNNERS_UP lines; the rest open in place."""

    if len(lines) <= VISIBLE_RUNNERS_UP:
        return "".join(lines)

    visible = VISIBLE_RUNNERS_UP - 1
    hidden = lines[visible:]
    return (
        "".join(lines[:visible])
        + '<details class="hof-more">'
        f"<summary>{len(hidden)} more</summary>"
        f"{''.join(hidden)}"
        "</details>"
    )


def _holder_html(record: dict[str, Any]) -> str:
    holders = [entry for entry in record["entries"] if entry["rank"] == 1]
    if not holders:
        return '<div class="hof-muted">No record yet</div>'
    return _collapsed_lines(
        [_holder_line(group, record) for group in _rank_groups(holders)]
    )


def _runners_up_html(record: dict[str, Any]) -> str:
    runners_up = [entry for entry in record["entries"] if entry["rank"] > 1]
    if not runners_up:
        return '<div class="hof-muted">—</div>'
    return _collapsed_lines(
        [_runner_up_line(group, record) for group in _rank_groups(runners_up)]
    )


def record_card_html(record: dict[str, Any]) -> str:
    """Return one record card: title band on top, holder and runners-up below."""

    return (
        '<article class="hof-card">'
        f'<header class="hof-card-title">{html.escape(record["title"])}</header>'
        '<div class="hof-card-body">'
        '<div class="hof-card-column">'
        '<div class="hof-label">Holder</div>'
        f"{_holder_html(record)}"
        "</div>"
        '<div class="hof-card-column">'
        '<div class="hof-label">Runners-up</div>'
        f"{_runners_up_html(record)}"
        "</div>"
        "</div>"
        "</article>"
    )


def record_cards_html(records: list[dict[str, Any]]) -> str:
    """Return a responsive grid of record cards."""

    return (
        '<div class="hof-grid">'
        + "".join(record_card_html(record) for record in records)
        + "</div>"
    )


TITLE_RANK_ICONS = {1: "🥇", 2: "🥈", 3: "🥉"}


def title_leaders_table(record: dict[str, Any]) -> dict[str, Any] | None:
    """Return dashboard_table_html data ranking every title holder."""

    if not record["entries"]:
        return None
    rows = []
    links: dict[tuple[int, int], str] = {}
    highlights: dict[int, str] = {}
    for row_index, entry in enumerate(record["entries"]):
        rank = int(entry["rank"])
        player = entry["players"][0]
        titles = int(entry["value"])
        rows.append(
            [
                f"{TITLE_RANK_ICONS.get(rank, '')} #{rank}".strip(),
                str(player["player"]),
                f"{titles} {'Title' if titles == 1 else 'Titles'}",
            ]
        )
        links[(row_index, 1)] = player_profile_url(str(player["player_id"]))
        if rank == 1:
            highlights[row_index] = "winners"
    return {
        "headers": ["Rank", "Player", "Titles"],
        "rows": rows,
        "cell_links": links,
        "row_highlights": highlights,
        "columns": "minmax(5.5rem,0.55fr) minmax(10rem,2fr) minmax(7rem,1fr)",
    }


def recent_milestone_table(
    tournaments: list[tuple[int, str]],
    milestones_by_tournament: dict[int, list[str]],
) -> dict[str, Any] | None:
    """Return table data for milestones of (number, date) tournaments in order."""

    rows = []
    markup: dict[tuple[int, int], str] = {}
    for number, date in tournaments:
        label = f"WC {number:02d}"
        for milestone in milestones_by_tournament.get(number, []):
            row_index = len(rows)
            rows.append([label, milestone])
            markup[(row_index, 0)] = (
                "<span>"
                + internal_dashboard_link(label, tournament_archive_url(number))
                + f'<span class="control-table-subline">'
                f"{html.escape(format_date(date))}</span>"
                "</span>"
            )

    if not rows:
        return None
    return {
        "headers": ["Tournament", "Milestone"],
        "rows": rows,
        "cell_html": markup,
        "columns": "minmax(6rem,0.35fr) minmax(0,2fr)",
    }


def hall_of_fame_styles() -> str:
    return """
        <style>
        .hof-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(min(100%, 21rem), 1fr));
            gap: 0.9rem;
            margin-top: 0.9rem;
            margin-bottom: 1rem;
        }
        .hof-card {
            display: flex;
            flex-direction: column;
            overflow: hidden;
            border: 1px solid rgba(128, 128, 128, 0.30);
            border-radius: 0.8rem;
        }
        .hof-card-title {
            padding: 0.75rem 1rem;
            border-bottom: 1px solid rgba(128, 128, 128, 0.24);
            background: rgba(128, 128, 128, 0.08);
            color: var(--swc-text);
            font-size: 1.05rem;
            font-weight: 800;
            line-height: 1.3;
        }
        .hof-card-body {
            display: grid;
            flex: 1;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 1rem;
            padding: 0.85rem 1rem 1rem;
            background: var(--swc-surface);
        }
        .hof-label {
            margin-bottom: 0.35rem;
            color: var(--swc-text-520);
            font-size: 0.72rem;
            font-weight: 750;
            letter-spacing: 0.035em;
            text-transform: uppercase;
        }
        .hof-line + .hof-line,
        .hof-line + .hof-more,
        .hof-more .hof-line {
            margin-top: 0.5rem;
        }
        .hof-name {
            color: var(--swc-text);
            font-weight: 800;
            line-height: 1.35;
        }
        .hof-runner-up .hof-name {
            font-weight: 700;
        }
        .hof-regular {
            font-weight: 500;
        }
        .hof-muted {
            color: var(--swc-text-580);
            font-size: 0.92em;
            font-weight: 600;
        }
        .hof-value {
            margin-top: 0.1rem;
            color: var(--swc-text);
            font-weight: 700;
        }
        .hof-subline {
            margin-top: 0.15rem;
            color: var(--swc-text-580);
            font-size: 0.78rem;
            font-weight: 600;
            line-height: 1.3;
        }
        .hof-link,
        .hof-link:link,
        .hof-link:visited {
            color: inherit !important;
            text-decoration: none !important;
        }
        .hof-link:hover,
        .hof-link:focus-visible {
            text-decoration: underline !important;
            text-underline-offset: 0.18em;
        }
        .hof-more summary {
            margin-top: 0.5rem;
            cursor: pointer;
            color: var(--swc-text-580);
            font-size: 0.85rem;
            font-weight: 700;
        }
        .hof-more summary:hover,
        .hof-more summary:focus-visible {
            color: var(--swc-text);
        }
        </style>
    """


def render_hall_of_fame(
    include_inactive: bool,
    *,
    load_hall_of_fame: Callable[[bool], list[dict[str, Any]]],
    load_tournaments: Callable[[], list[dict[str, Any]]],
    load_tournament_milestones: Callable[[int], list[str]],
) -> None:
    st.title("🏛️ Hall of Fame")
    st.caption(HALL_OF_FAME_CAPTION)

    records = load_hall_of_fame(include_inactive)
    st.markdown(hall_of_fame_styles(), unsafe_allow_html=True)

    for group_key, group_title in HALL_OF_FAME_GROUPS:
        group_records = [record for record in records if record["group"] == group_key]
        if not group_records:
            continue
        st.subheader(group_title)
        title_record = next(
            (record for record in group_records if record["key"] == "most_titles"),
            None,
        )
        if title_record is not None:
            group_records.remove(title_record)
            title_table = title_leaders_table(title_record)
            if title_table is not None:
                st.markdown("#### Title Leaders")
                st.markdown(
                    dashboard_table_html(
                        title_table["headers"],
                        title_table["rows"],
                        columns=title_table["columns"],
                        row_highlights=title_table["row_highlights"],
                        cell_links=title_table["cell_links"],
                        emphasis_column=1,
                        mobile_cards=True,
                        mobile_card_variant="titles",
                    ),
                    unsafe_allow_html=True,
                )
        if group_records:
            st.markdown(record_cards_html(group_records), unsafe_allow_html=True)

    st.subheader("Recent Milestones")
    recent = sorted(
        (
            (int(row["WC"].split()[1]), str(row["Date"] or ""))
            for row in load_tournaments()
        ),
        reverse=True,
    )[:RECENT_MILESTONE_TOURNAMENTS]
    milestone_table = recent_milestone_table(
        recent,
        {number: load_tournament_milestones(number) for number, _ in recent},
    )
    if milestone_table is None:
        st.info("No milestones have been reached in the latest tournaments.")
        return

    st.caption(
        f"Milestones reached at the last {len(recent)} World Championships."
    )
    st.markdown(
        dashboard_table_html(
            milestone_table["headers"],
            milestone_table["rows"],
            columns=milestone_table["columns"],
            cell_html=milestone_table["cell_html"],
            mobile_cards=True,
        ),
        unsafe_allow_html=True,
    )
