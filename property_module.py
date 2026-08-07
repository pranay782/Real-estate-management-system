"""
property_module.py  (Person 1: Property Management - Core CRUD)

- Data-layer functions (add/get/update/delete/images) can be imported and
  used independently of the GUI - e.g. from a test script or the dashboard.
- PropertyFrame is the CTkFrame plugged into main.py's navigation shell.
"""

import io
from datetime import datetime
from bson import ObjectId
from bson.errors import InvalidId

import customtkinter as ctk
from tkinter import ttk, messagebox, filedialog
from PIL import Image

from db import get_db, get_fs
import theme

PROPERTY_TYPES = ["Apartment", "Villa", "Plot", "Commercial"]
PROPERTY_STATUSES = ["available", "sold", "rented"]


# ---------------------------------------------------------------------------
# DATA LAYER
# ---------------------------------------------------------------------------
def add_property(data: dict):
    """Insert a new property document. Returns inserted_id."""
    doc = {
        "title": data["title"].strip(),
        "type": data["type"],
        "price": float(data["price"]),
        "location": data["location"].strip(),
        "bedrooms": int(data["bedrooms"]),
        "bathrooms": int(data["bathrooms"]),
        "area_sqft": float(data["area_sqft"]),
        "status": data.get("status", "available"),
        "image_ids": [],
        "date_listed": datetime.utcnow(),
    }
    if doc["price"] <= 0:
        raise ValueError("Price must be greater than 0.")
    if doc["area_sqft"] <= 0:
        raise ValueError("Area must be greater than 0.")
    if doc["bedrooms"] < 0 or doc["bathrooms"] < 0:
        raise ValueError("Bedrooms/bathrooms cannot be negative.")
    result = get_db().properties.insert_one(doc)
    return result.inserted_id


def get_all_properties(filters: dict = None):
    query = {}
    if filters:
        if filters.get("type"):
            query["type"] = filters["type"]
        if filters.get("status"):
            query["status"] = filters["status"]
        if filters.get("location"):
            query["location"] = {"$regex": filters["location"], "$options": "i"}
        price_q = {}
        if filters.get("min_price") not in (None, ""):
            price_q["$gte"] = float(filters["min_price"])
        if filters.get("max_price") not in (None, ""):
            price_q["$lte"] = float(filters["max_price"])
        if price_q:
            query["price"] = price_q
    return list(get_db().properties.find(query).sort("date_listed", -1))


def get_property(property_id):
    return get_db().properties.find_one({"_id": ObjectId(property_id)})


def update_property(property_id, new_data: dict):
    update_doc = {}
    for key in ("title", "type", "location", "status"):
        if key in new_data:
            update_doc[key] = new_data[key]
    for key in ("price", "area_sqft"):
        if key in new_data:
            update_doc[key] = float(new_data[key])
    for key in ("bedrooms", "bathrooms"):
        if key in new_data:
            update_doc[key] = int(new_data[key])
    get_db().properties.update_one({"_id": ObjectId(property_id)}, {"$set": update_doc})


def set_property_status(property_id, status: str):
    """Used by inquiry_module when a deal is closed (sold/rented)."""
    if status not in PROPERTY_STATUSES:
        return
    get_db().properties.update_one({"_id": ObjectId(property_id)}, {"$set": {"status": status}})


def delete_property(property_id):
    prop = get_property(property_id)
    if not prop:
        return
    fs = get_fs()
    for img_id in prop.get("image_ids", []):
        try:
            fs.delete(img_id)
        except Exception:
            pass
    get_db().properties.delete_one({"_id": ObjectId(property_id)})


def upload_property_image(property_id, file_path):
    fs = get_fs()
    with open(file_path, "rb") as f:
        file_id = fs.put(f, filename=file_path.split("/")[-1].split("\\")[-1])
    get_db().properties.update_one(
        {"_id": ObjectId(property_id)}, {"$push": {"image_ids": file_id}}
    )
    return file_id


def get_property_images(property_id):
    prop = get_property(property_id)
    return prop.get("image_ids", []) if prop else []


