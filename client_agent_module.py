"""
client_agent_module.py  (Client & Agent Management)

Two related collections managed from one screen: clients (people looking
for property) and agents (staff who serve them). Also implements the
"Matching Properties" integration feature, which reads live data out of
property_module's `properties` collection to prove the modules share one
database instead of working in isolation.
"""

from bson import ObjectId

import customtkinter as ctk
from tkinter import ttk, messagebox

from db import get_db
import theme

REQUIREMENT_TYPES = ["buy", "rent"]


# ---------------------------------------------------------------------------
# DATA LAYER - Clients
# ---------------------------------------------------------------------------
def add_client(data: dict):
    doc = {
        "name": data["name"].strip(),
        "contact": data["contact"].strip(),
        "budget": float(data["budget"]),
        "preferred_location": data["preferred_location"].strip(),
        "requirement_type": data.get("requirement_type", "buy"),
        "assigned_agent_id": ObjectId(data["assigned_agent_id"]) if data.get("assigned_agent_id") else None,
    }
    if doc["budget"] <= 0:
        raise ValueError("Budget must be greater than 0.")
    if not doc["name"]:
        raise ValueError("Client name is required.")
    return get_db().clients.insert_one(doc).inserted_id


def get_all_clients():
    return list(get_db().clients.find().sort("name", 1))


def get_client(client_id):
    return get_db().clients.find_one({"_id": ObjectId(client_id)})


def update_client(client_id, data: dict):
    update_doc = {}
    for key in ("name", "contact", "preferred_location", "requirement_type"):
        if key in data:
            update_doc[key] = data[key]
    if "budget" in data:
        update_doc["budget"] = float(data["budget"])
    if "assigned_agent_id" in data:
        update_doc["assigned_agent_id"] = (
            ObjectId(data["assigned_agent_id"]) if data["assigned_agent_id"] else None
        )
    get_db().clients.update_one({"_id": ObjectId(client_id)}, {"$set": update_doc})


def delete_client(client_id):
    get_db().clients.delete_one({"_id": ObjectId(client_id)})


def assign_agent(client_id, agent_id):
    get_db().clients.update_one(
        {"_id": ObjectId(client_id)},
        {"$set": {"assigned_agent_id": ObjectId(agent_id) if agent_id else None}},
    )


def find_matching_properties(client_id):
    """
    Integration point with property_module: queries properties where
    price <= client's budget AND location matches preferred_location.
    Imported lazily to avoid a circular import at module load time.
    """
    from property_module import get_all_properties

    client = get_client(client_id)
    if not client:
        return []
    candidates = get_all_properties({"status": "available", "max_price": client["budget"]})
    loc = client["preferred_location"].strip().lower()
    if not loc:
        return candidates
    return [p for p in candidates if loc in p["location"].lower()]


# ---------------------------------------------------------------------------
# DATA LAYER - Agents
# ---------------------------------------------------------------------------
def add_agent(data: dict):
    doc = {
        "name": data["name"].strip(),
        "contact": data["contact"].strip(),
        "region": data["region"].strip(),
        "experience_years": int(data["experience_years"] or 0),
    }
    if not doc["name"]:
        raise ValueError("Agent name is required.")
    return get_db().agents.insert_one(doc).inserted_id


def get_all_agents():
    return list(get_db().agents.find().sort("name", 1))


def get_agent(agent_id):
    return get_db().agents.find_one({"_id": ObjectId(agent_id)})


def update_agent(agent_id, data: dict):
    update_doc = {}
    for key in ("name", "contact", "region"):
        if key in data:
            update_doc[key] = data[key]
    if "experience_years" in data:
        update_doc["experience_years"] = int(data["experience_years"] or 0)
    get_db().agents.update_one({"_id": ObjectId(agent_id)}, {"$set": update_doc})


