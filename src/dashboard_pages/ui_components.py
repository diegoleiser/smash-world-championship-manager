"""Shared visual helpers for dashboard components."""

from __future__ import annotations

import html
from collections.abc import Sequence
from typing import Any


def format_optional_percentage(value: float | None) -> str:
    """Format a percentage while keeping pending statistics readable."""

    return "–" if value is None else f"{float(value):.1f}%"


def compact_metric_strip_html(
    items: list[
        tuple[str, str | int]
        | tuple[str, str | int, str]
    ],
    *,
    mobile_columns: int | None = None,
) -> str:
    """Return a compact horizontal strip of small summary metrics."""

    cells = []
    for item in items:
        label, value = item[:2]
        note = item[2] if len(item) == 3 else None
        note_html = (
            '<div class="compact-metric-strip-note">'
            f"{html.escape(str(note))}</div>"
            if note
            else ""
        )
        cells.append(
            '<div class="compact-metric-strip-cell">'
            f'<div class="compact-metric-strip-label">{html.escape(label)}</div>'
            f'<div class="compact-metric-strip-value">{html.escape(str(value))}</div>'
            f"{note_html}</div>"
        )
    cells_html = "".join(cells)
    mobile_column_count = mobile_columns or len(items)
    return f"""
    <style>
    .compact-metric-strip {{
        display: grid;
        grid-template-columns: repeat(
            var(--compact-metric-columns),
            minmax(0, 1fr)
        );
        max-width: 38rem;
        margin: 0.65rem 0 0.8rem;
        overflow: hidden;
        border: 1px solid rgba(128, 128, 128, 0.30);
        border-radius: 0.8rem;
        background: var(--swc-surface);
    }}
    .compact-metric-strip-cell {{
        padding: 0.8rem 0.9rem;
        border-right: 1px solid rgba(128, 128, 128, 0.20);
    }}
    .compact-metric-strip-cell:last-child {{ border-right: none; }}
    .compact-metric-strip-label {{
        color: var(--swc-text-550);
        font-size: 0.7rem;
        font-weight: 750;
        letter-spacing: 0.035em;
        text-transform: uppercase;
    }}
    .compact-metric-strip-value {{
        margin-top: 0.28rem;
        color: var(--swc-text);
        font-size: 1.3rem;
        font-weight: 800;
    }}
    .compact-metric-strip-note {{
        margin-top: 0.18rem;
        color: var(--swc-text-580);
        font-size: 0.7rem;
        font-weight: 650;
        line-height: 1.25;
    }}
    @media (max-width: 700px) {{
        .compact-metric-strip {{
            grid-template-columns: repeat(
                var(--compact-metric-mobile-columns),
                minmax(0, 1fr)
            );
            max-width: none;
        }}
        .compact-metric-strip-cell {{ padding: 0.7rem 0.55rem; }}
        .compact-metric-strip-label {{ font-size: 0.62rem; }}
        .compact-metric-strip-value {{ font-size: 1.15rem; }}
    }}
    </style>
    <div class="compact-metric-strip" style="--compact-metric-columns:{len(items)};--compact-metric-mobile-columns:{mobile_column_count}">
      {cells_html}
    </div>
    """


def mobile_control_center_card_styles() -> str:
    """Let equal-height desktop control cards grow naturally on mobile."""

    return """
    <style>
    @media (max-width: 700px) {
        div[class*="st-key-control_center_alternatives_section_"] {
            margin-top: 1.25rem;
        }
        div[class*="st-key-control_center_equal_card_"] {
            height: auto !important;
            max-height: none !important;
            overflow: visible !important;
        }
        div[class*="st-key-control_center_equal_card_"]
        [data-testid="stVerticalBlockBorderWrapper"],
        div[class*="st-key-control_center_equal_card_"]
        [data-testid="stVerticalBlock"] {
            height: auto !important;
            max-height: none !important;
            overflow: visible !important;
        }
    }
    </style>
    """


def mobile_seeding_styles() -> str:
    """Keep seeding controls in one compact row on narrow screens."""

    return """
    <style>
    div[class*="st-key-mobile_seeding_row_"] {
        max-width: 46rem;
        padding: 0.28rem 0;
        border-bottom: 1px solid rgba(128, 128, 128, 0.18);
    }
    div[class*="st-key-mobile_seeding_row_"]
    [data-testid="stHorizontalBlock"] {
        display: grid !important;
        grid-template-columns: 3.5rem minmax(10rem, 1fr) 2.4rem 2.4rem;
        gap: 0.55rem !important;
        align-items: center;
    }
    div[class*="st-key-mobile_seeding_row_"]
    [data-testid="stColumn"] {
        width: auto !important;
        min-width: 0 !important;
    }
    div[class*="st-key-mobile_seeding_row_"]
    [data-testid="stMarkdownContainer"] p {
        margin: 0;
    }
    div[class*="st-key-mobile_seeding_row_"] .stButton button {
        width: 2.4rem;
        min-height: 2.25rem;
        padding: 0;
    }
    @media (max-width: 700px) {
        div[class*="st-key-mobile_seeding_row_"] {
            max-width: none;
        }
        div[class*="st-key-mobile_seeding_row_"]
        [data-testid="stHorizontalBlock"] {
            display: grid !important;
            grid-template-columns: 2.5rem minmax(0, 1fr) 2.4rem 2.4rem;
            gap: 0.4rem !important;
            align-items: center;
        }
    }
    </style>
    """


