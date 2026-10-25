"""Shared colors for custom HTML components in both Streamlit themes."""


def dashboard_theme_css() -> str:
    """Follow the active app color-scheme, including client-side theme switches."""
    return """
    <style>
    .stApp {
        --swc-text: light-dark(#31333f, #fafafa);
        --swc-text-240: light-dark(#59616e, rgba(250, 250, 250, 0.24));
        --swc-text-480: light-dark(#59616e, rgba(250, 250, 250, 0.48));
        --swc-text-520: light-dark(#59616e, rgba(250, 250, 250, 0.52));
        --swc-text-550: light-dark(#59616e, rgba(250, 250, 250, 0.55));
        --swc-text-580: light-dark(#59616e, rgba(250, 250, 250, 0.58));
        --swc-text-600: light-dark(#59616e, rgba(250, 250, 250, 0.6));
        --swc-text-660: light-dark(#59616e, rgba(250, 250, 250, 0.66));
        --swc-text-680: light-dark(#59616e, rgba(250, 250, 250, 0.68));
        --swc-text-720: light-dark(#31333f, rgba(250, 250, 250, 0.72));
        --swc-text-760: light-dark(#31333f, rgba(250, 250, 250, 0.76));
        --swc-text-780: light-dark(#31333f, rgba(250, 250, 250, 0.78));
        --swc-text-820: light-dark(#31333f, rgba(250, 250, 250, 0.82));
        --swc-text-620: light-dark(#59616e, rgba(250, 250, 250, 0.62));
        --swc-text-650: light-dark(#59616e, rgba(250, 250, 250, 0.65));
        --swc-surface: light-dark(#f8fafc, rgba(255, 255, 255, 0.018));
        --swc-summary-bg: light-dark(#eff6ff, rgba(28, 74, 112, 0.55));
        --swc-gold: light-dark(#916000, #f2c94c);
        --swc-blue: light-dark(#1d5c98, #5b9bd5);
        --swc-chart-blue: light-dark(#1d5c98, #83c9ff);
        --swc-chart-bar: light-dark(#2463a6, #58a6ff);
        --swc-silver: light-dark(#5b687c, #b8c1cc);
        --swc-bronze: light-dark(#875522, #c98952);
        --swc-positive: light-dark(#166534, #3fb950);
        --swc-positive-bright: light-dark(#166534, #4ade80);
        --swc-negative: light-dark(#b42318, #f85149);
        --swc-negative-soft: light-dark(#b42318, #f87171);
        --swc-neutral: light-dark(#59616e, rgba(255, 255, 255, 0.48));
    }
    [data-testid="stVegaLiteChart"] svg text {
        fill: var(--swc-text-680);
    }
    [data-testid="stVegaLiteChart"] svg .role-mark.mark-text text {
        fill: var(--swc-text);
    }
    [data-testid="stVegaLiteChart"] svg [stroke="#83c9ff" i] {
        stroke: var(--swc-chart-blue);
    }
    [data-testid="stVegaLiteChart"] svg [fill="#83c9ff" i] {
        fill: var(--swc-chart-blue);
    }
    [data-testid="stVegaLiteChart"] svg [stroke="#f2c94c" i] {
        stroke: var(--swc-gold);
    }
    [data-testid="stVegaLiteChart"] svg [fill="#f2c94c" i] {
        fill: var(--swc-gold);
    }
    [data-testid="stVegaLiteChart"] svg [fill="#b8c1cc" i] {
        fill: var(--swc-silver);
    }
    [data-testid="stVegaLiteChart"] svg [fill="#c98952" i] {
        fill: var(--swc-bronze);
    }
    [data-testid="stVegaLiteChart"] svg [fill="#58a6ff" i] {
        fill: var(--swc-chart-bar);
    }
    </style>
    """
