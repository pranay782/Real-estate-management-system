# Real Estate & Property Listing Management System

A desktop GUI application (Python + CustomTkinter) with a MongoDB backend
for managing property listings, clients, agents, and inquiries/bookings —
built to satisfy the "GUI-Based MongoDB CRUD Operations" assignment.

## Features

- **Login / role-based access** — admin and agent roles, passwords hashed with bcrypt (never stored in plain text)
- **Property CRUD** — add/edit/delete listings, search & filter by type/status/location/price, upload images (stored in MongoDB via GridFS), thumbnail gallery
- **Client & Agent CRUD** — manage both in one screen, assign clients to agents, see each agent's live workload, one-click "Find Matching Properties" for a client (budget + location match, queried live from the properties collection)
- **Inquiry / Booking pipeline** — New → Contacted → Site Visit → Negotiation → Closed, closing a deal automatically flips the linked property to sold/rented and generates a PDF receipt (reportlab)
- **Dashboard** — property status pie chart and closed-deals-per-month bar chart (matplotlib, embedded in the window), CSV export of any collection (pandas)

All five screens read and write the *same* MongoDB database, so actions in
one screen show up immediately in another (e.g. add a client → they appear
in the Inquiries dropdown right away).

## Tech Stack

| Piece          | Library          |
|-----------------|------------------|
| GUI             | CustomTkinter    |
| Database driver | PyMongo          |
| Images          | GridFS (via PyMongo) |
| Password hashing| bcrypt           |
| PDF receipts    | reportlab        |
| Charts          | matplotlib       |
| CSV export      | pandas           |

## Project Structure

```
real_estate_project/
├── main.py                  # Entry point: login screen + main app shell
├── db.py                    # Single shared MongoDB connection (everyone imports this)
├── auth.py                  # Register/login logic, bcrypt hashing
├── theme.py                 # Shared colors/fonts so every screen looks consistent
├── property_module.py       # Property CRUD (data layer + GUI frame)
├── client_agent_module.py   # Client & Agent CRUD (data layer + GUI frame)
├── inquiry_module.py        # Inquiry/booking pipeline + PDF receipts
├── dashboard.py             # Analytics, charts, CSV export
├── seed_data.py             # Optional: inserts sample data for a demo
├── requirements.txt
├── receipts/                # PDF receipts land here at runtime
└── README.md
```

## 1. Prerequisites

You already have **MongoDB Community Server** and **MongoDB Compass**
installed — that's exactly what this needs. You do **not** need Atlas or
any cloud account; the app connects to `mongodb://localhost:27017/` by
default (set in `db.py`).

Before running the app, make sure the MongoDB service is actually running:

- **Windows:** open *Services* (search "services" in the Start menu), find
  **MongoDB Server**, confirm it says *Running*. If not, right-click → Start.
  Alternatively open a terminal and run `net start MongoDB`.
- **macOS (installed via brew):** `brew services start mongodb-community`
- **Linux:** `sudo systemctl start mongod`

You can sanity-check the connection any time by opening **Compass** and
connecting to `mongodb://localhost:27017/` — if Compass connects, the
Python app will too, since they're both just talking to the same local
server.

You'll also need **Python 3.10+**.

## 2. Setup

```bash
# 1. Create and activate a virtual environment (keeps this project's
#    packages separate from anything else on your machine)
python -m venv venv

# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. (Optional but recommended) Seed some sample data so the dashboard
#    charts and matching-properties feature have something to show
python seed_data.py

# 4. Run the app
python main.py
```

First run has no users yet, so `main.py` auto-creates a default admin
account:

```
username: admin
password: admin123
```

Log in with that, then use **Create Account** on the login screen to add
real agent logins for your demo/viva.

## 3. Verifying it worked (via Compass)

After running the app and adding a property or two, open Compass, connect
to `mongodb://localhost:27017/`, and you should see a new database called
**`real_estate_db`** with collections: `users`, `properties`, `clients`,
`agents`, `inquiries`, plus `fs.files` / `fs.chunks` (created automatically
by GridFS once you upload your first property image). This is a good
screenshot to include in your report/viva slides — it proves the GUI is
really talking to MongoDB and not just holding data in memory.

## 4. Design decisions worth mentioning in your report

- **One shared `db.py`** — every module imports `get_db()`/`get_fs()`
  from here instead of opening its own connection, so there's exactly one
  source of truth for the database name and connection string.
- **Deleting an agent with clients still assigned** is blocked by default;
  the GUI then offers to auto-unassign those clients and retry, rather than
  silently deleting or orphaning data.
- **Closing a deal is a two-step confirmation** (it writes into a
  *different* collection — the linked property — so it isn't undo-able
  from the Inquiries screen alone).
- **GridFS instead of a raw binary field** for property images, since
  MongoDB documents aren't meant to hold large binary blobs directly.
- **Role field on `users`** (`admin`/`agent`) is stored and shown in the
  window title bar; extending it into full row-level permissions (agents
  only seeing their own clients) is a natural "future work" bullet if your
  report needs one.

## 5. Deploying to GitHub (what the assignment asks for)

```bash
cd real_estate_project
git init
git add .
git commit -m "Real Estate & Property Listing Management System - GUI CRUD with MongoDB"

# Create an empty repo on github.com first, then:
git remote add origin https://github.com/<your-username>/<repo-name>.git
git branch -M main
git push -u origin main
```

The `.gitignore` already excludes your virtual environment and generated
PDF receipts, so only source code gets pushed. Paste the repo URL into the
assignment submission.

> Since MongoDB is running locally on your machine, nothing needs to be
> "deployed" to a server for this to work for grading — whoever reviews it
> just needs their own local MongoDB running and to follow the Setup steps
> above. If you'd ever want it running as an always-on web app instead of
> a desktop app, that's a different project shape (Flask/Streamlit + a
> hosted database) — say the word if you want to go that route instead.

## 6. Troubleshooting

| Problem | Fix |
|---|---|
| `Could not connect to MongoDB` on startup | MongoDB service isn't running — see step 1 above |
| `ModuleNotFoundError: No module named 'customtkinter'` (or similar) | Your virtual environment isn't activated, or `pip install -r requirements.txt` didn't run |
| Images don't show after upload | Confirm `Pillow` installed correctly; re-select the property row to reload its thumbnails |
| PDF receipt not found | Check the `receipts/` folder — the app prints/shows the full path when a deal is closed |
| Blank/garbled charts | Make sure `matplotlib` installed without errors; on Linux you may need `sudo apt install python3-tk` for Tkinter itself |

## 7. For the viva/demo

A clean run-through that shows every integration point in ~3 minutes:

1. Log in as admin.
2. **Properties** — add one, upload a photo, filter by location.
3. **Clients & Agents** — add an agent, add a client with a budget/location
   that matches the property you just added, click **Find Matching
   Properties** to prove it live-queries the properties collection.
4. **Inquiries** — create an inquiry for that client/property/agent pair,
   move it through the status pipeline, then **Close Deal** — point out
   that the property's status flips to sold/rented automatically and a PDF
   receipt is generated.
5. **Dashboard** — refresh and show the pie/bar charts update, then export
   a collection to CSV.