def internal_dashboard_link(
    label: str,
    href: str,
    *,
    class_name: str = "control-table-link",
) -> str:
    """Return an escaped same-app link for custom dashboard markup."""

    link_text = str(href)
    if not (
        link_text.startswith("?")
        or (link_text.startswith("/") and not link_text.startswith("//"))
    ):
        raise ValueError("Dashboard links must use internal URLs.")
    return (
        f'<a class="{html.escape(class_name, quote=True)}" '
        f'href="{html.escape(link_text, quote=True)}" target="_self">'
        f"{html.escape(str(label))}</a>"
    )


def archived_match_result_html(
    context_label: str,
    player_1_name: str,
    player_2_name: str,
    score_text: str,
    *,
    winner_name: str | None,
    status_label: str,
) -> str:
    """Return a compact read-only result card for an archived set."""

    player_1_color = (
        "var(--swc-positive-bright)"
        if winner_name == player_1_name
        else "var(--swc-text)"
    )
    player_2_color = (
        "var(--swc-positive-bright)"
        if winner_name == player_2_name
        else "var(--swc-text)"
    )
    return (
        '<div style="overflow:hidden;'
        'border:1px solid rgba(128,128,128,0.30);'
        'border-radius:0.8rem;">'
        '<div style="padding:0.7rem 1rem;'
        'border-bottom:1px solid rgba(128,128,128,0.24);'
        'background:rgba(128,128,128,0.08);'
        'color:var(--swc-text-580);'
        'font-size:0.75rem;font-weight:750;'
        'letter-spacing:0.035em;text-align:center;'
        'text-transform:uppercase;">'
        f"{html.escape(context_label)}"
        "</div>"
        '<div style="display:grid;'
        'grid-template-columns:1fr auto 1fr;'
        'align-items:center;gap:1rem;'
        'min-height:6.2rem;padding:1rem 1.25rem;">'
        '<div style="text-align:right;font-size:1.65rem;'
        f'font-weight:800;color:{player_1_color};">'
        f"{html.escape(player_1_name)}"
        "</div>"
        '<div style="font-size:1.6rem;font-weight:850;'
        'color:var(--swc-text);">'
        f"{html.escape(score_text)}"
        "</div>"
        '<div style="text-align:left;font-size:1.65rem;'
        f'font-weight:800;color:{player_2_color};">'
        f"{html.escape(player_2_name)}"
        "</div>"
        "</div>"
        '<div style="display:grid;grid-template-columns:1fr 1fr;'
        'gap:1rem;padding:0.75rem 1rem;'
        'border-top:1px solid rgba(128,128,128,0.20);'
        'background:var(--swc-surface);'
        'color:var(--swc-text-660);font-size:0.82rem;">'
        '<div style="text-align:left;">Winner · '
        f"<strong>{html.escape(winner_name or 'Unknown')}</strong>"
        "</div>"
        '<div style="text-align:right;">Status · '
        f"<strong>{html.escape(status_label)}</strong>"
        "</div>"
        "</div></div>"
    )


def versus_header_html(
    player_1_name: str,
    player_2_name: str,
    *,
    name_size: str,
    margin: str,
) -> str:
    """Return the centered "Player VS Player" heading used in Set editors."""

    def name_html(name: str, align: str) -> str:
        return (
            '<div style="'
            f'text-align:{align};'
            f'font-size:{name_size};'
            'font-weight:750;'
            '">'
            f'{html.escape(name)}'
            '</div>'
        )

    return (
        '<div style="'
        'display:grid;'
        'grid-template-columns:1fr auto 1fr;'
        'align-items:center;'
        'gap:1rem;'
        f'margin:{margin};'
        '">'
        + name_html(player_1_name, "right")
        + '<div style="'
        'opacity:0.55;'
        'font-size:0.9rem;'
        'font-weight:700;'
        '">'
        'VS'
        '</div>'
        + name_html(player_2_name, "left")
        + '</div>'
    )


