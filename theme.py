"""
theme.py
Central place for colors / fonts so every screen looks like part of the
same app instead of four mismatched student projects glued together.
Import constants from here rather than hard-coding hex values in each module.
"""

import customtkinter as ctk

# Call once, at app start (main.py does this).
def apply_theme():
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")


# Palette -------------------------------------------------------------
BG_SIDEBAR = "#161B22"
BG_MAIN = "#1E2530"
BG_CARD = "#242C3A"
ACCENT = "#2FBF71"          # emerald green - matches "available/closed deal" success color
ACCENT_HOVER = "#27A862"
DANGER = "#E5484D"
DANGER_HOVER = "#C93B3F"
WARNING = "#F5A524"
TEXT_PRIMARY = "#F5F7FA"
TEXT_MUTED = "#9AA4B2"

# Fonts -----------------------------------------------------------------
FONT_TITLE = ("Segoe UI", 24, "bold")
FONT_SUBTITLE = ("Segoe UI", 14)
FONT_HEADER = ("Segoe UI", 18, "bold")
FONT_BODY = ("Segoe UI", 13)
FONT_SMALL = ("Segoe UI", 11)
FONT_BUTTON = ("Segoe UI", 13, "bold")

# Status -> color map, reused by property list, inquiry pipeline, dashboard charts
PROPERTY_STATUS_COLORS = {
    "available": "#2FBF71",
    "sold": "#E5484D",
    "rented": "#F5A524",
}

INQUIRY_STATUS_COLORS = {
    "New": "#9AA4B2",
    "Contacted": "#3B82F6",
    "Site Visit": "#F5A524",
    "Negotiation": "#F97316",
    "Closed": "#2FBF71",
}

INQUIRY_STATUS_ORDER = ["New", "Contacted", "Site Visit", "Negotiation", "Closed"]
