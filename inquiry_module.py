"""
inquiry_module.py  (Inquiry & Booking / Transactions)

This is the main integration hub of the app: every inquiry references a
document from clients, agents AND properties, and closing a deal writes
back into property_module's `properties` collection (status -> sold/rented)
and generates a PDF receipt with reportlab.
"""

import os
from datetime import datetime
from bson import ObjectId

import customtkinter as ctk
from tkinter import ttk, messagebox

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

from db import get_db
import theme

STATUS_ORDER = theme.INQUIRY_STATUS_ORDER  # ["New", "Contacted", "Site Visit", "Negotiation", "Closed"]
RECEIPTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "receipts")


# ---------------------------------------------------------------------------
# DATA LAYER
# ---------------------------------------------------------------------------
def create_inquiry(client_id, property_id, agent_id):
    doc = {
        "client_id": ObjectId(client_id),
        "property_id": ObjectId(property_id),
        "agent_id": ObjectId(agent_id) if agent_id else None,
        "status": "New",
        "date_created": datetime.utcnow(),
        "closing_price": None,
    }
    return get_db().inquiries.insert_one(doc).inserted_id


def get_inquiries(filters: dict = None):
    query = {}
    if filters:
        if filters.get("status") and filters["status"] != "All":
            query["status"] = filters["status"]
        if filters.get("agent_id"):
            query["agent_id"] = ObjectId(filters["agent_id"])
    return list(get_db().inquiries.find(query).sort("date_created", -1))


def get_inquiry(inquiry_id):
    return get_db().inquiries.find_one({"_id": ObjectId(inquiry_id)})


def update_inquiry_status(inquiry_id, new_status: str):
    if new_status not in STATUS_ORDER:
        raise ValueError(f"Status must be one of {STATUS_ORDER}")
    get_db().inquiries.update_one({"_id": ObjectId(inquiry_id)}, {"$set": {"status": new_status}})


def close_deal(inquiry_id, closing_price: float):
    """
    Marks the inquiry Closed, writes the property's status back to
    sold/rented depending on the client's requirement_type, and generates
    a PDF receipt. Returns the path to the generated PDF.
    """
    from property_module import set_property_status  # local import, avoids circular import

    inquiry = get_inquiry(inquiry_id)
    if not inquiry:
        raise ValueError("Inquiry not found.")

    closing_price = float(closing_price)
    if closing_price <= 0:
        raise ValueError("Closing price must be greater than 0.")

    db = get_db()
    client = db.clients.find_one({"_id": inquiry["client_id"]})
    new_status = "rented" if client and client.get("requirement_type") == "rent" else "sold"

    db.inquiries.update_one(
        {"_id": ObjectId(inquiry_id)},
        {"$set": {"status": "Closed", "closing_price": closing_price}},
    )
    set_property_status(inquiry["property_id"], new_status)

    return generate_receipt_pdf(inquiry_id)