def up_next_matchup_html(
    context_label: str,
    player_1_name: str,
    player_2_name: str,
    *,
    player_1_probability: float | None = None,
) -> str:
    """Return the shared live-control header for the next playable set."""

    probability_content = (
        '<div style="text-align:right;">'
        f"{player_1_probability:.1%} win chance"
        '</div><div style="text-align:left;">'
        f"{1.0 - player_1_probability:.1%} win chance"
        "</div>"
        if player_1_probability is not None
        else ""
    )
    probability_html = (
        '<div style="display:grid;grid-template-columns:1fr 1fr;'
        'gap:2rem;margin:0.45rem 0 0.1rem;color:var(--swc-text-650);'
        'font-size:0.82rem;min-height:1.25rem;">'
        f"{probability_content}"
        "</div>"
    )
    return (
        '<div style="text-align:center;color:var(--swc-text-680);'
        'font-size:0.9rem;font-weight:600;'
        'margin:0.1rem 0 0.45rem;">'
        f"{html.escape(context_label)}"
        "</div>"
        '<div style="display:grid;'
        'grid-template-columns:1fr auto 1fr;'
        'align-items:center;gap:1rem;'
        'padding:0.1rem 0 0.2rem;">'
        '<div style="text-align:right;font-size:2.15rem;'
        'font-weight:800;line-height:1.1;">'
        f"{html.escape(player_1_name)}"
        "</div>"
        '<div style="color:var(--swc-text-550);font-size:0.9rem;'
        'font-weight:700;">VS</div>'
        '<div style="text-align:left;font-size:2.15rem;'
        'font-weight:800;line-height:1.1;">'
        f"{html.escape(player_2_name)}"
        "</div></div>"
        f"{probability_html}"
    )


def compact_score_input_styles(
    key_prefix: str,
    *,
    separate_stepper_buttons: bool = False,
) -> str:
    """Return shared styles for compact score number inputs."""

    selector = f'[class*="st-key-{key_prefix}"]'
    stepper_separators = (
        f"""
    {selector} div[data-baseweb="input"] button:first-of-type {{
        border-right: 1px solid rgba(128, 128, 128, 0.28);
    }}
    {selector} div[data-baseweb="input"] button:last-of-type {{
        border-left: 1px solid rgba(128, 128, 128, 0.28);
    }}
    """
        if separate_stepper_buttons
        else ""
    )
    return f"""
    <style>
    {selector} div[data-baseweb="input"] {{
        min-height: 3.55rem;
        overflow: hidden;
        border: 1px solid rgba(128, 128, 128, 0.42);
        border-radius: 0.65rem;
        background: var(--swc-surface);
        box-shadow:
            0 1px 2px rgba(0, 0, 0, 0.25),
            0 6px 18px rgba(0, 0, 0, 0.08);
        transition:
            border-color 0.15s ease,
            box-shadow 0.15s ease;
    }}
    {selector} div[data-baseweb="input"]:focus-within {{
        border-color: var(--primary-color, rgb(255, 75, 75));
        box-shadow:
            0 0 0 2px rgba(96, 165, 250, 0.22),
            0 8px 24px rgba(59, 130, 246, 0.18);
    }}
    {selector} input {{
        padding: 0 !important;
        color: var(--swc-text) !important;
        font-size: 1.55rem !important;
        font-weight: 800 !important;
        text-align: center !important;
    }}
    {selector} div[data-baseweb="input"] button {{
        width: 3.25rem;
        min-width: 3.25rem;
        border-radius: 0;
        color: var(--swc-text-680);
        transition:
            background-color 0.15s ease,
            color 0.15s ease;
    }}
    {selector} div[data-baseweb="input"] button:hover {{
        background: rgba(59, 130, 246, 0.12);
        color: var(--swc-text);
    }}
    {stepper_separators}
    {selector} label p {{
        color: var(--swc-text-680);
        font-size: 0.82rem;
        font-weight: 650;
    }}
    </style>
    """


MOBILE_CARD_ROLES = ("rank", "title", "aside", "stat", "wide")
MOBILE_CARD_RANK_WIDTH = "3.4rem"


