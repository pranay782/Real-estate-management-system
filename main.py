"""
main.py  (Authentication + Main App Shell)

Single entry point for the whole project:
    python main.py

Flow:
    LoginWindow -> (successful login) -> MainApp
    MainApp is a sidebar-navigation shell that swaps in the Property,
    Client/Agent, Inquiry, and Dashboard frames from the other modules.

First run: no users exist yet, so ensure_default_admin() seeds
admin / admin123. Log in with that, then use "Create Account" to add
real agent logins.
"""

import customtkinter as ctk
from tkinter import messagebox

import theme
from db import ensure_indexes
from auth import login_user, register_user, ensure_default_admin

from property_module import PropertyFrame
from client_agent_module import ClientAgentFrame
from inquiry_module import InquiryFrame
from dashboard import DashboardFrame

APP_TITLE = "Real Estate & Property Listing Management System"


class LoginWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE + " - Login")
        self.geometry("420x480")
        self.resizable(False, False)
        self.configure(fg_color=theme.BG_MAIN)

        card = ctk.CTkFrame(self, fg_color=theme.BG_CARD, corner_radius=16)
        card.pack(expand=True, fill="both", padx=30, pady=30)

        ctk.CTkLabel(card, text="🏠", font=("Segoe UI", 40)).pack(pady=(30, 0))
        ctk.CTkLabel(card, text="Real Estate Manager", font=theme.FONT_TITLE).pack(pady=(4, 0))
        ctk.CTkLabel(card, text="Property Listing Management System", font=theme.FONT_SUBTITLE,
                     text_color=theme.TEXT_MUTED).pack(pady=(0, 24))

        ctk.CTkLabel(card, text="Username", font=theme.FONT_SMALL, text_color=theme.TEXT_MUTED).pack(
            anchor="w", padx=40
        )
        self.username_entry = ctk.CTkEntry(card, width=300, placeholder_text="e.g. admin")
        self.username_entry.pack(padx=40, pady=(2, 12))

        ctk.CTkLabel(card, text="Password", font=theme.FONT_SMALL, text_color=theme.TEXT_MUTED).pack(
            anchor="w", padx=40
        )
        self.password_entry = ctk.CTkEntry(card, width=300, show="*")
        self.password_entry.pack(padx=40, pady=(2, 6))
        self.password_entry.bind("<Return>", lambda _e: self.on_login())

        self.role_var = ctk.StringVar(value="agent")
        role_row = ctk.CTkFrame(card, fg_color="transparent")
        role_row.pack(pady=(6, 4))
        ctk.CTkLabel(role_row, text="New account role:", font=theme.FONT_SMALL,
                     text_color=theme.TEXT_MUTED).pack(side="left", padx=(0, 8))
        ctk.CTkOptionMenu(role_row, values=["agent", "admin"], variable=self.role_var, width=100).pack(side="left")

        ctk.CTkButton(card, text="Log In", command=self.on_login, width=300,
                      fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER).pack(pady=(16, 8))
        ctk.CTkButton(card, text="Create Account", command=self.on_register, width=300,
                      fg_color=theme.BG_SIDEBAR).pack(pady=4)

        ctk.CTkLabel(
            card, text="First run? Default login is admin / admin123",
            font=theme.FONT_SMALL, text_color=theme.TEXT_MUTED,
        ).pack(pady=(16, 0))

    def on_login(self):
        username = self.username_entry.get().strip()
        password = self.password_entry.get()
        if not username or not password:
            messagebox.showwarning("Missing info", "Enter both username and password.")
            return
        role = login_user(username, password)
        if role is None:
            messagebox.showerror("Login failed", "Invalid username or password.")
            return
        self.destroy()
        app = MainApp(current_user={"username": username, "role": role})
        app.mainloop()

    def on_register(self):
        username = self.username_entry.get().strip()
        password = self.password_entry.get()
        if not username or not password:
            messagebox.showwarning("Missing info", "Enter both username and password to register.")
            return
        ok, msg = register_user(username, password, self.role_var.get())
        if ok:
            messagebox.showinfo("Account created", msg)
        else:
            messagebox.showerror("Registration failed", msg)


