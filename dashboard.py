"""
dashboard.py  (Authentication support + Dashboard & Reports)

Reads from properties AND inquiries (owned by other modules) to prove all
screens share one live MongoDB database. Embeds matplotlib charts directly
in the Tkinter window via FigureCanvasTkAgg, and exports any collection to
CSV using pandas.
"""

import os
from datetime import datetime
from collections import Counter, defaultdict

import customtkinter as ctk
from tkinter import filedialog, messagebox

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import pandas as pd

from db import get_db
import theme


# ---------------------------------------------------------------------------
# DATA LAYER
# ---------------------------------------------------------------------------
def get_dashboard_stats():
    db = get_db()
    total_properties = db.properties.count_documents({})
    available = db.properties.count_documents({"status": "available"})
    sold = db.properties.count_documents({"status": "sold"})
    rented = db.properties.count_documents({"status": "rented"})
    total_clients = db.clients.count_documents({})
    total_agents = db.agents.count_documents({})
    open_inquiries = db.inquiries.count_documents({"status": {"$ne": "Closed"}})
    closed_deals = list(db.inquiries.find({"status": "Closed"}))
    total_revenue = sum(d.get("closing_price", 0) or 0 for d in closed_deals)
    return {
        "total_properties": total_properties,
        "available": available,
        "sold": sold,
        "rented": rented,
        "total_clients": total_clients,
        "total_agents": total_agents,
        "open_inquiries": open_inquiries,
        "closed_deals": len(closed_deals),
        "total_revenue": total_revenue,
    }


def property_status_breakdown():
    db = get_db()
    counts = Counter(p["status"] for p in db.properties.find({}, {"status": 1}))
    return counts


def monthly_sales_breakdown():
    """Count of closed deals per month (YYYY-MM), based on date_created."""
    db = get_db()
    by_month = defaultdict(int)
    for inq in db.inquiries.find({"status": "Closed"}):
        month_key = inq["date_created"].strftime("%Y-%m")
        by_month[month_key] += 1
    return dict(sorted(by_month.items()))


def export_report_to_csv(collection_name: str, filepath: str):
    """Exports a whole collection to CSV using pandas. Returns row count."""
    db = get_db()
    if collection_name not in db.list_collection_names():
        raise ValueError(f"Collection '{collection_name}' does not exist.")
    docs = list(db[collection_name].find())
    for d in docs:
        d["_id"] = str(d.get("_id"))
        for key in ("client_id", "property_id", "agent_id", "assigned_agent_id"):
            if key in d and d[key] is not None:
                d[key] = str(d[key])
        for key in ("image_ids",):
            if key in d and isinstance(d[key], list):
                d[key] = ", ".join(str(i) for i in d[key])
    df = pd.DataFrame(docs)
    df.to_csv(filepath, index=False)
    return len(docs)