def delete_agent(agent_id, force=False):
    """
    Design decision: block deletion if clients are still assigned, unless
    the caller explicitly confirms `force=True`, in which case those
    clients are auto-unassigned rather than deleted.
    """
    assigned_count = get_db().clients.count_documents({"assigned_agent_id": ObjectId(agent_id)})
    if assigned_count and not force:
        raise ValueError(
            f"{assigned_count} client(s) are still assigned to this agent. "
            "Unassign or reassign them first (or delete again to force-unassign)."
        )
    if force and assigned_count:
        get_db().clients.update_many(
            {"assigned_agent_id": ObjectId(agent_id)}, {"$set": {"assigned_agent_id": None}}
        )
    get_db().agents.delete_one({"_id": ObjectId(agent_id)})


def agent_workload():
    """Returns [(agent_doc, client_count), ...] via a simple grouped count."""
    pipeline = [{"$group": {"_id": "$assigned_agent_id", "count": {"$sum": 1}}}]
    counts = {row["_id"]: row["count"] for row in get_db().clients.aggregate(pipeline) if row["_id"]}
    return [(agent, counts.get(agent["_id"], 0)) for agent in get_all_agents()]


# ---------------------------------------------------------------------------
# GUI LAYER
# ---------------------------------------------------------------------------
class ClientAgentFrame(ctk.CTkFrame):
    def __init__(self, master, current_user):
        super().__init__(master, fg_color=theme.BG_MAIN)
        self.current_user = current_user
        self.selected_client_id = None
        self.selected_agent_id = None

        ctk.CTkLabel(self, text="Clients & Agents", font=theme.FONT_HEADER).pack(
            anchor="w", padx=20, pady=(20, 10)
        )

        self.tabs = ctk.CTkTabview(self, fg_color=theme.BG_CARD)
        self.tabs.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        self.tabs.add("Clients")
        self.tabs.add("Agents")

        self._build_clients_tab(self.tabs.tab("Clients"))
        self._build_agents_tab(self.tabs.tab("Agents"))

        self.refresh_clients()
        self.refresh_agents()

    # ------------------------------------------------------------------ #
    # CLIENTS TAB
    # ------------------------------------------------------------------ #
    def _build_clients_tab(self, parent):
        parent.grid_columnconfigure(1, weight=1)
        parent.grid_rowconfigure(0, weight=1)

        form = ctk.CTkFrame(parent, fg_color=theme.BG_SIDEBAR, corner_radius=10, width=280)
        form.grid(row=0, column=0, sticky="ns", padx=(10, 15), pady=10)

        self.c_entries = {}
        for key, label in [("name", "Name"), ("contact", "Contact"), ("budget", "Budget"),
                            ("preferred_location", "Preferred Location")]:
            ctk.CTkLabel(form, text=label, font=theme.FONT_SMALL, text_color=theme.TEXT_MUTED).pack(
                anchor="w", padx=16, pady=(10, 0)
            )
            entry = ctk.CTkEntry(form, width=240)
            entry.pack(padx=16, pady=(2, 0))
            self.c_entries[key] = entry

        ctk.CTkLabel(form, text="Requirement", font=theme.FONT_SMALL, text_color=theme.TEXT_MUTED).pack(
            anchor="w", padx=16, pady=(10, 0)
        )
        self.c_req_var = ctk.StringVar(value=REQUIREMENT_TYPES[0])
        ctk.CTkOptionMenu(form, values=REQUIREMENT_TYPES, variable=self.c_req_var, width=240).pack(
            padx=16, pady=(2, 0)
        )

        ctk.CTkLabel(form, text="Assigned Agent", font=theme.FONT_SMALL, text_color=theme.TEXT_MUTED).pack(
            anchor="w", padx=16, pady=(10, 0)
        )
        self.c_agent_var = ctk.StringVar(value="Unassigned")
        self.c_agent_menu = ctk.CTkOptionMenu(form, values=["Unassigned"], variable=self.c_agent_var, width=240)
        self.c_agent_menu.pack(padx=16, pady=(2, 0))

        btns = ctk.CTkFrame(form, fg_color="transparent")
        btns.pack(fill="x", padx=16, pady=14)
        ctk.CTkButton(btns, text="Add Client", command=self.on_add_client,
                      fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER).pack(fill="x", pady=3)
        ctk.CTkButton(btns, text="Update Selected", command=self.on_update_client).pack(fill="x", pady=3)
        ctk.CTkButton(btns, text="Delete Selected", command=self.on_delete_client,
                      fg_color=theme.DANGER, hover_color=theme.DANGER_HOVER).pack(fill="x", pady=3)
        ctk.CTkButton(btns, text="Find Matching Properties", command=self.on_find_matches,
                      fg_color=theme.WARNING, hover_color="#D9911A").pack(fill="x", pady=3)
        ctk.CTkButton(btns, text="Clear Form", command=self.clear_client_form,
                      fg_color=theme.BG_MAIN).pack(fill="x", pady=3)

        right = ctk.CTkFrame(parent, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew", pady=10, padx=(0, 10))
        right.grid_rowconfigure(0, weight=1)
        right.grid_columnconfigure(0, weight=1)

        cols = ("name", "contact", "budget", "location", "req", "agent")
        self.client_tree = ttk.Treeview(right, columns=cols, show="headings", style="Custom.Treeview")
        headings = {"name": "Name", "contact": "Contact", "budget": "Budget", "location": "Preferred Loc.",
                    "req": "Buy/Rent", "agent": "Agent"}
        for col in cols:
            self.client_tree.heading(col, text=headings[col])
            self.client_tree.column(col, width=120)
        self.client_tree.grid(row=0, column=0, sticky="nsew")
        self.client_tree.bind("<<TreeviewSelect>>", self.on_select_client)

        sb = ttk.Scrollbar(right, orient="vertical", command=self.client_tree.yview)
        self.client_tree.configure(yscrollcommand=sb.set)
        sb.grid(row=0, column=1, sticky="ns")

    def _agent_lookup(self):
        """Returns dict: display_label -> agent_id, and reverse map for populating forms."""
        agents = get_all_agents()
        self._agents_cache = {str(a["_id"]): a for a in agents}
        return {"Unassigned": None, **{a["name"]: str(a["_id"]) for a in agents}}

    def refresh_clients(self):
        for item in self.client_tree.get_children():
            self.client_tree.delete(item)
        label_map = self._agent_lookup()
        self.c_agent_menu.configure(values=list(label_map.keys()))
        id_to_label = {v: k for k, v in label_map.items() if v is not None}
        for c in get_all_clients():
            agent_label = id_to_label.get(str(c.get("assigned_agent_id")), "Unassigned")
            self.client_tree.insert(
                "", "end", iid=str(c["_id"]),
                values=(c["name"], c["contact"], f"{c['budget']:,.0f}",
                        c["preferred_location"], c["requirement_type"], agent_label),
            )

    def on_select_client(self, _event=None):
        sel = self.client_tree.selection()
        if not sel:
            return
        self.selected_client_id = sel[0]
        c = get_client(self.selected_client_id)
        if not c:
            return
        for key in ("name", "contact", "budget", "preferred_location"):
            self.c_entries[key].delete(0, "end")
            self.c_entries[key].insert(0, str(c.get(key, "")))
        self.c_req_var.set(c.get("requirement_type", REQUIREMENT_TYPES[0]))
        agent = self._agents_cache.get(str(c.get("assigned_agent_id")))
        self.c_agent_var.set(agent["name"] if agent else "Unassigned")

    def read_client_form(self):
        data = {key: self.c_entries[key].get() for key in self.c_entries}
        data["requirement_type"] = self.c_req_var.get()
        label_map = self._agent_lookup()
        data["assigned_agent_id"] = label_map.get(self.c_agent_var.get())
        return data

    def clear_client_form(self):
        for entry in self.c_entries.values():
            entry.delete(0, "end")
        self.c_req_var.set(REQUIREMENT_TYPES[0])
        self.c_agent_var.set("Unassigned")
        self.selected_client_id = None
        self.client_tree.selection_remove(self.client_tree.selection())

    def on_add_client(self):
        try:
            add_client(self.read_client_form())
            messagebox.showinfo("Success", "Client added.")
            self.clear_client_form()
            self.refresh_clients()
            self.refresh_agents()
        except Exception as exc:
            messagebox.showerror("Error", str(exc))

    def on_update_client(self):
        if not self.selected_client_id:
            messagebox.showwarning("No selection", "Select a client to update.")
            return
        try:
            update_client(self.selected_client_id, self.read_client_form())
            messagebox.showinfo("Success", "Client updated.")
            self.refresh_clients()
            self.refresh_agents()
        except Exception as exc:
            messagebox.showerror("Error", str(exc))

    def on_delete_client(self):
        if not self.selected_client_id:
            messagebox.showwarning("No selection", "Select a client to delete.")
            return
        if not messagebox.askyesno("Confirm delete", "Delete this client permanently?"):
            return
        delete_client(self.selected_client_id)
        self.clear_client_form()
        self.refresh_clients()
        self.refresh_agents()

    def on_find_matches(self):
        if not self.selected_client_id:
            messagebox.showwarning("No selection", "Select a client first.")
            return
        matches = find_matching_properties(self.selected_client_id)
        popup = ctk.CTkToplevel(self)
        popup.title("Matching Properties")
        popup.geometry("520x360")
        popup.configure(fg_color=theme.BG_MAIN)
        ctk.CTkLabel(popup, text=f"{len(matches)} matching propert{'y' if len(matches)==1 else 'ies'}",
                     font=theme.FONT_HEADER).pack(anchor="w", padx=16, pady=12)
        box = ctk.CTkScrollableFrame(popup, fg_color=theme.BG_CARD)
        box.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        if not matches:
            ctk.CTkLabel(box, text="No properties currently match this client's budget/location.",
                         text_color=theme.TEXT_MUTED).pack(pady=20)
        for p in matches:
            row = ctk.CTkFrame(box, fg_color=theme.BG_SIDEBAR, corner_radius=8)
            row.pack(fill="x", pady=4, padx=4)
            ctk.CTkLabel(row, text=f"{p['title']}  -  {p['location']}", font=theme.FONT_BODY).pack(
                anchor="w", padx=10, pady=(6, 0)
            )
            ctk.CTkLabel(row, text=f"₹{p['price']:,.0f}  |  {p['type']}  |  {p['bedrooms']}BHK",
                         text_color=theme.TEXT_MUTED, font=theme.FONT_SMALL).pack(anchor="w", padx=10, pady=(0, 6))

    # ------------------------------------------------------------------ #
    # AGENTS TAB
    # ------------------------------------------------------------------ #
    def _build_agents_tab(self, parent):
        parent.grid_columnconfigure(1, weight=1)
        parent.grid_rowconfigure(0, weight=1)

        form = ctk.CTkFrame(parent, fg_color=theme.BG_SIDEBAR, corner_radius=10, width=280)
        form.grid(row=0, column=0, sticky="ns", padx=(10, 15), pady=10)

        self.a_entries = {}
        for key, label in [("name", "Name"), ("contact", "Contact"), ("region", "Region"),
                            ("experience_years", "Experience (yrs)")]:
            ctk.CTkLabel(form, text=label, font=theme.FONT_SMALL, text_color=theme.TEXT_MUTED).pack(
                anchor="w", padx=16, pady=(10, 0)
            )
            entry = ctk.CTkEntry(form, width=240)
            entry.pack(padx=16, pady=(2, 0))
            self.a_entries[key] = entry

        btns = ctk.CTkFrame(form, fg_color="transparent")
        btns.pack(fill="x", padx=16, pady=14)
        ctk.CTkButton(btns, text="Add Agent", command=self.on_add_agent,
                      fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER).pack(fill="x", pady=3)
        ctk.CTkButton(btns, text="Update Selected", command=self.on_update_agent).pack(fill="x", pady=3)
        ctk.CTkButton(btns, text="Delete Selected", command=self.on_delete_agent,
                      fg_color=theme.DANGER, hover_color=theme.DANGER_HOVER).pack(fill="x", pady=3)
        ctk.CTkButton(btns, text="Clear Form", command=self.clear_agent_form,
                      fg_color=theme.BG_MAIN).pack(fill="x", pady=3)

        right = ctk.CTkFrame(parent, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew", pady=10, padx=(0, 10))
        right.grid_rowconfigure(0, weight=1)
        right.grid_columnconfigure(0, weight=1)

        cols = ("name", "contact", "region", "experience", "clients")
        self.agent_tree = ttk.Treeview(right, columns=cols, show="headings", style="Custom.Treeview")
        headings = {"name": "Name", "contact": "Contact", "region": "Region",
                    "experience": "Experience", "clients": "Assigned Clients"}
        for col in cols:
            self.agent_tree.heading(col, text=headings[col])
            self.agent_tree.column(col, width=130)
        self.agent_tree.grid(row=0, column=0, sticky="nsew")
        self.agent_tree.bind("<<TreeviewSelect>>", self.on_select_agent)

        sb = ttk.Scrollbar(right, orient="vertical", command=self.agent_tree.yview)
        self.agent_tree.configure(yscrollcommand=sb.set)
        sb.grid(row=0, column=1, sticky="ns")

    def refresh_agents(self):
        for item in self.agent_tree.get_children():
            self.agent_tree.delete(item)
        for agent, count in agent_workload():
            self.agent_tree.insert(
                "", "end", iid=str(agent["_id"]),
                values=(agent["name"], agent["contact"], agent["region"],
                        f"{agent['experience_years']} yrs", count),
            )

    def on_select_agent(self, _event=None):
        sel = self.agent_tree.selection()
        if not sel:
            return
        self.selected_agent_id = sel[0]
        a = get_agent(self.selected_agent_id)
        if not a:
            return
        for key in ("name", "contact", "region", "experience_years"):
            self.a_entries[key].delete(0, "end")
            self.a_entries[key].insert(0, str(a.get(key, "")))

    def read_agent_form(self):
        return {key: self.a_entries[key].get() for key in self.a_entries}

    def clear_agent_form(self):
        for entry in self.a_entries.values():
            entry.delete(0, "end")
        self.selected_agent_id = None
        self.agent_tree.selection_remove(self.agent_tree.selection())

    def on_add_agent(self):
        try:
            add_agent(self.read_agent_form())
            messagebox.showinfo("Success", "Agent added.")
            self.clear_agent_form()
            self.refresh_agents()
            self.refresh_clients()
        except Exception as exc:
            messagebox.showerror("Error", str(exc))

    def on_update_agent(self):
        if not self.selected_agent_id:
            messagebox.showwarning("No selection", "Select an agent to update.")
            return
        try:
            update_agent(self.selected_agent_id, self.read_agent_form())
            messagebox.showinfo("Success", "Agent updated.")
            self.refresh_agents()
            self.refresh_clients()
        except Exception as exc:
            messagebox.showerror("Error", str(exc))

    def on_delete_agent(self):
        if not self.selected_agent_id:
            messagebox.showwarning("No selection", "Select an agent to delete.")
            return
        try:
            delete_agent(self.selected_agent_id, force=False)
        except ValueError as exc:
            if messagebox.askyesno("Clients assigned", f"{exc}\n\nUnassign them and delete anyway?"):
                delete_agent(self.selected_agent_id, force=True)
            else:
                return
        self.clear_agent_form()
        self.refresh_agents()
        self.refresh_clients()