def mobile_card_layout(
    roles: Sequence[str],
    *,
    stat_columns: int | None = None,
) -> dict[str, Any]:
    """Place each table column on a phone card according to its role.

    ``rank`` sits in a narrow left column beside the title, ``title`` and
    ``aside`` share the first row (``aside`` right-aligned), ``stat`` cells
    follow two or three per row and ``wide`` takes a row of its own. A card
    with exactly two stats and nothing else beside the title keeps them in
    the title row, right-aligned. Returns the card grid columns and, per table
    column, its grid column and row and whether it is right-aligned.
    """

    unknown = sorted(set(roles) - set(MOBILE_CARD_ROLES))
    if unknown:
        raise ValueError(f"Unknown mobile card role: {', '.join(unknown)}")
    for single_role in ("rank", "title", "aside"):
        if list(roles).count(single_role) > 1:
            raise ValueError(f"Use the mobile card role {single_role} once.")

    stat_count = list(roles).count("stat")
    content_columns = stat_columns or min(3, max(2, stat_count))
    if not 1 <= content_columns <= 4:
        raise ValueError("Mobile card stat columns must be from 1 to 4.")
    offset = 1 if "rank" in roles else 0
    first = offset + 1
    if (
        stat_columns is None
        and stat_count == 2
        and set(roles) <= {"rank", "title", "stat"}
    ):
        return _single_row_card_layout(roles, offset)
    end = offset + content_columns + 1

    placements: list[dict[str, Any]] = [{} for _ in roles]
    has_aside = "aside" in roles
    if "title" in roles:
        placements[list(roles).index("title")] = {
            "column": f"{first} / {end - 1 if has_aside else end}",
            "row": "1",
            "end": False,
        }
    if has_aside:
        placements[list(roles).index("aside")] = {
            "column": f"{end - 1} / {end}",
            "row": "1",
            "end": True,
        }

    row = 2 if "title" in roles or has_aside else 1
    position = 0
    for index, role in enumerate(roles):
        if role == "stat":
            if position == content_columns:
                row += 1
                position = 0
            column = first + position
            placements[index] = {
                "column": f"{column} / {column + 1}",
                "row": str(row),
                "end": content_columns > 1
                and position == content_columns - 1,
            }
            position += 1
        elif role == "wide":
            if position:
                row += 1
            placements[index] = {
                "column": f"{first} / {end}",
                "row": str(row),
                "end": False,
            }
            row += 1
            position = 0

    if "rank" in roles:
        placements[list(roles).index("rank")] = {
            "column": "1 / 2",
            "row": "1",
            "end": False,
        }
    # The right-hand column only takes the width its values need, which
    # leaves the title as much room as possible.
    grid = (
        f"repeat({content_columns - 1}, minmax(0, 1fr)) auto"
        if content_columns > 1
        else "minmax(0, 1fr)"
    )
    if offset:
        grid = f"{MOBILE_CARD_RANK_WIDTH} {grid}"
    return {"grid_columns": grid, "placements": placements}


def _single_row_card_layout(roles: Sequence[str], offset: int) -> dict[str, Any]:
    """Put the title and two stats side by side in one card row."""

    placements: list[dict[str, Any]] = []
    next_stat = offset + 2
    for role in roles:
        if role == "rank":
            column, end = 1, False
        elif role == "title":
            column, end = offset + 1, False
        else:
            column, end = next_stat, True
            next_stat += 1
        placements.append(
            {"column": f"{column} / {column + 1}", "row": "1", "end": end}
        )
    grid = "minmax(0, 1fr) auto auto"
    if offset:
        grid = f"{MOBILE_CARD_RANK_WIDTH} {grid}"
    return {"grid_columns": grid, "placements": placements}