def generate_receipt_pdf(inquiry_id):
    db = get_db()
    inquiry = db.inquiries.find_one({"_id": ObjectId(inquiry_id)})
    if not inquiry:
        raise ValueError("Inquiry not found.")
    client = db.clients.find_one({"_id": inquiry["client_id"]}) or {}
    prop = db.properties.find_one({"_id": inquiry["property_id"]}) or {}
    agent = db.agents.find_one({"_id": inquiry.get("agent_id")}) if inquiry.get("agent_id") else {}
    agent = agent or {}

    os.makedirs(RECEIPTS_DIR, exist_ok=True)
    filename = f"receipt_{str(inquiry['_id'])}.pdf"
    filepath = os.path.join(RECEIPTS_DIR, filename)

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("TitleStyle", parent=styles["Title"], textColor=colors.HexColor("#1E2530"))
    doc = SimpleDocTemplate(filepath, pagesize=A4, topMargin=2 * cm, bottomMargin=2 * cm)
    elements = [
        Paragraph("Real Estate & Property Listing Management System", title_style),
        Paragraph("Booking Confirmation / Receipt", styles["Heading2"]),
        Spacer(1, 0.5 * cm),
        Paragraph(f"Receipt ID: {inquiry['_id']}", styles["Normal"]),
        Paragraph(f"Date: {datetime.utcnow().strftime('%d-%b-%Y')}", styles["Normal"]),
        Spacer(1, 0.6 * cm),
    ]

    table_data = [
        ["Property", prop.get("title", "N/A")],
        ["Location", prop.get("location", "N/A")],
        ["Type", prop.get("type", "N/A")],
        ["Client", client.get("name", "N/A")],
        ["Client Contact", client.get("contact", "N/A")],
        ["Handled By (Agent)", agent.get("name", "Unassigned")],
        ["Deal Type", (client.get("requirement_type") or "buy").title()],
        ["Closing Price", f"Rs. {inquiry.get('closing_price', 0):,.0f}"],
    ]
    table = Table(table_data, colWidths=[5 * cm, 9 * cm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#242C3A")),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    elements.append(table)
    elements.append(Spacer(1, 1 * cm))
    elements.append(Paragraph(
        "This receipt confirms the transaction has been recorded in the Real Estate "
        "Management System. Thank you for using our services.", styles["Normal"]
    ))
    doc.build(elements)
    return filepath


# ---------------------------------------------------------------------------
# GUI LAYER
# ---------------------------------------------------------------------------
class InquiryFrame(ctk.CTkFrame):
    def __init__(self, master, current_user):
        super().__init__(master, fg_color=theme.BG_MAIN)
        self.current_user = current_user
        self.selected_id = None
        self._build_ui()
        self.refresh_dropdowns()
        self.refresh_list()

    def _build_ui(self):
        ctk.CTkLabel(self, text="Inquiries & Bookings", font=theme.FONT_HEADER).pack(
            anchor="w", padx=20, pady=(20, 10)
        )

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        # ---- Left: new inquiry form ----
        form = ctk.CTkFrame(body, fg_color=theme.BG_CARD, corner_radius=10, width=300)
        form.grid(row=0, column=0, sticky="ns", padx=(0, 15))

        ctk.CTkLabel(form, text="New Inquiry", font=theme.FONT_BODY).pack(anchor="w", padx=16, pady=(14, 6))

        ctk.CTkLabel(form, text="Client", font=theme.FONT_SMALL, text_color=theme.TEXT_MUTED).pack(
            anchor="w", padx=16
        )
        self.client_var = ctk.StringVar()
        self.client_menu = ctk.CTkOptionMenu(form, values=["-"], variable=self.client_var, width=250)
        self.client_menu.pack(padx=16, pady=(2, 8))

        ctk.CTkLabel(form, text="Property", font=theme.FONT_SMALL, text_color=theme.TEXT_MUTED).pack(
            anchor="w", padx=16
        )
        self.property_var = ctk.StringVar()
        self.property_menu = ctk.CTkOptionMenu(form, values=["-"], variable=self.property_var, width=250)
        self.property_menu.pack(padx=16, pady=(2, 8))

        ctk.CTkLabel(form, text="Agent", font=theme.FONT_SMALL, text_color=theme.TEXT_MUTED).pack(
            anchor="w", padx=16
        )
        self.agent_var = ctk.StringVar()
        self.agent_menu = ctk.CTkOptionMenu(form, values=["Unassigned"], variable=self.agent_var, width=250)
        self.agent_menu.pack(padx=16, pady=(2, 8))

        ctk.CTkButton(form, text="Create Inquiry", command=self.on_create,
                      fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER).pack(
            fill="x", padx=16, pady=(10, 6)
        )
        ctk.CTkButton(form, text="Refresh Dropdowns", command=self.refresh_dropdowns,
                      fg_color=theme.BG_SIDEBAR).pack(fill="x", padx=16, pady=4)

        ctk.CTkFrame(form, fg_color=theme.TEXT_MUTED, height=1).pack(fill="x", padx=16, pady=14)

        ctk.CTkLabel(form, text="Update Selected Inquiry", font=theme.FONT_BODY).pack(
            anchor="w", padx=16, pady=(0, 6)
        )
        ctk.CTkLabel(form, text="Move to status:", font=theme.FONT_SMALL, text_color=theme.TEXT_MUTED).pack(
            anchor="w", padx=16
        )
        self.status_var = ctk.StringVar(value=STATUS_ORDER[0])
        ctk.CTkOptionMenu(form, values=STATUS_ORDER, variable=self.status_var, width=250).pack(
            padx=16, pady=(2, 8)
        )
        ctk.CTkButton(form, text="Update Status", command=self.on_update_status).pack(
            fill="x", padx=16, pady=4
        )

        ctk.CTkLabel(form, text="Closing price (for Closed):", font=theme.FONT_SMALL,
                     text_color=theme.TEXT_MUTED).pack(anchor="w", padx=16, pady=(10, 0))
        self.closing_price_entry = ctk.CTkEntry(form, width=250)
        self.closing_price_entry.pack(padx=16, pady=(2, 8))
        ctk.CTkButton(form, text="Close Deal + Generate Receipt", command=self.on_close_deal,
                      fg_color=theme.WARNING, hover_color="#D9911A").pack(fill="x", padx=16, pady=(0, 14))

        # ---- Right: filters + list ----
        right = ctk.CTkFrame(body, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew")
        right.grid_rowconfigure(1, weight=1)
        right.grid_columnconfigure(0, weight=1)

        filter_bar = ctk.CTkFrame(right, fg_color=theme.BG_CARD, corner_radius=10)
        filter_bar.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        self.filter_status = ctk.CTkOptionMenu(filter_bar, values=["All"] + STATUS_ORDER, width=140)
        self.filter_status.grid(row=0, column=0, padx=8, pady=8)
        ctk.CTkButton(filter_bar, text="Filter", width=90, command=self.refresh_list,
                      fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER).grid(row=0, column=1, padx=8, pady=8)
        ctk.CTkButton(filter_bar, text="Show All", width=90, command=self.reset_filters,
                      fg_color=theme.BG_SIDEBAR).grid(row=0, column=2, padx=8, pady=8)

        cols = ("client", "property", "agent", "status", "date", "price")
        self.tree = ttk.Treeview(right, columns=cols, show="headings", style="Custom.Treeview")
        headings = {"client": "Client", "property": "Property", "agent": "Agent",
                    "status": "Status", "date": "Created", "price": "Closing Price"}
        for col in cols:
            self.tree.heading(col, text=headings[col])
            self.tree.column(col, width=130)
        self.tree.grid(row=1, column=0, sticky="nsew")
        self.tree.bind("<<TreeviewSelect>>", self.on_select)

        sb = ttk.Scrollbar(right, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.grid(row=1, column=1, sticky="ns")

    # -- dropdown population (reads live client/property/agent collections) --
    def refresh_dropdowns(self):
        from client_agent_module import get_all_clients, get_all_agents
        from property_module import get_all_properties

        self._clients = {f"{c['name']} ({c['contact']})": str(c["_id"]) for c in get_all_clients()}
        self._properties = {
            f"{p['title']} - {p['location']}": str(p["_id"])
            for p in get_all_properties({"status": "available"})
        }
        self._agents = {a["name"]: str(a["_id"]) for a in get_all_agents()}

        self.client_menu.configure(values=list(self._clients.keys()) or ["No clients yet"])
        self.property_menu.configure(values=list(self._properties.keys()) or ["No available properties"])
        self.agent_menu.configure(values=["Unassigned"] + list(self._agents.keys()))
        if self._clients:
            self.client_var.set(list(self._clients.keys())[0])
        if self._properties:
            self.property_var.set(list(self._properties.keys())[0])
        self.agent_var.set("Unassigned")

    def on_create(self):
        client_id = self._clients.get(self.client_var.get())
        property_id = self._properties.get(self.property_var.get())
        agent_id = self._agents.get(self.agent_var.get())
        if not client_id or not property_id:
            messagebox.showwarning("Missing data", "Add at least one client and one available property first.")
            return
        create_inquiry(client_id, property_id, agent_id)
        messagebox.showinfo("Success", "Inquiry created with status 'New'.")
        self.refresh_list()

    # -- list --
    def reset_filters(self):
        self.filter_status.set("All")
        self.refresh_list()

    def refresh_list(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        db = get_db()
        filters = {"status": self.filter_status.get()}
        for inq in get_inquiries(filters):
            client = db.clients.find_one({"_id": inq["client_id"]}) or {}
            prop = db.properties.find_one({"_id": inq["property_id"]}) or {}
            agent = db.agents.find_one({"_id": inq.get("agent_id")}) if inq.get("agent_id") else None
            price = f"{inq['closing_price']:,.0f}" if inq.get("closing_price") else "-"
            self.tree.insert(
                "", "end", iid=str(inq["_id"]),
                values=(client.get("name", "?"), prop.get("title", "?"),
                        agent["name"] if agent else "Unassigned",
                        inq["status"], inq["date_created"].strftime("%d-%b-%Y"), price),
            )

    def on_select(self, _event=None):
        sel = self.tree.selection()
        if sel:
            self.selected_id = sel[0]

    def on_update_status(self):
        if not self.selected_id:
            messagebox.showwarning("No selection", "Select an inquiry first.")
            return
        try:
            update_inquiry_status(self.selected_id, self.status_var.get())
            self.refresh_list()
        except Exception as exc:
            messagebox.showerror("Error", str(exc))

    def on_close_deal(self):
        if not self.selected_id:
            messagebox.showwarning("No selection", "Select an inquiry first.")
            return
        price = self.closing_price_entry.get().strip()
        if not price:
            messagebox.showwarning("Missing price", "Enter the closing price first.")
            return
        if not messagebox.askyesno(
            "Confirm close",
            "Closing this deal will mark the property as sold/rented and generate a PDF "
            "receipt. This also updates data owned by the Property module. Continue?",
        ):
            return
        try:
            pdf_path = close_deal(self.selected_id, price)
            messagebox.showinfo("Deal closed", f"Receipt generated:\n{pdf_path}")
            self.closing_price_entry.delete(0, "end")
            self.refresh_list()
            self.refresh_dropdowns()
        except Exception as exc:
            messagebox.showerror("Error", str(exc))
