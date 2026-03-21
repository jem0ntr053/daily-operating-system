"""Streamlit web UI for dayctl — Daily Operating System."""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import streamlit as st

# Ensure the package is importable
sys.path.insert(0, str(Path(__file__).parent / "src"))

from dayctl.models import (
    DayPlan, NON_NEGOTIABLE_KEYS, SCHEDULE_PROFILES, SHOW_TOGGLE,
    score_plan, profile_for_date, compute_streak, carry_forward,
)
from dayctl.storage import load_plan, save_plan, plan_path, list_days, load_config, save_config
from dayctl.web_themes import WEB_THEMES, DEFAULT_WEB_THEME


# ---------------------------------------------------------------------------
# Theme
# ---------------------------------------------------------------------------

def get_web_theme() -> dict[str, str]:
    config = load_config()
    name = config.get("theme", DEFAULT_WEB_THEME)
    return WEB_THEMES.get(name, WEB_THEMES[DEFAULT_WEB_THEME])


def inject_css(t: dict[str, str]) -> None:
    st.markdown(f"""
    <style>
        .stApp {{
            background-color: {t['bg']};
            color: {t['fg']};
        }}
        .stSidebar > div {{
            background-color: {t['surface']};
        }}
        h1, h2, h3 {{
            color: {t['heading']} !important;
        }}

        /* Schedule — tighter spacing */
        .schedule-item {{
            padding: 0.12rem 0;
            border-bottom: 1px solid {t['surface']};
            font-family: monospace;
            font-size: 0.85rem;
            line-height: 1.4;
        }}
        .schedule-time {{
            color: {t['muted']};
        }}

        /* Non-negotiable toggle cards */
        .nn-card {{
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 0.5rem;
            padding: 0.75rem 0.5rem;
            border-radius: 0.5rem;
            font-weight: bold;
            font-size: 0.95rem;
            letter-spacing: 0.03em;
            cursor: pointer;
            transition: all 0.15s ease;
            border: 2px solid transparent;
        }}
        .nn-card.done {{
            background: {t['green']}18;
            border-color: {t['green']}60;
            color: {t['green']};
        }}
        .nn-card.pending {{
            background: {t['surface']};
            border-color: {t['muted']}40;
            color: {t['muted']};
        }}
        .nn-card .nn-icon {{
            font-size: 1.1rem;
        }}

        /* Score progress bar */
        .score-bar-container {{
            display: flex;
            align-items: center;
            gap: 0.75rem;
            margin-bottom: 0.75rem;
        }}
        .score-bar-track {{
            flex: 1;
            height: 8px;
            background: {t['surface']};
            border-radius: 4px;
            overflow: hidden;
        }}
        .score-bar-fill {{
            height: 100%;
            border-radius: 4px;
            transition: width 0.3s ease;
        }}
        .score-label {{
            font-size: 1.3rem;
            font-weight: bold;
            min-width: 3rem;
            text-align: right;
        }}

        /* Subtle +/- buttons (default for all buttons) */
        div[data-testid="stButton"] > button {{
            background: transparent !important;
            border: 1px solid {t['muted']}40 !important;
            color: {t['muted']} !important;
            font-size: 1rem !important;
            padding: 0.15rem 0.5rem !important;
            min-height: 0 !important;
            transition: all 0.15s ease;
        }}
        div[data-testid="stButton"] > button:hover {{
            border-color: {t['accent']} !important;
            color: {t['accent']} !important;
            background: {t['accent']}15 !important;
        }}

        /* Non-negotiable toggle buttons — override default button style */
        div[data-testid="stButton"] > button[kind="secondary"]:has(> div > p) {{
            padding: 0.75rem 0.5rem !important;
            font-weight: bold !important;
            font-size: 0.95rem !important;
            letter-spacing: 0.03em !important;
            min-height: 2.5rem !important;
        }}

        /* Section headers with subtle underline */
        .section-header {{
            color: {t['heading']};
            font-size: 1.1rem;
            font-weight: 600;
            padding-bottom: 0.3rem;
            margin-bottom: 0.5rem;
            border-bottom: 1px solid {t['muted']}30;
        }}

        /* Hide default checkbox styling for NN (we use custom cards) */
        .nn-hidden-checkbox {{
            position: absolute;
            opacity: 0;
            pointer-events: none;
            height: 0;
            overflow: hidden;
        }}

        div[data-testid="stCheckbox"] label span {{
            color: {t['fg']} !important;
        }}
    </style>
    """, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def format_date_display(day_str: str) -> str:
    d = date.fromisoformat(day_str)
    return d.strftime("%A, %B %d, %Y")


def score_color(s: int, t: dict[str, str]) -> str:
    if s == 4:
        return t["green"]
    elif s >= 2:
        return t["yellow"]
    return t["red"]


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

def main() -> None:
    st.set_page_config(
        page_title="Daily OS",
        page_icon="●",
        layout="wide",
    )

    t = get_web_theme()
    inject_css(t)

    # --- Sidebar ---
    with st.sidebar:
        st.markdown(f"<h2 style='color:{t['accent']}'>Daily OS</h2>", unsafe_allow_html=True)

        # Date picker
        selected_date = st.date_input("Date", value=date.today())
        day_str = selected_date.isoformat()

        st.divider()

        # Profile override
        auto_profile = profile_for_date(day_str)
        profile_names = list(SCHEDULE_PROFILES.keys())
        # Detect current profile (single load for the entire sidebar)
        if plan_path(day_str).exists():
            plan = load_plan(day_str)
            current_key = getattr(plan, "profile", None)
        else:
            plan = None
            current_key = None

        auto_key = next(k for k, v in SCHEDULE_PROFILES.items() if v == auto_profile)
        default_idx = profile_names.index(current_key) if current_key and current_key in profile_names else profile_names.index(auto_key)

        profile_key = st.selectbox(
            "Schedule Profile",
            profile_names,
            index=default_idx,
            format_func=lambda k: SCHEDULE_PROFILES[k]["label"],
        )

        # Show tonight toggle (only on Fri/Sat)
        selected_dow = date.fromisoformat(day_str).weekday()
        if selected_dow in (4, 5):  # Friday or Saturday
            is_show = profile_key in ("friday_show", "saturday_show")
            show_toggle = st.toggle("Playing a show tonight?", value=is_show, key=f"show_{day_str}")
            if show_toggle and not is_show:
                profile_key = SHOW_TOGGLE.get(profile_key, profile_key)
            elif not show_toggle and is_show:
                profile_key = SHOW_TOGGLE.get(profile_key, profile_key)

        # Init / reinit (preserve user data on profile switch)
        if plan is None:
            plan = DayPlan.new(day_str, profile_key=profile_key)
            # Carry forward incomplete tasks from previous day
            yesterday = (date.fromisoformat(day_str) - timedelta(days=1)).isoformat()
            if plan_path(yesterday).exists():
                prev = load_plan(yesterday)
                carry_forward(plan, prev)
            save_plan(plan)
        elif plan.profile != profile_key:
            plan.switch_profile(profile_key)
            save_plan(plan)

        st.divider()

        # Theme picker
        config = load_config()
        theme_name = st.selectbox(
            "Theme",
            list(WEB_THEMES.keys()),
            index=list(WEB_THEMES.keys()).index(
                config.get("theme", DEFAULT_WEB_THEME)
            ),
        )
        if config.get("theme") != theme_name:
            config["theme"] = theme_name
            save_config(config)
            st.rerun()

    # --- Header ---
    st.markdown(
        f"<h1 style='margin-bottom:0'>{format_date_display(day_str)}</h1>"
        f"<p style='color:{t['accent']};font-size:1.1rem;margin-top:0'>"
        f"{SCHEDULE_PROFILES[plan.profile]['label']} · "
        f"Fasting: {plan.fasting_window}</p>",
        unsafe_allow_html=True,
    )

    st.divider()

    # --- Main layout: two columns ---
    left, right = st.columns([1, 1], gap="large")

    with left:
        # --- Schedule (collapsible) ---
        with st.expander("Schedule", expanded=False):
            for item in plan.schedule:
                parts = item.split("  ", 1)
                if len(parts) == 2:
                    time_part, activity = parts
                    st.markdown(
                        f"<div class='schedule-item'>"
                        f"<span class='schedule-time'>{time_part}</span> &nbsp; {activity}"
                        f"</div>",
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(f"<div class='schedule-item'>{item}</div>", unsafe_allow_html=True)

        st.markdown("<div style='margin-top:1.5rem'></div>", unsafe_allow_html=True)

        # --- Weekly Summary ---
        st.markdown(f"<div class='section-header'>Week Summary</div>", unsafe_allow_html=True)
        _render_week_summary(day_str, t)

        st.markdown("<div style='margin-top:1.5rem'></div>", unsafe_allow_html=True)

        # --- Streak ---
        _render_streak(t)

        st.markdown("<div style='margin-top:1.5rem'></div>", unsafe_allow_html=True)

        # --- Weekly Trend ---
        _render_weekly_trend(day_str, t)

        st.markdown("<div style='margin-top:1.5rem'></div>", unsafe_allow_html=True)

        # --- Notes ---
        st.markdown(f"<div class='section-header'>Notes</div>", unsafe_allow_html=True)
        _render_notes(plan, day_str)

    with right:
        # --- Score bar + Non-negotiables ---
        s = score_plan(plan)
        sc = score_color(s, t)
        pct = int(s / 4 * 100)
        st.markdown(
            f"<div class='score-bar-container'>"
            f"<div class='score-bar-track'>"
            f"<div class='score-bar-fill' style='width:{pct}%;background:{sc}'></div>"
            f"</div>"
            f"<div class='score-label' style='color:{sc}'>{s}/4</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

        nn_cols = st.columns(4)
        for i, key in enumerate(NON_NEGOTIABLE_KEYS):
            with nn_cols[i]:
                done = plan.completed[key]
                icon = "✓" if done else "○"
                if done:
                    color = t["green"]
                    bg = f"{t['green']}18"
                    border = f"{t['green']}60"
                else:
                    color = t["muted"]
                    bg = t["surface"]
                    border = f"{t['muted']}40"
                # Render as styled HTML card + hidden checkbox for toggle
                st.markdown(
                    f"<div style='"
                    f"background:{bg};border:2px solid {border};color:{color};"
                    f"border-radius:0.5rem;padding:0.7rem 0.5rem;"
                    f"text-align:center;font-weight:bold;font-size:0.95rem;"
                    f"letter-spacing:0.03em;"
                    f"'>{icon}  {key.upper()}</div>",
                    unsafe_allow_html=True,
                )
                val = st.checkbox(
                    "toggle", value=done,
                    key=f"nn_{day_str}_{key}",
                    label_visibility="collapsed",
                )
                if val != done:
                    plan.completed[key] = val
                    save_plan(plan)
                    st.rerun()

        # --- Details ---
        st.markdown(f"<div class='section-header'>Details</div>", unsafe_allow_html=True)

        new_focus = st.text_input("Focus", value=plan.focus, placeholder="What's the #1 priority today?")
        col_e, col_s = st.columns(2)
        with col_e:
            new_energy = st.text_input("Energy", value=plan.energy, placeholder="low / medium / high")
        with col_s:
            new_sleep = st.text_input("Sleep (hrs)", value=plan.sleep_hours, placeholder="8")

        if new_focus != plan.focus or new_energy != plan.energy or new_sleep != plan.sleep_hours:
            plan.focus = new_focus
            plan.energy = new_energy
            plan.sleep_hours = new_sleep
            save_plan(plan)

        # --- App Tasks ---
        st.markdown(f"<div class='section-header'>App Tasks</div>", unsafe_allow_html=True)
        _render_tasks(plan, "app_tasks", day_str)

        # --- Music Tasks ---
        st.markdown(f"<div class='section-header'>Music Tasks</div>", unsafe_allow_html=True)
        _render_tasks(plan, "music_tasks", day_str)


def _render_week_summary(day_str: str, t: dict[str, str]) -> None:
    """Render Mon-Sun summary for the week containing day_str."""
    d = date.fromisoformat(day_str)
    monday = d - timedelta(days=d.weekday())
    days = [(monday + timedelta(days=i)).isoformat() for i in range(7)]

    for ds in days:
        is_today = ds == day_str
        dt = date.fromisoformat(ds)
        day_label = f"{dt.strftime('%a')} {dt.strftime('%m/%d')}"

        if plan_path(ds).exists():
            p = load_plan(ds)
            s = score_plan(p)
            dots = ""
            for i in range(4):
                if i < s:
                    dots += f"<span style='color:{t['green']}'>●</span>"
                else:
                    dots += f"<span style='color:{t['muted']}'>·</span>"
            score_text = f"{dots} {s}/4"
        else:
            score_text = f"<span style='color:{t['muted']}'>—</span>"

        if is_today:
            marker = f"<span style='color:{t['cyan']}'>▸</span>"
            weight = "font-weight:bold"
        else:
            marker = "&nbsp;"
            weight = ""

        st.markdown(
            f"<div style='display:flex;justify-content:space-between;padding:0.15rem 0;{weight}'>"
            f"<span>{marker} {day_label}</span>"
            f"<span>{score_text}</span>"
            f"</div>",
            unsafe_allow_html=True,
        )


def _render_streak(t: dict[str, str]) -> None:
    """Show current streak count."""
    all_days = list_days()
    if not all_days:
        return

    day_scores = []
    for d in all_days:
        p = load_plan(d)
        day_scores.append((d, score_plan(p)))

    streak = compute_streak(day_scores, threshold=3)
    if streak > 0:
        st.markdown(
            f"<div style='text-align:center;padding:0.5rem;background:{t['surface']};"
            f"border-radius:0.5rem;border:1px solid {t['muted']}30'>"
            f"<span style='font-size:1.5rem'>&#x1F525;</span> "
            f"<span style='font-size:1.1rem;font-weight:bold;color:{t['green']}'>"
            f"{streak} day streak</span>"
            f"<span style='color:{t['muted']};font-size:0.85rem'> (>= 3/4)</span>"
            f"</div>",
            unsafe_allow_html=True,
        )


def _render_weekly_trend(day_str: str, t: dict[str, str]) -> None:
    """Show a bar chart of weekly score averages over recent weeks."""
    all_days = list_days()
    if not all_days:
        return

    # Group scores by ISO week
    weeks: dict[str, list[int]] = {}
    for d in all_days:
        dt = date.fromisoformat(d)
        monday = dt - timedelta(days=dt.weekday())
        week_key = monday.isoformat()
        if week_key not in weeks:
            weeks[week_key] = []
        p = load_plan(d)
        weeks[week_key].append(score_plan(p))

    # Take last 8 weeks max
    sorted_weeks = sorted(weeks.items())[-8:]

    st.markdown(f"<div class='section-header'>Weekly Trend</div>", unsafe_allow_html=True)

    for week_key, scores in sorted_weeks:
        monday = date.fromisoformat(week_key)
        label = f"{monday.strftime('%m/%d')}"
        avg = sum(scores) / len(scores)
        pct = int(avg / 4 * 100)

        current_week = day_str and (
            date.fromisoformat(day_str) - timedelta(days=date.fromisoformat(day_str).weekday())
        ).isoformat() == week_key

        color = score_color(round(avg), t)
        weight = "font-weight:bold" if current_week else ""
        marker = f"<span style='color:{t['cyan']}'>▸</span>" if current_week else "&nbsp;"

        st.markdown(
            f"<div style='display:flex;align-items:center;gap:0.5rem;padding:0.15rem 0;{weight}'>"
            f"<span style='min-width:3.5rem'>{marker} {label}</span>"
            f"<div style='flex:1;height:8px;background:{t['surface']};border-radius:4px;overflow:hidden'>"
            f"<div style='width:{pct}%;height:100%;background:{color};border-radius:4px'></div>"
            f"</div>"
            f"<span style='min-width:2.5rem;text-align:right;color:{color};font-size:0.85rem'>"
            f"{avg:.1f}/4</span>"
            f"</div>",
            unsafe_allow_html=True,
        )


def _render_tasks(plan: DayPlan, attr: str, day_str: str) -> None:
    tasks = getattr(plan, attr)
    changed = False
    to_delete = None

    for i, task in enumerate(tasks):
        col_check, col_text, col_del = st.columns([0.06, 0.84, 0.10])
        with col_check:
            done = st.checkbox(
                "done", value=bool(task["done"]),
                key=f"{attr}_{day_str}_{i}_done",
                label_visibility="collapsed",
            )
            if done != bool(task["done"]):
                task["done"] = done
                changed = True
        with col_text:
            new_text = st.text_input(
                "task", value=str(task["task"]),
                key=f"{attr}_{day_str}_{i}_text",
                label_visibility="collapsed",
            )
            if new_text != str(task["task"]):
                task["task"] = new_text
                changed = True
        with col_del:
            if st.button("−", key=f"{attr}_{day_str}_{i}_del", use_container_width=True):
                to_delete = i

    if to_delete is not None:
        tasks.pop(to_delete)
        save_plan(plan)
        st.rerun()

    if changed:
        save_plan(plan)
        st.rerun()

    # Add button
    if st.button("＋", key=f"{attr}_{day_str}_add", use_container_width=True):
        tasks.append({"task": "", "done": False})
        save_plan(plan)
        st.rerun()


def _render_notes(plan: DayPlan, day_str: str) -> None:
    changed = False
    to_delete = None

    for i, note in enumerate(plan.notes):
        col_text, col_del = st.columns([0.90, 0.10])
        with col_text:
            new_text = st.text_input(
                "note", value=note,
                key=f"note_{day_str}_{i}_text",
                label_visibility="collapsed",
            )
            if new_text != note:
                plan.notes[i] = new_text
                changed = True
        with col_del:
            if st.button("−", key=f"note_{day_str}_{i}_del", use_container_width=True):
                to_delete = i

    if to_delete is not None:
        plan.notes.pop(to_delete)
        save_plan(plan)
        st.rerun()

    if changed:
        save_plan(plan)

    # Add button
    if st.button("＋", key=f"note_{day_str}_add", use_container_width=True):
        plan.notes.append("")
        save_plan(plan)
        st.rerun()


if __name__ == "__main__":
    main()