def dashboard_table_html(
    headers: list[str],
    rows: list[list[str]],
    *,
    columns: str,
    row_highlights: dict[int, str] | None = None,
    emphasis_column: int | None = None,
    cell_links: dict[tuple[int, int], str] | None = None,
    cell_html: dict[tuple[int, int], str] | None = None,
    mobile_cards: bool = False,
    mobile_visible_rows: int | None = None,
    mobile_summary: str = "Show all",
    mobile_roles: Sequence[str] | None = None,
    mobile_stat_columns: int | None = None,
    visible_rows: int | None = None,
    more_summary: str = "Show all",
) -> str:
    """Return markup for a compact table in the dashboard visual language.

    The table relies on ``dashboard_table_styles()``, which the dashboard
    loads once per page.

    ``visible_rows`` keeps only the first rows visible on every screen size;
    the remaining rows open in place below them via ``more_summary``.
    ``cell_html`` replaces single cells with ready markup; callers escape any
    text in it themselves.

    ``mobile_roles`` turns rows into cards on narrow containers and names the
    role of each column (see ``mobile_card_layout``); ``mobile_cards`` alone
    keeps a plain two-column card.
    """

    card_layout = None
    if mobile_roles is not None:
        if len(mobile_roles) != len(headers):
            raise ValueError("Give one mobile card role per column.")
        card_layout = mobile_card_layout(
            mobile_roles,
            stat_columns=mobile_stat_columns,
        )
        mobile_cards = True
    row_highlights = row_highlights or {}
    cell_links = cell_links or {}
    cell_html = cell_html or {}
    header_html = "".join(
        f"<div>{html.escape(header)}</div>" for header in headers
    )
    row_html = []
    for row_index, row in enumerate(rows):
        cells = []
        for column_index, value in enumerate(row):
            value_text = str(value)
            emphasis_class = (
                " control-table-emphasis"
                if column_index == emphasis_column
                else ""
            )
            movement_class = (
                " control-table-positive"
                if value_text.startswith("▲")
                else (
                    " control-table-negative"
                    if value_text.startswith("▼")
                    else ""
                )
            )
            cell_content = html.escape(value_text)
            cell_link = cell_links.get((row_index, column_index))
            if cell_link is not None:
                link_text = str(cell_link)
                if not (
                    link_text.startswith("?")
                    or (
                        link_text.startswith("/")
                        and not link_text.startswith("//")
                    )
                ):
                    raise ValueError(
                        "Dashboard table links must be internal query URLs."
                    )
                cell_content = internal_dashboard_link(value_text, link_text)
            if (row_index, column_index) in cell_html:
                cell_content = cell_html[(row_index, column_index)]
            card_class = ""
            card_style = ""
            if card_layout is not None:
                placement = card_layout["placements"][column_index]
                card_class = (
                    f" control-table-card-{mobile_roles[column_index]}"
                    + (" control-table-card-end" if placement["end"] else "")
                    + (" control-table-card-lead" if placement["row"] == "1" else "")
                )
                card_style = (
                    f' style="--card-column:{placement["column"]};'
                    f'--card-row:{placement["row"]};"'
                )
            cells.append(
                f'<div class="control-table-cell{emphasis_class}'
                f'{movement_class}{card_class}"{card_style} '
                f'data-label="{html.escape(headers[column_index], quote=True)}">'
                f"{cell_content}</div>"
            )
        highlight = row_highlights.get(row_index)
        highlight_class = (
            f" control-table-row-{highlight}" if highlight else ""
        )
        collapsed_class = (
            " control-table-mobile-collapsed"
            if mobile_visible_rows is not None
            and row_index >= mobile_visible_rows
            else ""
        )
        row_html.append(
            f'<div class="control-table-row{highlight_class}'
            f'{collapsed_class}">'
            f"{''.join(cells)}</div>"
        )

    if mobile_visible_rows is not None and mobile_visible_rows < 1:
        raise ValueError("Mobile visible rows must be positive.")
    if visible_rows is not None and visible_rows < 1:
        raise ValueError("Visible rows must be positive.")
    if visible_rows is not None and mobile_visible_rows is not None:
        raise ValueError("Use either visible_rows or mobile_visible_rows.")
    more_html = (
        '<details class="control-table-more">'
        "<summary>"
        '<span class="control-table-show-more">'
        f"{html.escape(more_summary)}"
        "</span>"
        '<span class="control-table-show-less">Show less</span>'
        "</summary>"
        '<div class="control-table-more-rows">'
        f"{''.join(row_html[visible_rows:])}"
        "</div></details>"
        if visible_rows is not None and len(row_html) > visible_rows
        else ""
    )
    if more_html:
        row_html = row_html[:visible_rows]
    hidden_mobile_rows = (
        row_html[mobile_visible_rows:]
        if mobile_cards
        and mobile_visible_rows is not None
        and len(row_html) > mobile_visible_rows
        else []
    )
    mobile_more_html = (
        '<details class="control-table-mobile-more">'
        "<summary>"
        '<span class="control-table-show-more">'
        f"{html.escape(mobile_summary)}"
        "</span>"
        '<span class="control-table-show-less">Show less</span>'
        "</summary>"
        '<div class="control-table-mobile-more-rows">'
        f"{''.join(hidden_mobile_rows)}"
        "</div></details>"
        if hidden_mobile_rows
        else ""
    )
    table_classes = "control-table"
    table_style = f"--control-table-columns:{html.escape(columns)};"
    if mobile_cards:
        table_classes += " control-table-mobile-cards"
    if card_layout is not None:
        table_classes += " control-table-mobile-roles"
        table_style += f"--card-columns:{card_layout['grid_columns']};"

    return (
        '<div class="control-table-scroll">'
        f'<div class="{table_classes}" style="{table_style}">'
        f'<div class="control-table-header">{header_html}</div>'
        f"{''.join(row_html)}"
        f"{more_html}"
        f"{mobile_more_html}"
        "</div></div>"
    )