# ---------------------------------------------------------------------------
# GUI LAYER
# ---------------------------------------------------------------------------
class DashboardFrame(ctk.CTkFrame):
    def __init__(self, master, current_user):
        super().__init__(master, fg_color=theme.BG_MAIN)
        self.current_user = current_user
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(20, 10))
        ctk.CTkLabel(header, text="Dashboard & Reports", font=theme.FONT_HEADER).pack(side="left")
        ctk.CTkButton(header, text="Refresh", command=self.refresh, width=100,
                      fg_color=theme.BG_SIDEBAR).pack(side="right")

        # ---- stat cards ----
        self.cards_row = ctk.CTkFrame(self, fg_color="transparent")
        self.cards_row.pack(fill="x", padx=20, pady=(0, 10))
        self.card_labels = {}
        card_defs = [
            ("total_properties", "Properties"),
            ("total_clients", "Clients"),
            ("total_agents", "Agents"),
            ("open_inquiries", "Open Inquiries"),
            ("closed_deals", "Closed Deals"),
            ("total_revenue", "Total Revenue"),
        ]
        for key, label in card_defs:
            card = ctk.CTkFrame(self.cards_row, fg_color=theme.BG_CARD, corner_radius=10)
            card.pack(side="left", expand=True, fill="both", padx=6)
            val = ctk.CTkLabel(card, text="0", font=theme.FONT_TITLE, text_color=theme.ACCENT)
            val.pack(pady=(14, 0))
            ctk.CTkLabel(card, text=label, font=theme.FONT_SMALL, text_color=theme.TEXT_MUTED).pack(pady=(0, 12))
            self.card_labels[key] = val

        # ---- charts ----
        charts_row = ctk.CTkFrame(self, fg_color="transparent")
        charts_row.pack(fill="both", expand=True, padx=20, pady=10)
        charts_row.grid_columnconfigure(0, weight=1)
        charts_row.grid_columnconfigure(1, weight=1)
        charts_row.grid_rowconfigure(0, weight=1)

        self.chart1_holder = ctk.CTkFrame(charts_row, fg_color=theme.BG_CARD, corner_radius=10)
        self.chart1_holder.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self.chart2_holder = ctk.CTkFrame(charts_row, fg_color=theme.BG_CARD, corner_radius=10)
        self.chart2_holder.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

        # ---- export ----
        export_row = ctk.CTkFrame(self, fg_color="transparent")
        export_row.pack(fill="x", padx=20, pady=(0, 20))
        ctk.CTkLabel(export_row, text="Export report:", font=theme.FONT_SMALL,
                     text_color=theme.TEXT_MUTED).pack(side="left", padx=(0, 8))
        self.export_var = ctk.StringVar(value="properties")
        ctk.CTkOptionMenu(
            export_row, values=["properties", "clients", "agents", "inquiries"], variable=self.export_var, width=140
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(export_row, text="Export to CSV", command=self.on_export,
                      fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER, width=140).pack(side="left")

    def refresh(self):
        stats = get_dashboard_stats()
        self.card_labels["total_properties"].configure(text=str(stats["total_properties"]))
        self.card_labels["total_clients"].configure(text=str(stats["total_clients"]))
        self.card_labels["total_agents"].configure(text=str(stats["total_agents"]))
        self.card_labels["open_inquiries"].configure(text=str(stats["open_inquiries"]))
        self.card_labels["closed_deals"].configure(text=str(stats["closed_deals"]))
        self.card_labels["total_revenue"].configure(text=f"₹{stats['total_revenue']:,.0f}")
        self.render_property_status_chart()
        self.render_monthly_sales_chart()

    def _clear_holder(self, holder):
        for w in holder.winfo_children():
            w.destroy()

    def render_property_status_chart(self):
        self._clear_holder(self.chart1_holder)
        counts = property_status_breakdown()
        fig = Figure(figsize=(4.2, 3.4), dpi=100, facecolor=theme.BG_CARD)
        ax = fig.add_subplot(111)
        ax.set_facecolor(theme.BG_CARD)
        labels = list(counts.keys()) or ["No data"]
        values = list(counts.values()) or [1]
        colors_list = [theme.PROPERTY_STATUS_COLORS.get(l, "#888") for l in labels]
        ax.pie(values, labels=labels, autopct="%1.0f%%", colors=colors_list,
               textprops={"color": theme.TEXT_PRIMARY, "fontsize": 9})
        ax.set_title("Property Status", color=theme.TEXT_PRIMARY, fontsize=12)
        canvas = FigureCanvasTkAgg(fig, master=self.chart1_holder)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=10)

    def render_monthly_sales_chart(self):
        self._clear_holder(self.chart2_holder)
        by_month = monthly_sales_breakdown()
        fig = Figure(figsize=(4.2, 3.4), dpi=100, facecolor=theme.BG_CARD)
        ax = fig.add_subplot(111)
        ax.set_facecolor(theme.BG_CARD)
        months = list(by_month.keys()) or ["-"]
        counts = list(by_month.values()) or [0]
        ax.bar(months, counts, color=theme.ACCENT)
        ax.set_title("Closed Deals per Month", color=theme.TEXT_PRIMARY, fontsize=12)
        ax.tick_params(axis="x", colors=theme.TEXT_PRIMARY, labelrotation=30, labelsize=8)
        ax.tick_params(axis="y", colors=theme.TEXT_PRIMARY, labelsize=8)
        for spine in ax.spines.values():
            spine.set_color(theme.TEXT_MUTED)
        fig.tight_layout()
        canvas = FigureCanvasTkAgg(fig, master=self.chart2_holder)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=10)

    def on_export(self):
        collection = self.export_var.get()
        default_name = f"{collection}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        filepath = filedialog.asksaveasfilename(
            defaultextension=".csv", initialfile=default_name,
            filetypes=[("CSV files", "*.csv")],
        )
        if not filepath:
            return
        try:
            count = export_report_to_csv(collection, filepath)
            messagebox.showinfo("Export complete", f"Exported {count} row(s) to:\n{filepath}")
        except Exception as exc:
            messagebox.showerror("Export failed", str(exc))