class MainApp(ctk.CTk):
    """
    Sidebar-navigation shell. Every other module's Frame is instantiated
    once and shown/hidden with .tkraise() - this keeps state (selected
    row, typed filters, etc.) intact when switching tabs instead of
    rebuilding the whole screen every click.
    """

    NAV_ITEMS = [
        ("Dashboard", "📊"),
        ("Properties", "🏘️"),
        ("Clients & Agents", "🧑‍💼"),
        ("Inquiries", "📋"),
    ]

    def __init__(self, current_user):
        super().__init__()
        self.current_user = current_user
        self.title(f"{APP_TITLE} - {current_user['username']} ({current_user['role']})")
        self.geometry("1200x720")
        self.minsize(1000, 640)
        self.configure(fg_color=theme.BG_MAIN)

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_sidebar()
        self._build_content_area()
        self.show_frame("Dashboard")

    def _build_sidebar(self):
        sidebar = ctk.CTkFrame(self, fg_color=theme.BG_SIDEBAR, width=220, corner_radius=0)
        sidebar.grid(row=0, column=0, sticky="nsw")
        sidebar.grid_propagate(False)

        ctk.CTkLabel(sidebar, text="🏠 Real Estate", font=theme.FONT_HEADER).pack(padx=20, pady=(24, 4), anchor="w")
        ctk.CTkLabel(
            sidebar, text=f"{self.current_user['username']}  •  {self.current_user['role']}",
            font=theme.FONT_SMALL, text_color=theme.TEXT_MUTED,
        ).pack(padx=20, pady=(0, 24), anchor="w")

        self.nav_buttons = {}
        for name, icon in self.NAV_ITEMS:
            btn = ctk.CTkButton(
                sidebar, text=f"{icon}  {name}", anchor="w", height=40,
                fg_color="transparent", hover_color=theme.BG_MAIN, font=theme.FONT_BODY,
                command=lambda n=name: self.show_frame(n),
            )
            btn.pack(fill="x", padx="12", pady=2)
            self.nav_buttons[name] = btn

        ctk.CTkFrame(sidebar, fg_color=theme.TEXT_MUTED, height=1).pack(fill="x", padx=20, pady=16)
        ctk.CTkButton(
            sidebar, text="🚪  Log Out", anchor="w", height=40,
            fg_color="transparent", hover_color=theme.DANGER, font=theme.FONT_BODY,
            command=self.on_logout,
        ).pack(fill="x", padx=12, pady=2, side="bottom", anchor="s")

    def _build_content_area(self):
        self.content = ctk.CTkFrame(self, fg_color=theme.BG_MAIN, corner_radius=0)
        self.content.grid(row=0, column=1, sticky="nsew")
        self.content.grid_rowconfigure(0, weight=1)
        self.content.grid_columnconfigure(0, weight=1)

        self.frames = {
            "Dashboard": DashboardFrame(self.content, self.current_user),
            "Properties": PropertyFrame(self.content, self.current_user),
            "Clients & Agents": ClientAgentFrame(self.content, self.current_user),
            "Inquiries": InquiryFrame(self.content, self.current_user),
        }
        for frame in self.frames.values():
            frame.grid(row=0, column=0, sticky="nsew")

    def show_frame(self, name):
        for n, btn in self.nav_buttons.items():
            btn.configure(fg_color=theme.ACCENT if n == name else "transparent")
        frame = self.frames[name]
        frame.tkraise()
        # Refresh dropdown-dependent data whenever a tab becomes visible,
        # so e.g. a newly-added client shows up immediately in Inquiries.
        if hasattr(frame, "refresh_dropdowns"):
            frame.refresh_dropdowns()
        if hasattr(frame, "refresh_list"):
            frame.refresh_list()
        if name == "Dashboard":
            frame.refresh()

    def on_logout(self):
        self.destroy()
        login = LoginWindow()
        login.mainloop()


def main():
    theme.apply_theme()
    ensure_indexes()
    ensure_default_admin()
    login = LoginWindow()
    login.mainloop()


if __name__ == "__main__":
    main()