def dashboard_table_styles() -> str:
    """Return the shared style sheet for dashboard_table_html markup.

    The dashboard injects it once per page run, so tables do not repeat it.
    Mobile cards follow the width available to the table (a container
    query), not the window width, so an open sidebar cannot squeeze the
    desktop grid; a table that is still too wide scrolls instead of being
    clipped.
    """

    return """
        <style>
        .control-table-scroll {
            container-type: inline-size;
            overflow-x: auto;
        }
        .control-table {
            min-width: min-content;
            overflow: hidden;
            border: 1px solid rgba(128, 128, 128, 0.30);
            border-radius: 0.8rem;
        }
        .control-table-header,
        .control-table-row {
            display: grid;
            grid-template-columns: var(--control-table-columns);
            align-items: center;
            gap: 0.8rem;
            padding: 0.7rem 1rem;
        }
        .control-table-header {
            min-height: 2.6rem;
            border-bottom: 1px solid rgba(128, 128, 128, 0.24);
            background: rgba(128, 128, 128, 0.08);
            color: var(--swc-text-550);
            font-size: 0.72rem;
            font-weight: 750;
            letter-spacing: 0.035em;
            text-transform: uppercase;
        }
        .control-table-row {
            min-height: 3.65rem;
            border-bottom: 1px solid rgba(128, 128, 128, 0.20);
            transition: background-color 0.15s ease;
        }
        .control-table-row:last-child {
            border-bottom: none;
        }
        .control-table-row:hover {
            background: rgba(128, 128, 128, 0.055);
        }
        .control-table-row-winners {
            background: rgba(34, 197, 94, 0.07);
        }
        .control-table-row-losers {
            background: rgba(245, 158, 11, 0.07);
        }
        .control-table-row-participated {
            background: rgba(59, 130, 246, 0.055);
            box-shadow: inset 3px 0 rgba(96, 165, 250, 0.48);
        }
        .control-table-row-champion {
            background: rgba(234, 179, 8, 0.065);
            box-shadow: inset 3px 0 rgba(250, 204, 21, 0.48);
        }
        .control-table-bar {
            display: block;
            height: 0.32rem;
            margin-top: 0.35rem;
            overflow: hidden;
            border-radius: 999px;
            background: rgba(128, 128, 128, 0.22);
        }
        .control-table-bar-fill {
            height: 100%;
            border-radius: 999px;
        }
        .control-table-cell {
            min-width: 0;
            overflow: hidden;
            color: var(--swc-text-760);
            font-size: 0.88rem;
            font-weight: 650;
            text-overflow: ellipsis;
            white-space: nowrap;
        }
        .control-table-emphasis {
            color: var(--swc-text);
            font-size: 1.02rem;
            font-weight: 800;
        }
        .control-table-strong {
            color: var(--swc-text);
            font-weight: 800;
        }
        .control-table-regular {
            font-weight: 500;
        }
        .control-table-muted {
            color: var(--swc-text-580);
            font-size: 0.92em;
            font-weight: 600;
        }
        .control-table-nowrap {
            white-space: nowrap;
        }
        .control-table-subline {
            display: block;
            margin-top: 0.15rem;
            color: var(--swc-text-580);
            font-size: 0.78rem;
            font-weight: 600;
            line-height: 1.3;
        }
        .control-table-link,
        .control-table-link:link,
        .control-table-link:visited {
            color: inherit !important;
            font-weight: inherit;
            text-decoration: none !important;
        }
        .control-table-link {
            display: inline-block;
            transition: opacity 0.15s ease, transform 0.15s ease;
        }
        .control-table-link:hover {
            opacity: 0.72;
            transform: translateX(3px);
        }
        .control-table-link:focus-visible {
            border-radius: 0.25rem;
            outline: 2px solid var(--primary-color, rgb(255, 75, 75));
            outline-offset: 3px;
        }
        .control-table-positive {
            color: var(--swc-positive-bright);
        }
        .control-table-negative {
            color: var(--swc-negative-soft);
        }
        @container (max-width: 700px) {
            .control-table-mobile-cards {
                min-width: 0;
                overflow: visible;
                border: none;
                border-radius: 0;
            }
            .control-table-mobile-cards .control-table-header {
                display: none;
            }
            .control-table-mobile-cards .control-table-row {
                grid-template-columns: repeat(2, minmax(0, 1fr));
                gap: 0.75rem 1rem;
                min-height: 0;
                margin-bottom: 0.75rem;
                padding: 0.9rem 1rem;
                border: 1px solid rgba(128, 128, 128, 0.30);
                border-radius: 0.8rem;
                background: var(--swc-surface);
            }
            .control-table-mobile-cards .control-table-row-winners {
                background: rgba(34, 197, 94, 0.07);
                box-shadow: inset 3px 0 rgba(74, 222, 128, 0.42);
            }
            .control-table-mobile-cards .control-table-row-champion {
                background: rgba(234, 179, 8, 0.065);
                box-shadow: inset 3px 0 rgba(250, 204, 21, 0.48);
            }
            .control-table-mobile-cards .control-table-row:last-child {
                margin-bottom: 0;
                border-bottom: 1px solid rgba(128, 128, 128, 0.30);
            }
            .control-table-mobile-cards .control-table-cell {
                display: flex;
                flex-direction: column;
                gap: 0.18rem;
                overflow: visible;
                font-size: 0.9rem;
                text-overflow: clip;
                white-space: normal;
            }
            .control-table-mobile-cards .control-table-cell::before {
                content: attr(data-label);
                color: var(--swc-text-520);
                font-size: 0.72rem;
                font-weight: 750;
                letter-spacing: 0.035em;
                text-transform: uppercase;
            }
            .control-table-mobile-cards .control-table-emphasis {
                grid-column: 1 / -1;
                font-size: 1.12rem;
            }
            .control-table-mobile-cards > .control-table-mobile-collapsed {
                display: none;
            }
            .control-table-mobile-more {
                margin-top: 0.15rem;
            }
            .control-table-mobile-more summary {
                padding: 0.9rem 1rem;
                border: 1px solid rgba(128, 128, 128, 0.30);
                border-radius: 0.8rem;
                background: rgba(128, 128, 128, 0.055);
                color: var(--swc-text-820);
                font-size: 0.86rem;
                font-weight: 750;
                cursor: pointer;
            }
            .control-table-mobile-more[open] summary {
                order: 2;
                margin-top: 0.15rem;
            }
            .control-table-mobile-more[open] {
                display: flex;
                flex-direction: column;
            }
            .control-table-mobile-more-rows {
                padding: 0;
            }
            .control-table-show-less {
                display: none;
            }
            .control-table-mobile-more[open]
            .control-table-show-more {
                display: none;
            }
            .control-table-mobile-more[open]
            .control-table-show-less {
                display: inline;
            }
            .control-table-mobile-more-rows .control-table-row {
                display: grid;
            }
            .control-table-mobile-roles .control-table-row {
                grid-template-columns: var(--card-columns);
                align-items: start;
                gap: 0.65rem 0.8rem;
                padding: 0.85rem 0.95rem;
            }
            .control-table-mobile-roles
            .control-table-row > .control-table-cell {
                grid-column: var(--card-column);
                grid-row: var(--card-row);
            }
            .control-table-mobile-roles .control-table-card-rank {
                color: var(--swc-text-780);
                font-size: 1.1rem;
                font-weight: 800;
            }
            .control-table-mobile-roles .control-table-card-title {
                color: var(--swc-text);
                font-size: 1.2rem;
                font-weight: 800;
                line-height: 1.2;
            }
            .control-table-mobile-roles .control-table-card-rank::before,
            .control-table-mobile-roles .control-table-card-title::before {
                content: none;
            }
            .control-table-mobile-roles .control-table-card-lead {
                align-self: center;
            }
            .control-table-mobile-roles .control-table-card-aside,
            .control-table-mobile-roles .control-table-card-end {
                align-items: flex-end;
                text-align: right;
            }
        }
        .control-table-more summary {
            display: flex;
            justify-content: center;
            padding: 0.65rem 1rem;
            background: rgba(128, 128, 128, 0.035);
            color: var(--swc-text-760);
            font-size: 0.82rem;
            font-weight: 750;
            cursor: pointer;
            list-style: none;
        }
        .control-table-more summary::-webkit-details-marker {
            display: none;
        }
        .control-table-more summary:hover {
            background: rgba(128, 128, 128, 0.075);
        }
        .control-table-more[open] {
            display: flex;
            flex-direction: column;
        }
        .control-table-more[open] summary {
            order: 2;
            border-top: 1px solid rgba(128, 128, 128, 0.20);
        }
        .control-table-more .control-table-show-less,
        .control-table-more[open] .control-table-show-more {
            display: none;
        }
        .control-table-more[open] .control-table-show-less {
            display: inline;
        }
        @container (max-width: 700px) {
            .control-table-mobile-cards .control-table-more summary {
                justify-content: flex-start;
                padding: 0.9rem 1rem;
                border: 1px solid rgba(128, 128, 128, 0.30);
                border-radius: 0.8rem;
                background: rgba(128, 128, 128, 0.055);
                color: var(--swc-text-820);
                font-size: 0.86rem;
            }
            .control-table-mobile-cards .control-table-more[open] summary {
                margin-top: 0.75rem;
            }
        }
        @container (min-width: 701px) {
            .control-table-mobile-more {
                display: none;
            }
        }
        </style>
    """


