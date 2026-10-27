"""Achievement badges and the holder dialog for Player and Tournament pages."""

from __future__ import annotations

from typing import Any

import streamlit as st

from dashboard_pages.navigation_routes import (
    player_profile_url,
    tournament_archive_url,
)
from dashboard_pages.ui_components import (
    dashboard_table_html,
    internal_dashboard_link,
)
from smash_stats.achievements import (
    ACHIEVEMENT_CATALOGUE,
    TIER_NAMES,
    summarize_achievements,
    tier_description,
)
from text_format import format_date, format_ordinal


ACHIEVEMENT_ICONS = {
    "sets": ":material/bolt:",
    "championships": ":material/emoji_events:",
    "bracket": ":material/account_tree:",
    "elo": ":material/trending_up:",
    "career": ":material/military_tech:",
}
RARE_ICON = ":material/diamond:"
TOURNAMENT_CARD_COLUMNS = 2


def _wc_label(tournament_number: int) -> str:
    return f"WC {int(tournament_number):02d}"


def player_badges(
    unlocks: list[dict[str, Any]],
    player_id: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Returns one player's badges and all badges (for the holder dialog)."""

    badges = summarize_achievements(unlocks)
    return (
        [badge for badge in badges if badge["player_id"] == str(player_id)],
        badges,
    )


def badge_label(badge: dict[str, Any]) -> str:
    """Returns the compact badge text, e.g. "Giant Killer ×3" or "Mainstay · WC 07"."""

    if badge["count"] > 1:
        return f"{badge['title']} ×{badge['count']}"
    return f"{badge['title']} · {_wc_label(badge['latest']['tournament_number'])}"


def badge_help(badge: dict[str, Any]) -> str:
    """Returns the tooltip: description, when it was reached and rarity."""

    parts = [badge["description"]]
    latest = badge["latest"]
    reached = f"{_wc_label(latest['tournament_number'])}, {format_date(latest['tournament_date'])}"
    if badge["count"] > 1:
        first = badge["first"]
        parts.append(
            f"First at {_wc_label(first['tournament_number'])}, "
            f"{format_date(first['tournament_date'])}; latest at {reached}."
        )
    else:
        parts.append(f"Reached at {reached}.")
    if badge["tier_name"]:
        parts.append(f"{badge['tier_name']} tier.")
    parts.append(_holders_text(badge["holders"]))
    return " ".join(parts)


def _holders_text(holders: int) -> str:
    return "Held by 1 player." if holders == 1 else f"Held by {holders} players."


def unlock_label(entry: dict[str, Any]) -> str:
    """Returns the button text for one unlock at a tournament."""

    if entry["occurrence"] > 1:
        return f"{entry['title']} ×{entry['occurrence']}"
    return str(entry["title"])


def unlock_help(entry: dict[str, Any], *, rare: bool = False) -> str:
    """Returns the tooltip: description, then rarity, tier and Set context."""

    parts = [str(entry["description"])]
    if rare:
        parts.append("Rare.")
    if entry["tier"]:
        parts.append(f"{TIER_NAMES[entry['tier'] - 1]} tier.")
    if entry["occurrence"] > 1:
        parts.append(f"{format_ordinal(entry['occurrence'])} time.")
    if entry["detail"]:
        parts.append(f"{entry['detail']}.")
    return " ".join(parts)


def tournament_unlock_groups(
    unlocks: list[dict[str, Any]],
    tournament_number: int,
    player_order: list[str],
) -> list[tuple[dict[str, Any], list[dict[str, Any]]]]:
    """
    Groups one tournament's unlocks by player.

    Players follow ``player_order`` (the final standings); each player's
    unlocks keep their chronological order.
    """

    rank = {str(player_id): index for index, player_id in enumerate(player_order)}
    by_player: dict[str, list[dict[str, Any]]] = {}
    for entry in unlocks:
        if entry["tournament_number"] == int(tournament_number):
            by_player.setdefault(entry["player_id"], []).append(entry)

    return sorted(
        (
            ({"player_id": player_id, "player": entries[0]["player"]}, entries)
            for player_id, entries in by_player.items()
        ),
        key=lambda group: (
            rank.get(group[0]["player_id"], len(rank)),
            group[0]["player"].casefold(),
        ),
    )


def achievement_holders_table_html(
    badges: list[dict[str, Any]],
    key: str,
) -> str:
    """Returns every holder of one achievement, earliest first."""

    achievement = ACHIEVEMENT_CATALOGUE[key]
    holders = sorted(
        (badge for badge in badges if badge["key"] == key),
        key=lambda badge: (
            -(badge["tier"] or 0),
            -badge["count"],
            badge["first"]["tournament_number"],
            badge["player"].casefold(),
        ),
    )

    links: dict[tuple[int, int], str] = {}
    rows: list[list[str]] = []
    if "tiers" in achievement:
        headers = ["Player", "Level", "Reached", "Date"]
        columns = "1.4fr 1.2fr 0.8fr 1fr"
        for row_index, badge in enumerate(holders):
            latest = badge["latest"]
            rows.append([
                badge["player"],
                f"{badge['title']} ({badge['tier_name']})",
                _wc_label(latest["tournament_number"]),
                format_date(latest["tournament_date"]),
            ])
            links[(row_index, 2)] = tournament_archive_url(latest["tournament_number"])
    elif achievement.get("repeatable"):
        headers = ["Player", "Times", "First", "Latest"]
        columns = "1.4fr 0.6fr 1.2fr 1.2fr"
        for row_index, badge in enumerate(holders):
            first, latest = badge["first"], badge["latest"]
            rows.append([
                badge["player"],
                str(badge["count"]),
                f"{_wc_label(first['tournament_number'])} · {format_date(first['tournament_date'])}",
                f"{_wc_label(latest['tournament_number'])} · {format_date(latest['tournament_date'])}",
            ])
            links[(row_index, 2)] = tournament_archive_url(first["tournament_number"])
            links[(row_index, 3)] = tournament_archive_url(latest["tournament_number"])
    else:
        holders.sort(key=lambda badge: (badge["first"]["tournament_number"], badge["player"].casefold()))
        show_detail = any(badge["first"]["detail"] for badge in holders)
        headers = ["Player", "WC", "Date"] + (["Detail"] if show_detail else [])
        columns = "1.4fr 0.7fr 1fr" + (" 1.8fr" if show_detail else "")
        for row_index, badge in enumerate(holders):
            first = badge["first"]
            row = [
                badge["player"],
                _wc_label(first["tournament_number"]),
                format_date(first["tournament_date"]),
            ]
            if show_detail:
                row.append(str(first["detail"] or ""))
            rows.append(row)
            links[(row_index, 1)] = tournament_archive_url(first["tournament_number"])

    for row_index, badge in enumerate(holders):
        links[(row_index, 0)] = player_profile_url(badge["player_id"])

    return dashboard_table_html(
        headers,
        rows,
        columns=columns,
        emphasis_column=0,
        cell_links=links,
    )


def player_unlock_history_html(
    unlocks: list[dict[str, Any]],
    key: str,
    player_id: str,
) -> str | None:
    """
    Returns every time one player unlocked an achievement, oldest first.

    Only for achievements reached more than once (repeats or tiers); a
    single unlock is already shown on the badge. Tiers get a Level column,
    and the Detail column (opponent, seeds, Elo gap) appears when any row has
    one.
    """

    entries = [
        entry for entry in unlocks
        if entry["key"] == key and entry["player_id"] == str(player_id)
    ]
    if len(entries) < 2:
        return None

    tiered = any(entry["tier"] for entry in entries)
    show_detail = any(entry["detail"] for entry in entries)
    headers = (["Level"] if tiered else ["#"]) + ["WC", "Date"]
    columns = ("1.2fr" if tiered else "0.4fr") + " 0.7fr 1fr"
    if show_detail:
        headers.append("Detail")
        columns += " 2.2fr"

    rows: list[list[str]] = []
    links: dict[tuple[int, int], str] = {}
    for row_index, entry in enumerate(entries):
        first = (
            f"{entry['title']} ({TIER_NAMES[entry['tier'] - 1]})"
            if tiered
            else str(entry["occurrence"])
        )
        row = [
            first,
            _wc_label(entry["tournament_number"]),
            format_date(entry["tournament_date"]),
        ]
        if show_detail:
            row.append(str(entry["detail"] or "–"))
        rows.append(row)
        links[(row_index, 1)] = tournament_archive_url(entry["tournament_number"])

    return dashboard_table_html(headers, rows, columns=columns, cell_links=links)


@st.dialog("Achievement", width="medium")
def show_achievement_dialog(
    key: str,
    badges: list[dict[str, Any]],
    *,
    player_history: tuple[str, str] | None = None,
) -> None:
    """
    Shows the description and every player who unlocked the achievement.

    ``player_history`` is ``(player name, table markup)`` from the profile:
    every time that player reached the achievement, shown before all holders.
    """

    achievement = ACHIEVEMENT_CATALOGUE[key]
    holder_count = len({badge["player_id"] for badge in badges if badge["key"] == key})
    st.subheader(achievement["title"])
    if "tiers" in achievement:
        st.markdown(
            "\n".join(
                f"- **{TIER_NAMES[tier - 1]} – {title}:** {tier_description(key, tier)}"
                for tier, (_threshold, title) in enumerate(achievement["tiers"], start=1)
            )
        )
    else:
        st.write(achievement["description"])
    if player_history is not None:
        player_name, history_html = player_history
        st.markdown(f"**{player_name}**")
        st.markdown(history_html, unsafe_allow_html=True)
        st.space("medium")
        st.markdown("**All holders**")
    st.caption(_holders_text(holder_count).rstrip("."))
    st.markdown(
        achievement_holders_table_html(badges, key),
        unsafe_allow_html=True,
    )


def _badge_icon(group: str, rare: bool) -> str | None:
    return RARE_ICON if rare else ACHIEVEMENT_ICONS.get(group)


def render_player_badges(
    unlocks: list[dict[str, Any]],
    player_id: str,
) -> None:
    """Shows a player's badges as wrapping chips; a click opens the dialog."""

    badges, all_badges = player_badges(unlocks, player_id)
    if not badges:
        return

    st.subheader("Achievements")
    rare = sum(1 for badge in badges if badge["rare"])
    st.caption(
        f"{len(badges)} achievements"
        + (f" · {rare} rare" if rare else "")
        + " · select one for details"
    )
    with st.container(horizontal=True, gap="small"):
        for badge in badges:
            if st.button(
                badge_label(badge),
                key=f"player_badge_{badge['key']}",
                icon=_badge_icon(badge["group"], badge["rare"]),
                help=badge_help(badge),
            ):
                history_html = player_unlock_history_html(unlocks, badge["key"], player_id)
                show_achievement_dialog(
                    badge["key"],
                    all_badges,
                    player_history=(
                        (badge["player"], history_html) if history_html else None
                    ),
                )


def render_tournament_unlocks(
    unlocks: list[dict[str, Any]],
    tournament_number: int,
    player_order: list[str],
) -> None:
    """
    Shows one tournament's achievements as one bordered card per player, in
    standings order and two cards per row on wide screens. A button opens
    the holder dialog.
    """

    groups = tournament_unlock_groups(unlocks, tournament_number, player_order)
    if not groups:
        return

    all_badges = summarize_achievements(unlocks)
    rare = {
        (badge["player_id"], badge["key"], badge["tier"])
        for badge in all_badges
        if badge["rare"]
    }

    st.subheader("Achievements Unlocked")
    for start in range(0, len(groups), TOURNAMENT_CARD_COLUMNS):
        columns = st.columns(TOURNAMENT_CARD_COLUMNS)
        for column, (player, entries) in zip(
            columns,
            groups[start:start + TOURNAMENT_CARD_COLUMNS],
        ):
            with column, st.container(border=True, height="stretch"):
                st.markdown(
                    "<strong>"
                    + internal_dashboard_link(
                        player["player"],
                        player_profile_url(player["player_id"]),
                    )
                    + "</strong>",
                    unsafe_allow_html=True,
                )
                with st.container(horizontal=True, gap="small"):
                    for entry in entries:
                        is_rare = (player["player_id"], entry["key"], entry["tier"]) in rare
                        if st.button(
                            unlock_label(entry),
                            key=(
                                f"tournament_unlock_{entry['key']}_{player['player_id']}_"
                                f"{entry['tier']}_{entry['occurrence']}"
                            ),
                            icon=_badge_icon(entry["group"], is_rare),
                            help=unlock_help(entry, rare=is_rare),
                        ):
                            show_achievement_dialog(entry["key"], all_badges)