def get_image_bytes(image_id):
    return get_fs().get(image_id).read()


# ---------------------------------------------------------------------------
# GUI LAYER
# ---------------------------------------------------------------------------
def style_treeview():
    """Make ttk.Treeview match the dark CustomTkinter theme."""
    style = ttk.Style()
    style.theme_use("clam")
    style.configure(
        "Custom.Treeview",
        background=theme.BG_CARD,
        fieldbackground=theme.BG_CARD,
        foreground=theme.TEXT_PRIMARY,
        rowheight=28,
        borderwidth=0,
        font=theme.FONT_BODY,
    )
    style.configure(
        "Custom.Treeview.Heading",
        background=theme.BG_SIDEBAR,
        foreground=theme.TEXT_PRIMARY,
        font=theme.FONT_SMALL,
        borderwidth=0,
    )
    style.map("Custom.Treeview", background=[("selected", theme.ACCENT)])


class PropertyFrame(ctk.CTkFrame):
    def __init__(self, master, current_user):
        super().__init__(master, fg_color=theme.BG_MAIN)
        self.current_user = current_user
        self.selected_id = None
        self.pending_image_path = None
        style_treeview()
        self._build_ui()
        self.refresh_list()

    # ---- UI construction -------------------------------------------------
    def _build_ui(self):
        ctk.CTkLabel(self, text="Property Listings", font=theme.FONT_HEADER).pack(
            anchor="w", padx=20, pady=(20, 10)
        )

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        body.grid_columnconfigure(0, weight=0)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        # ---- Left: form ----
        form = ctk.CTkFrame(body, fg_color=theme.BG_CARD, corner_radius=10, width=300)
        form.grid(row=0, column=0, sticky="ns", padx=(0, 15))

        self.entries = {}
        fields = [
            ("title", "Title"),
            ("location", "Location"),
            ("price", "Price"),
            ("bedrooms", "Bedrooms"),
            ("bathrooms", "Bathrooms"),
            ("area_sqft", "Area (sqft)"),
        ]
        for key, label in fields:
            ctk.CTkLabel(form, text=label, font=theme.FONT_SMALL, text_color=theme.TEXT_MUTED).pack(
                anchor="w", padx=16, pady=(10, 0)
            )
            entry = ctk.CTkEntry(form, width=260)
            entry.pack(padx=16, pady=(2, 0))
            self.entries[key] = entry

        ctk.CTkLabel(form, text="Type", font=theme.FONT_SMALL, text_color=theme.TEXT_MUTED).pack(
            anchor="w", padx=16, pady=(10, 0)
        )
        self.type_var = ctk.CTkOptionMenu(form, values=PROPERTY_TYPES, width=260)
        self.type_var.pack(padx=16, pady=(2, 0))

        ctk.CTkLabel(form, text="Status", font=theme.FONT_SMALL, text_color=theme.TEXT_MUTED).pack(
            anchor="w", padx=16, pady=(10, 0)
        )
        self.status_var = ctk.CTkOptionMenu(form, values=PROPERTY_STATUSES, width=260)
        self.status_var.pack(padx=16, pady=(2, 0))

        self.image_label = ctk.CTkLabel(form, text="No image selected", font=theme.FONT_SMALL)
        self.image_label.pack(padx=16, pady=(12, 0))
        ctk.CTkButton(
            form, text="Choose Image...", command=self.choose_image, fg_color=theme.BG_SIDEBAR
        ).pack(padx=16, pady=(6, 0), fill="x")

        btn_row = ctk.CTkFrame(form, fg_color="transparent")
        btn_row.pack(padx=16, pady=16, fill="x")
        ctk.CTkButton(
            btn_row, text="Add", command=self.on_add, fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER
        ).pack(fill="x", pady=3)
        ctk.CTkButton(btn_row, text="Update Selected", command=self.on_update).pack(fill="x", pady=3)
        ctk.CTkButton(
            btn_row, text="Delete Selected", command=self.on_delete,
            fg_color=theme.DANGER, hover_color=theme.DANGER_HOVER
        ).pack(fill="x", pady=3)
        ctk.CTkButton(btn_row, text="Clear Form", command=self.clear_form, fg_color=theme.BG_SIDEBAR).pack(
            fill="x", pady=3
        )

        self.thumb_row = ctk.CTkFrame(form, fg_color="transparent")
        self.thumb_row.pack(padx=16, pady=(0, 10), fill="x")

        # ---- Right: filters + list ----
        right = ctk.CTkFrame(body, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew")
        right.grid_rowconfigure(1, weight=1)
        right.grid_columnconfigure(0, weight=1)

        filter_bar = ctk.CTkFrame(right, fg_color=theme.BG_CARD, corner_radius=10)
        filter_bar.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        self.filter_location = ctk.CTkEntry(filter_bar, placeholder_text="Search location...", width=180)
        self.filter_location.grid(row=0, column=0, padx=8, pady=8)
        self.filter_type = ctk.CTkOptionMenu(filter_bar, values=["All"] + PROPERTY_TYPES, width=130)
        self.filter_type.grid(row=0, column=1, padx=8, pady=8)
        self.filter_status = ctk.CTkOptionMenu(filter_bar, values=["All"] + PROPERTY_STATUSES, width=130)
        self.filter_status.grid(row=0, column=2, padx=8, pady=8)
        self.filter_min = ctk.CTkEntry(filter_bar, placeholder_text="Min price", width=100)
        self.filter_min.grid(row=0, column=3, padx=8, pady=8)
        self.filter_max = ctk.CTkEntry(filter_bar, placeholder_text="Max price", width=100)
        self.filter_max.grid(row=0, column=4, padx=8, pady=8)
        ctk.CTkButton(filter_bar, text="Search", width=90, command=self.refresh_list,
                      fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER).grid(row=0, column=5, padx=8, pady=8)
        ctk.CTkButton(filter_bar, text="Reset", width=90, command=self.reset_filters,
                      fg_color=theme.BG_SIDEBAR).grid(row=0, column=6, padx=8, pady=8)

        columns = ("title", "type", "price", "location", "bhk", "status")
        self.tree = ttk.Treeview(right, columns=columns, show="headings", style="Custom.Treeview")
        headings = {"title": "Title", "type": "Type", "price": "Price", "location": "Location",
                    "bhk": "Bed/Bath", "status": "Status"}
        widths = {"title": 200, "type": 100, "price": 100, "location": 150, "bhk": 90, "status": 90}
        for col in columns:
            self.tree.heading(col, text=headings[col], command=lambda c=col: self.sort_by(c))
            self.tree.column(col, width=widths[col])
        self.tree.grid(row=1, column=0, sticky="nsew")
        self.tree.bind("<<TreeviewSelect>>", self.on_row_select)

        scrollbar = ttk.Scrollbar(right, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.grid(row=1, column=1, sticky="ns")

    # ---- behaviour ---------------------------------------------------
    def get_filters(self):
        return {
            "location": self.filter_location.get().strip(),
            "type": None if self.filter_type.get() == "All" else self.filter_type.get(),
            "status": None if self.filter_status.get() == "All" else self.filter_status.get(),
            "min_price": self.filter_min.get().strip() or None,
            "max_price": self.filter_max.get().strip() or None,
        }

    def reset_filters(self):
        self.filter_location.delete(0, "end")
        self.filter_type.set("All")
        self.filter_status.set("All")
        self.filter_min.delete(0, "end")
        self.filter_max.delete(0, "end")
        self.refresh_list()

    def refresh_list(self):
        self._all_rows = []
        for item in self.tree.get_children():
            self.tree.delete(item)
        try:
            props = get_all_properties(self.get_filters())
        except Exception as exc:
            messagebox.showerror("Search error", str(exc))
            return
        for p in props:
            self._all_rows.append(p)
            self.tree.insert(
                "", "end", iid=str(p["_id"]),
                values=(p["title"], p["type"], f"{p['price']:,.0f}", p["location"],
                        f"{p['bedrooms']}/{p['bathrooms']}", p["status"]),
            )

    def sort_by(self, col):
        # Simple client-side sort on the currently loaded rows.
        key_map = {"title": "title", "type": "type", "price": "price",
                   "location": "location", "bhk": "bedrooms", "status": "status"}
        key = key_map.get(col, "title")
        self._all_rows.sort(key=lambda p: p.get(key, ""))
        for item in self.tree.get_children():
            self.tree.delete(item)
        for p in self._all_rows:
            self.tree.insert(
                "", "end", iid=str(p["_id"]),
                values=(p["title"], p["type"], f"{p['price']:,.0f}", p["location"],
                        f"{p['bedrooms']}/{p['bathrooms']}", p["status"]),
            )

    def on_row_select(self, _event=None):
        sel = self.tree.selection()
        if not sel:
            return
        self.selected_id = sel[0]
        prop = get_property(self.selected_id)
        if not prop:
            return
        for key in ("title", "location", "price", "bedrooms", "bathrooms", "area_sqft"):
            self.entries[key].delete(0, "end")
            self.entries[key].insert(0, str(prop.get(key, "")))
        self.type_var.set(prop.get("type", PROPERTY_TYPES[0]))
        self.status_var.set(prop.get("status", PROPERTY_STATUSES[0]))
        self.load_thumbnails(prop.get("image_ids", []))

    def load_thumbnails(self, image_ids):
        for widget in self.thumb_row.winfo_children():
            widget.destroy()
        self._thumb_refs = []
        for img_id in image_ids[:3]:
            try:
                raw = get_image_bytes(img_id)
                pil_img = Image.open(io.BytesIO(raw)).convert("RGB")
                pil_img.thumbnail((70, 70))
                ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=pil_img.size)
                self._thumb_refs.append(ctk_img)
                ctk.CTkLabel(self.thumb_row, image=ctk_img, text="").pack(side="left", padx=3)
            except Exception:
                continue

    def choose_image(self):
        path = filedialog.askopenfilename(
            filetypes=[("Images", "*.png *.jpg *.jpeg *.gif *.bmp")]
        )
        if path:
            self.pending_image_path = path
            self.image_label.configure(text=path.split("/")[-1].split("\\")[-1])

    def read_form(self):
        data = {key: self.entries[key].get() for key in self.entries}
        data["type"] = self.type_var.get()
        data["status"] = self.status_var.get()
        return data

    def clear_form(self):
        for entry in self.entries.values():
            entry.delete(0, "end")
        self.type_var.set(PROPERTY_TYPES[0])
        self.status_var.set(PROPERTY_STATUSES[0])
        self.selected_id = None
        self.pending_image_path = None
        self.image_label.configure(text="No image selected")
        for widget in self.thumb_row.winfo_children():
            widget.destroy()
        self.tree.selection_remove(self.tree.selection())

    def on_add(self):
        try:
            data = self.read_form()
            new_id = add_property(data)
            if self.pending_image_path:
                upload_property_image(new_id, self.pending_image_path)
            messagebox.showinfo("Success", "Property added.")
            self.clear_form()
            self.refresh_list()
        except (ValueError, KeyError) as exc:
            messagebox.showerror("Invalid input", str(exc))
        except Exception as exc:
            messagebox.showerror("Error", str(exc))

    def on_update(self):
        if not self.selected_id:
            messagebox.showwarning("No selection", "Select a property to update.")
            return
        try:
            data = self.read_form()
            update_property(self.selected_id, data)
            if self.pending_image_path:
                upload_property_image(self.selected_id, self.pending_image_path)
                self.pending_image_path = None
            messagebox.showinfo("Success", "Property updated.")
            self.refresh_list()
        except Exception as exc:
            messagebox.showerror("Error", str(exc))

    def on_delete(self):
        if not self.selected_id:
            messagebox.showwarning("No selection", "Select a property to delete.")
            return
        if not messagebox.askyesno("Confirm delete", "Delete this property permanently?"):
            return
        try:
            delete_property(self.selected_id)
            self.clear_form()
            self.refresh_list()
        except Exception as exc:
            messagebox.showerror("Error", str(exc))