def narrative_paragraphs_html(text: str) -> str:
    """Split a narrative into escaped paragraphs of two sentences each."""

    sentences = [sentence.strip() for sentence in text.split(". ") if sentence.strip()]
    paragraphs = []
    for index in range(0, len(sentences), 2):
        paragraph = ". ".join(sentences[index:index + 2])
        if not paragraph.endswith("."):
            paragraph += "."
        paragraphs.append(f"<p>{html.escape(paragraph)}</p>")
    return "".join(paragraphs)


def summary_box_html(
    label_html: str,
    text_html: str,
    *,
    attached: bool = False,
) -> str:
    """Return the blue text box with a label column, used for narratives.

    ``attached`` joins the box to the card directly above it.
    """

    box_class = "dash-summary dash-summary-attached" if attached else "dash-summary"
    return (
        f'<div class="{box_class}">'
        f'<div class="dash-summary-label">{label_html}</div>'
        f'<div class="dash-summary-text">{text_html}</div>'
        "</div>"
    )


def summary_box_styles() -> str:
    """Return the style sheet for summary_box_html.

    The dashboard injects it once per page run, like the table styles.
    """

    return """
        <style>
        .dash-summary {
            display: grid;
            grid-template-columns: 9rem minmax(0, 1fr);
            gap: 2rem;
            align-items: start;
            margin: 0.35rem 0 1rem;
            padding: 1.5rem 1.7rem;
            border: 1px solid rgba(70, 150, 220, 0.18);
            border-radius: 0.8rem;
            background: var(--swc-summary-bg);
        }
        .dash-summary-attached {
            grid-template-columns: 7rem minmax(0, 1fr);
            gap: 1.5rem;
            margin-top: 0;
            padding: 1.25rem 1.45rem;
            border-top: none;
            border-radius: 0 0 0.8rem 0.8rem;
        }
        .dash-summary-label {
            padding-top: 0.15rem;
            color: var(--swc-text-720);
            font-size: 0.78rem;
            font-weight: 750;
            letter-spacing: 0.04em;
            text-transform: uppercase;
        }
        .dash-summary-text {
            font-size: 1rem;
            line-height: 1.75;
        }
        .dash-summary-text p {
            margin: 0 0 0.9rem 0;
        }
        .dash-summary-text p:last-child {
            margin-bottom: 0 !important;
        }
        @media (max-width: 800px) {
            .dash-summary {
                grid-template-columns: 1fr;
                gap: 0.75rem;
                padding: 1.25rem 1.4rem;
            }
        }
        </style>
    """


def clickable_card_button_styles(
    key_prefix: str,
    *,
    title_font_size: str = "1.25rem",
    show_focus_ring: bool = False,
) -> str:
    """Return shared styles for Streamlit buttons presented as cards."""

    selector = f'[class*="st-key-{key_prefix}"]'
    focus_shadow = (
        "0 0 0 2px rgba(96, 165, 250, 0.22),\n"
        "            0 8px 24px rgba(59, 130, 246, 0.18)"
        if show_focus_ring
        else (
            "0 2px 5px rgba(0, 0, 0, 0.32),\n"
            "            0 8px 24px rgba(59, 130, 246, 0.18)"
        )
    )
    return f"""
    <style>
    {selector} button {{
        min-height: 4.35rem;
        padding: 0.65rem 0.9rem;
        text-align: left;
        transition:
            border-color 0.15s ease,
            box-shadow 0.15s ease,
            transform 0.15s ease;
    }}
    {selector} button:hover {{
        border-color: var(--primary-color, rgb(255, 75, 75));
        box-shadow:
            0 2px 5px rgba(0, 0, 0, 0.32),
            0 8px 24px rgba(59, 130, 246, 0.18);
        transform: translateY(-1px);
    }}
    {selector} button:focus-visible {{
        border-color: var(--primary-color, rgb(255, 75, 75));
        box-shadow:
            {focus_shadow};
        transform: translateY(-1px);
    }}
    {selector} button p {{
        width: 100%;
        color: var(--swc-text-580);
        font-size: 0.78rem;
        line-height: 1.25;
        text-align: left;
    }}
    {selector} button strong {{
        display: block;
        margin-bottom: 0.2rem;
        color: var(--swc-text);
        font-size: {title_font_size};
        line-height: 1.2;
    }}
    </style>
    """


def selector_card_styles(container_key: str, value_font_size: str) -> str:
    """Return the styles for a prominent page-level selectbox.

    The selectbox sits in ``st.container(key=container_key)``;
    ``value_font_size`` sets the size of the selected value. The field keeps
    Streamlit's own background so it reads as a dropdown, and gains a taller
    outlined shape with hover and focus states. It is reached through its
    ARIA roles (``group`` field, ``combobox`` input) rather than generated
    classes; if a Streamlit update changes them, the default selectbox
    remains.
    """

    return f"""
    <style>
    div[class*="st-key-{container_key}"] {{
        margin-bottom: 0.85rem;
    }}
    div[class*="st-key-{container_key}"] label p {{
        color: var(--swc-text-720);
        font-size: 0.82rem !important;
        font-weight: 750 !important;
    }}
    div[class*="st-key-{container_key}"] [role="group"] {{
        min-height: 3.4rem;
        border: 1px solid rgba(128, 128, 128, 0.30) !important;
        border-radius: 0.7rem !important;
        transition: border-color 0.15s ease, box-shadow 0.15s ease;
    }}
    div[class*="st-key-{container_key}"] [role="group"]:hover {{
        border-color: rgba(128, 128, 128, 0.55) !important;
    }}
    div[class*="st-key-{container_key}"] [role="group"]:focus-within {{
        border-color: var(--primary-color, rgb(255, 75, 75)) !important;
        box-shadow: 0 0 0 2px rgba(96, 165, 250, 0.18) !important;
    }}
    div[class*="st-key-{container_key}"] [role="combobox"] {{
        padding-left: 0.9rem !important;
        font-size: {value_font_size} !important;
        font-weight: 800 !important;
        line-height: 1.2 !important;
    }}
    </style>
    """
