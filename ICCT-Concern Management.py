import csv
import hashlib
import json
import os
import sqlite3
import tkinter as tk
import urllib.request
from abc import ABC, abstractmethod
from datetime import datetime
from tkinter import filedialog, messagebox, ttk

DB_NAME = "icct_concerns.db"
TEACHER_CODE = "ICCT2026"
TAGLINE = "Your Concern Matters"
API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

CATEGORIES = ["Academic", "Facilities", "Finance", "Registrar", "IT / Technical", "Student Services", "Other"]
STATUSES = ["Pending", "In Progress", "Resolved"]

NAVY = "#0B2A6B"
RED = "#D22030"
GOLD = "#F6B90F"
DARK_GOLD = "#C98F00"
GREEN = "#2E8B57"
BG = "#F3F5FA"
WHITE = "#FFFFFF"
TEXT = "#1B2440"
LINE = "#D5DBEA"
STATUS_COLORS = {"Pending": "#FDE3E5", "In Progress": "#FFF3CC", "Resolved": "#DDF3E6"}


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def load_logo(name):
    try:
        return tk.PhotoImage(data=LOGOS[name])
    except Exception:
        return None


def prepare_text(text):
    for ch in ",.;:!?()/":
        text = text.replace(ch, " ")
    return " " + " ".join(text.lower().split()) + " "


def show_text(box, text):
    box.config(state="normal")
    box.delete("1.0", "end")
    box.insert("1.0", text)
    box.config(state="disabled")


def set_style(window):
    window.configure(bg=BG)
    s = ttk.Style(window)
    s.theme_use("clam")
    s.configure(".", background=BG, foreground=TEXT, font=("Segoe UI", 10))
    s.configure("TLabel", background=BG)
    s.configure("Title.TLabel", font=("Segoe UI", 12, "bold"), foreground=NAVY)
    s.configure("TNotebook", background=BG, borderwidth=0)
    s.configure("TNotebook.Tab", padding=(20, 9), font=("Segoe UI", 10, "bold"),
                background="#DCE2F1", foreground=NAVY)
    s.map("TNotebook.Tab", background=[("selected", NAVY)], foreground=[("selected", WHITE)])
    s.configure("Treeview", rowheight=28, background=WHITE, fieldbackground=WHITE, borderwidth=0)
    s.configure("Treeview.Heading", background=NAVY, foreground=WHITE, font=("Segoe UI", 10, "bold"), padding=6)
    s.map("Treeview.Heading", background=[("active", NAVY)])
    s.map("Treeview", background=[("selected", GOLD)], foreground=[("selected", NAVY)])
    s.configure("TEntry", padding=5)
    s.configure("TCombobox", padding=4)
    s.configure("Red.TButton", background=RED, foreground=WHITE, font=("Segoe UI", 10, "bold"), padding=8)
    s.map("Red.TButton", background=[("active", "#A8141F")])
    s.configure("Blue.TButton", background=NAVY, foreground=WHITE, font=("Segoe UI", 10, "bold"), padding=8)
    s.map("Blue.TButton", background=[("active", "#081D4A")])
    s.configure("Gold.TButton", background=GOLD, foreground=NAVY, font=("Segoe UI", 10, "bold"), padding=8)
    s.map("Gold.TButton", background=[("active", "#E0A600")])


def make_card(parent):
    return tk.Frame(parent, bg=WHITE, highlightbackground=LINE, highlightthickness=1)


class Database:
    def __init__(self):
        self.conn = sqlite3.connect(DB_NAME)
        self.conn.row_factory = sqlite3.Row
        self.make_tables()
        self.add_default_users()

    def make_tables(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS users(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                role TEXT NOT NULL,
                full_name TEXT NOT NULL,
                student_no TEXT)""")
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS concerns(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                submitted_by TEXT NOT NULL,
                student_name TEXT NOT NULL,
                student_no TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                category TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Pending',
                remarks TEXT DEFAULT '',
                ai_reply TEXT DEFAULT '',
                date_created TEXT NOT NULL)""")
        columns = [row["name"] for row in self.conn.execute("PRAGMA table_info(concerns)")]
        if "ai_reply" not in columns:
            self.conn.execute("ALTER TABLE concerns ADD COLUMN ai_reply TEXT DEFAULT ''")
        self.conn.commit()

    def add_default_users(self):
        rows = self.conn.execute("SELECT * FROM users").fetchall()
        if len(rows) == 0:
            self.add_user("teacher", "teacher123", "Teacher", "Teacher Demo", "")
            self.add_user("student", "student123", "Student", "Sabrina P. Dasco", "2026-0001")

    def add_user(self, username, password, role, full_name, student_no):
        self.conn.execute(
            "INSERT INTO users(username, password, role, full_name, student_no) VALUES(?,?,?,?,?)",
            (username, hash_password(password), role, full_name, student_no))
        self.conn.commit()

    def find_user(self, username, password):
        return self.conn.execute("SELECT * FROM users WHERE username=? AND password=?",
                                 (username, hash_password(password))).fetchone()

    def add_concern(self, user, title, description, category, ai_reply):
        self.conn.execute(
            "INSERT INTO concerns(submitted_by, student_name, student_no, title, description, "
            "category, status, remarks, ai_reply, date_created) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (user.username, user.full_name, user.student_no, title, description, category,
             "Pending", "", ai_reply, datetime.now().strftime("%Y-%m-%d %H:%M")))
        self.conn.commit()

    def get_concerns(self, keyword=""):
        k = "%" + keyword + "%"
        return self.conn.execute(
            "SELECT * FROM concerns WHERE student_name LIKE ? OR title LIKE ? OR category LIKE ? "
            "OR status LIKE ? ORDER BY id DESC", (k, k, k, k)).fetchall()

    def get_my_concerns(self, username):
        return self.conn.execute("SELECT * FROM concerns WHERE submitted_by=? ORDER BY id DESC",
                                 (username,)).fetchall()

    def get_concern(self, concern_id):
        return self.conn.execute("SELECT * FROM concerns WHERE id=?", (concern_id,)).fetchone()

    def update_concern(self, concern_id, category, status, remarks):
        self.conn.execute("UPDATE concerns SET category=?, status=?, remarks=? WHERE id=?",
                          (category, status, remarks, concern_id))
        self.conn.commit()

    def delete_concern(self, concern_id):
        self.conn.execute("DELETE FROM concerns WHERE id=?", (concern_id,))
        self.conn.commit()


class User:
    def __init__(self, username, role, full_name, student_no):
        self.username = username
        self.role = role
        self.full_name = full_name
        self.student_no = student_no


class BaseClassifier(ABC):
    @abstractmethod
    def predict(self, text):
        pass


class KeywordClassifier(BaseClassifier):
    KEYWORDS = {
        "Academic": ["grade", "grades", "subject", "professor", "teacher", "instructor", "exam", "quiz",
                     "class", "schedule", "assignment", "lesson", "thesis", "attendance", "project"],
        "Facilities": ["room", "aircon", "air-con", "fan", "light", "restroom", "comfort", "cr", "chair",
                       "table", "broken", "leak", "dirty", "clean", "library", "canteen", "parking"],
        "Finance": ["tuition", "payment", "fee", "fees", "balance", "cashier", "scholarship", "refund",
                    "installment", "receipt", "discount"],
        "Registrar": ["enroll", "enrollment", "tor", "transcript", "certificate", "document", "documents",
                      "records", "shifting", "drop", "credential", "diploma"],
        "IT / Technical": ["wifi", "wi-fi", "internet", "portal", "password", "account", "login", "computer",
                           "laptop", "printer", "website", "system", "email", "lms"],
        "Student Services": ["guidance", "counseling", "bullying", "id", "clinic", "organization", "event",
                             "discipline", "harassment", "uniform", "health", "medical"],
    }

    def predict(self, text):
        text = prepare_text(text)
        best_category = "Other"
        best_score = 0
        for category in self.KEYWORDS:
            score = 0
            for word in self.KEYWORDS[category]:
                if " " + word + " " in text:
                    score += 1
            if score > best_score:
                best_score = score
                best_category = category
        return best_category


class BaseResponder(ABC):
    @abstractmethod
    def reply(self, title, description, category):
        pass


class RuleResponder(BaseResponder):
    OFFICES = {
        "Academic": "the Program Head / your subject instructor",
        "Facilities": "the Maintenance / Property Office",
        "Finance": "the Cashier / Accounting Office",
        "Registrar": "the Registrar's Office",
        "IT / Technical": "the IT Department",
        "Student Services": "the Guidance / Student Affairs Office",
        "Other": "the Student Affairs Office",
    }

    GENERAL = {
        "Academic": "For concerns about your class, it is best to talk to your subject instructor first. "
                    "If it is still not solved, you can bring it to your Program Head.",
        "Facilities": "Please include the building, the room number and what exactly is broken or dirty "
                      "so that the maintenance staff can find and fix it faster.",
        "Finance": "Please prepare your official receipts and your school ID when you visit the cashier, "
                   "so your account can be checked quickly.",
        "Registrar": "Requests about records and documents are handled by the Registrar. "
                     "Please bring a valid ID and allow a few working days for processing.",
        "IT / Technical": "Please write down the room, the time and the device you used when the problem "
                          "happened. This helps the IT staff check it.",
        "Student Services": "Your concern is important. You are also welcome to visit the office in person "
                            "if you want to talk to somebody.",
        "Other": "We are not sure which office handles this, so a teacher will read it and guide you.",
    }

    TIPS = [
        (["bullying", "harassment", "threat", "abuse"],
         "We are sorry this happened to you. Your safety comes first. Please tell a teacher or go to the "
         "Guidance Office as soon as you can. We marked this concern as important."),
        (["wifi", "wi-fi", "internet"],
         "For WiFi problems, try to forget the network and connect again, then restart your device."),
        (["password", "login", "account", "portal"],
         "For account problems, try the 'forgot password' option first. If it still does not work, "
         "bring your school ID to the IT office so your account can be reset."),
        (["grade", "grades"],
         "For grade concerns, please prepare your quizzes, exams or class record so your instructor can check them."),
        (["tuition", "balance", "payment", "receipt"],
         "For payment concerns, please keep all your official receipts and ask the cashier to check your balance."),
        (["scholarship", "discount"],
         "For scholarship or discount concerns, please bring the requirements or letter you received."),
        (["enroll", "enrollment", "drop", "shifting"],
         "For enrollment concerns, please check with the Registrar the schedule and the requirements for enrollment."),
        (["tor", "transcript", "certificate", "diploma", "document", "documents"],
         "For document requests, please fill out the request form at the Registrar and bring a valid ID."),
        (["aircon", "air-con", "fan", "light", "leak", "broken", "restroom", "comfort"],
         "Thank you for reporting the problem. Please tell us the exact room so it can be checked."),
        (["printer", "computer", "laptop"],
         "For computer or printer problems, please tell us the laboratory and the unit number."),
    ]

    def reply(self, title, description, category):
        text = prepare_text(title + " " + description)
        lines = ["Hello! Thank you for sending your concern."]
        tips_added = 0
        for words, tip in self.TIPS:
            for word in words:
                if " " + word + " " in text:
                    lines.append(tip)
                    tips_added += 1
                    break
            if tips_added == 2:
                break
        lines.append(self.GENERAL[category])
        lines.append("Your concern is under '" + category + "' and was sent to " + self.OFFICES[category] +
                     ". A teacher will follow up. You can check the status in My Concerns.")
        return "\n\n".join(lines)


class ClaudeResponder(BaseResponder):
    def __init__(self, api_key, backup):
        self.api_key = api_key
        self.backup = backup

    def reply(self, title, description, category):
        try:
            question = "Category: " + category + "\nTitle: " + title + "\nConcern: " + description
            body = json.dumps({
                "model": "claude-haiku-4-5-20251001",
                "max_tokens": 300,
                "system": "You are the helpful assistant of ICCT Colleges Foundation Inc. Answer the concern "
                          "of a student politely in 3 to 5 short sentences. Use simple English. Say which "
                          "office can help. Do not invent school policies or promise results. End by telling "
                          "the student that a teacher will follow up.",
                "messages": [{"role": "user", "content": question}],
            }).encode()
            request = urllib.request.Request(
                "https://api.anthropic.com/v1/messages", data=body,
                headers={"x-api-key": self.api_key, "anthropic-version": "2023-06-01",
                         "content-type": "application/json"})
            with urllib.request.urlopen(request, timeout=20) as response:
                result = json.loads(response.read().decode())
            return result["content"][0]["text"]
        except Exception:
            return self.backup.reply(title, description, category)


def make_responder():
    rule_responder = RuleResponder()
    if API_KEY:
        return ClaudeResponder(API_KEY, rule_responder)
    return rule_responder


class Report:
    def __init__(self, db):
        self.db = db

    def make_summary(self):
        rows = self.db.get_concerns()
        lines = ["ICCT STUDENT CONCERN REPORT",
                 "Generated: " + datetime.now().strftime("%Y-%m-%d %H:%M"),
                 "Total concerns: " + str(len(rows)), "", "By Category:"]
        for category in CATEGORIES:
            count = len([r for r in rows if r["category"] == category])
            if count > 0:
                lines.append("  " + category.ljust(20) + str(count))
        lines += ["", "By Status:"]
        for status in STATUSES:
            count = len([r for r in rows if r["status"] == status])
            lines.append("  " + status.ljust(20) + str(count))
        lines += ["", "By Date:"]
        dates = sorted(set(r["date_created"][:10] for r in rows), reverse=True)
        for d in dates:
            count = len([r for r in rows if r["date_created"][:10] == d])
            lines.append("  " + d.ljust(20) + str(count))
        return "\n".join(lines)

    def export_csv(self, path):
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["ID", "Student", "Student No", "Title", "Description", "Category",
                             "Status", "AI Reply", "Teacher Remarks", "Date"])
            for r in self.db.get_concerns():
                writer.writerow([r["id"], r["student_name"], r["student_no"], r["title"], r["description"],
                                 r["category"], r["status"], r["ai_reply"], r["remarks"], r["date_created"]])


class LoginWindow(tk.Tk):
    def __init__(self, db):
        super().__init__()
        self.db = db
        self.user = None
        set_style(self)
        self.title("Login - ICCT Student Concern System")
        self.geometry("400x600")
        self.resizable(False, False)

        self.icct_logo = load_logo("icct_lg")
        self.ccs_logo = load_logo("ccs_lg")
        self.small_logo = load_logo("icct_sm")
        if self.small_logo:
            self.iconphoto(True, self.small_logo)

        header = tk.Frame(self, bg=NAVY)
        header.pack(fill="x")
        logo_box = tk.Frame(header, bg=NAVY)
        logo_box.pack(pady=(20, 8))
        if self.icct_logo:
            tk.Label(logo_box, image=self.icct_logo, bg=NAVY).pack(side="left", padx=10)
        if self.ccs_logo:
            tk.Label(logo_box, image=self.ccs_logo, bg=NAVY).pack(side="left", padx=10)
        tk.Label(header, text="Student Concern System", font=("Segoe UI", 17, "bold"), fg=WHITE, bg=NAVY).pack()
        tk.Label(header, text="ICCT Colleges Foundation Inc.", fg=GOLD, bg=NAVY).pack()
        tk.Label(header, text="College of Computer Studies", font=("Segoe UI", 10, "bold"),
                 fg=GOLD, bg=NAVY).pack(pady=(0, 16))
        tk.Frame(self, bg=GOLD, height=4).pack(fill="x")

        form = ttk.Frame(self, padding=(40, 22))
        form.pack(fill="both", expand=True)
        ttk.Label(form, text="Username").pack(anchor="w")
        self.username_entry = ttk.Entry(form)
        self.username_entry.pack(fill="x", pady=(2, 10))
        ttk.Label(form, text="Password").pack(anchor="w")
        self.password_entry = ttk.Entry(form, show="*")
        self.password_entry.pack(fill="x", pady=(2, 16))
        ttk.Button(form, text="LOGIN", style="Red.TButton", command=self.login).pack(fill="x")
        ttk.Button(form, text="Create Account", style="Blue.TButton",
                   command=self.open_register).pack(fill="x", pady=(8, 0))
        tk.Label(form, text=TAGLINE, font=("Segoe UI", 9, "italic"),
                 fg=NAVY, bg=BG).pack(side="bottom")

        self.bind("<Return>", lambda event: self.login())
        self.username_entry.focus()

    def login(self):
        username = self.username_entry.get().strip()
        password = self.password_entry.get()
        if username == "" or password == "":
            messagebox.showwarning("Missing info", "Please enter your username and password.")
            return
        row = self.db.find_user(username, password)
        if row is None:
            messagebox.showerror("Login failed", "Wrong username or password.")
            return
        self.user = User(row["username"], row["role"], row["full_name"], row["student_no"])
        self.destroy()

    def open_register(self):
        RegisterWindow(self, self.db)


class RegisterWindow(tk.Toplevel):
    def __init__(self, parent, db):
        super().__init__(parent)
        self.parent = parent
        self.db = db
        self.title("Create Account")
        self.geometry("340x470")
        self.resizable(False, False)
        self.configure(bg=BG)
        self.grab_set()

        form = ttk.Frame(self, padding=24)
        form.pack(fill="both", expand=True)
        ttk.Label(form, text="I am a").pack(anchor="w")
        self.role_box = ttk.Combobox(form, values=["Student", "Teacher"], state="readonly")
        self.role_box.set("Student")
        self.role_box.pack(fill="x", pady=(2, 8))
        self.role_box.bind("<<ComboboxSelected>>", self.change_label)

        ttk.Label(form, text="Full Name").pack(anchor="w")
        self.name_entry = ttk.Entry(form)
        self.name_entry.pack(fill="x", pady=(2, 8))
        ttk.Label(form, text="Username").pack(anchor="w")
        self.username_entry = ttk.Entry(form)
        self.username_entry.pack(fill="x", pady=(2, 8))
        ttk.Label(form, text="Password").pack(anchor="w")
        self.password_entry = ttk.Entry(form, show="*")
        self.password_entry.pack(fill="x", pady=(2, 8))
        ttk.Label(form, text="Confirm Password").pack(anchor="w")
        self.confirm_entry = ttk.Entry(form, show="*")
        self.confirm_entry.pack(fill="x", pady=(2, 8))
        self.extra_label = ttk.Label(form, text="Student No.")
        self.extra_label.pack(anchor="w")
        self.extra_entry = ttk.Entry(form)
        self.extra_entry.pack(fill="x", pady=(2, 12))
        ttk.Button(form, text="REGISTER", style="Red.TButton", command=self.register).pack(fill="x")

    def change_label(self, event=None):
        if self.role_box.get() == "Student":
            self.extra_label.config(text="Student No.")
        else:
            self.extra_label.config(text="Teacher Access Code")

    def register(self):
        role = self.role_box.get()
        full_name = self.name_entry.get().strip()
        username = self.username_entry.get().strip()
        password = self.password_entry.get()
        confirm = self.confirm_entry.get()
        extra = self.extra_entry.get().strip()

        if full_name == "":
            messagebox.showwarning("Invalid input", "Please enter your full name.", parent=self)
            return
        if len(username) < 4:
            messagebox.showwarning("Invalid input", "Username must be at least 4 characters.", parent=self)
            return
        if len(password) < 6:
            messagebox.showwarning("Invalid input", "Password must be at least 6 characters.", parent=self)
            return
        if password != confirm:
            messagebox.showwarning("Invalid input", "Passwords do not match.", parent=self)
            return
        if role == "Student" and extra == "":
            messagebox.showwarning("Invalid input", "Please enter your student number.", parent=self)
            return
        if role == "Teacher" and extra != TEACHER_CODE:
            messagebox.showwarning("Invalid input", "Wrong teacher access code.", parent=self)
            return

        student_no = extra if role == "Student" else ""
        try:
            self.db.add_user(username, password, role, full_name, student_no)
        except sqlite3.IntegrityError:
            messagebox.showwarning("Invalid input", "Username already exists.", parent=self)
            return

        messagebox.showinfo("Success", "Account created! You can now log in.", parent=self)
        self.parent.username_entry.delete(0, "end")
        self.parent.username_entry.insert(0, username)
        self.destroy()


class BaseWindow(tk.Tk):
    def __init__(self, db, user):
        super().__init__()
        self.db = db
        self.user = user
        self.logged_out = False
        set_style(self)
        self.title("ICCT Student Concern System - " + user.full_name + " (" + user.role + ")")
        self.geometry("1000x700")
        self.minsize(920, 640)

        self.icct_logo = load_logo("icct_sm")
        self.ccs_logo = load_logo("ccs_sm")
        if self.icct_logo:
            self.iconphoto(True, self.icct_logo)
        self.make_header()

        body = ttk.Frame(self, padding=12)
        body.pack(fill="both", expand=True)
        self.tabs = ttk.Notebook(body)
        self.tabs.pack(fill="both", expand=True)

    def make_header(self):
        header = tk.Frame(self, bg=NAVY)
        header.pack(fill="x")
        if self.icct_logo:
            tk.Label(header, image=self.icct_logo, bg=NAVY).pack(side="left", padx=(14, 0), pady=8)
        if self.ccs_logo:
            tk.Label(header, image=self.ccs_logo, bg=NAVY).pack(side="left", padx=(10, 0), pady=8)
        titles = tk.Frame(header, bg=NAVY)
        titles.pack(side="left", padx=14)
        tk.Label(titles, text="Student Concern System", font=("Segoe UI", 15, "bold"), fg=WHITE, bg=NAVY).pack(anchor="w")
        tk.Label(titles, text="ICCT Colleges Foundation Inc. | College of Computer Studies",
                 font=("Segoe UI", 9), fg=GOLD, bg=NAVY).pack(anchor="w")
        right = tk.Frame(header, bg=NAVY)
        right.pack(side="right", padx=16)
        tk.Label(right, text=self.user.full_name, font=("Segoe UI", 11, "bold"), fg=WHITE, bg=NAVY).pack(anchor="e")
        tk.Label(right, text=self.user.role, font=("Segoe UI", 9), fg=GOLD, bg=NAVY).pack(anchor="e")
        ttk.Button(right, text="Logout", style="Gold.TButton", command=self.logout).pack(anchor="e", pady=(4, 0))
        tk.Frame(self, bg=GOLD, height=4).pack(fill="x")

    def add_tab(self, name):
        tab = ttk.Frame(self.tabs, padding=14)
        self.tabs.add(tab, text=name)
        return tab

    def logout(self):
        self.logged_out = True
        self.destroy()


class StudentWindow(BaseWindow):
    def __init__(self, db, user):
        super().__init__(db, user)
        self.classifier = KeywordClassifier()
        self.responder = make_responder()

        self.submit_tab = self.add_tab("Submit Concern")
        self.mine_tab = self.add_tab("My Concerns")
        self.ask_tab = self.add_tab("Ask AI")
        self.build_submit()
        self.build_mine()
        self.build_ask()
        self.tabs.bind("<<NotebookTabChanged>>", lambda event: self.load_my_concerns())
        self.load_my_concerns()

    def build_submit(self):
        card = make_card(self.submit_tab)
        card.pack(fill="x", padx=40, pady=6)
        form = tk.Frame(card, bg=WHITE)
        form.pack(padx=24, pady=16, fill="x")

        tk.Label(form, text="Send a Concern", font=("Segoe UI", 14, "bold"), fg=NAVY, bg=WHITE).grid(row=0, column=0, columnspan=2, sticky="w")
        tk.Label(form, text=self.user.full_name + "   |   Student No: " + self.user.student_no,
                 fg=RED, bg=WHITE).grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 10))

        tk.Label(form, text="Concern Title", bg=WHITE).grid(row=2, column=0, sticky="w", pady=6)
        self.title_entry = ttk.Entry(form, width=60)
        self.title_entry.grid(row=2, column=1, sticky="w")
        tk.Label(form, text="Description", bg=WHITE).grid(row=3, column=0, sticky="nw", pady=6)
        self.desc_box = tk.Text(form, width=60, height=6, wrap="word", relief="solid", bd=1)
        self.desc_box.grid(row=3, column=1, sticky="w")
        ttk.Button(form, text="SUBMIT CONCERN", style="Red.TButton",
                   command=self.submit).grid(row=4, column=1, sticky="w", pady=(12, 0))

        tk.Label(self.submit_tab, text="AI Assistant Reply", font=("Segoe UI", 12, "bold"),
                 fg=NAVY, bg=BG).pack(anchor="w", padx=40, pady=(12, 4))
        self.category_label = tk.Label(self.submit_tab, text="", fg=RED, bg=BG, font=("Segoe UI", 10, "bold"))
        self.category_label.pack(anchor="w", padx=40)
        self.reply_box = tk.Text(self.submit_tab, height=9, wrap="word", state="disabled", bg=WHITE,
                                 relief="flat", highlightthickness=1, highlightbackground=LINE)
        self.reply_box.pack(fill="x", padx=40, pady=(2, 0))
        show_text(self.reply_box, "After you submit your concern, the AI will answer here.")

    def submit(self):
        title = self.title_entry.get().strip()
        description = self.desc_box.get("1.0", "end").strip()
        if title == "" or description == "":
            messagebox.showwarning("Invalid input", "Please fill in the title and description.")
            return
        if len(description) < 10:
            messagebox.showwarning("Invalid input", "Description is too short (at least 10 characters).")
            return

        self.config(cursor="watch")
        self.update()
        category = self.classifier.predict(title + " " + description)
        reply = self.responder.reply(title, description, category)
        self.config(cursor="")

        self.db.add_concern(self.user, title, description, category, reply)
        self.category_label.config(text="Category chosen by the AI: " + category)
        show_text(self.reply_box, reply)
        self.title_entry.delete(0, "end")
        self.desc_box.delete("1.0", "end")
        self.load_my_concerns()

    def build_mine(self):
        columns = ("id", "title", "category", "status", "date")
        self.my_tree = ttk.Treeview(self.mine_tab, columns=columns, show="headings", height=8)
        for name, width in zip(columns, (40, 320, 140, 110, 140)):
            self.my_tree.heading(name, text=name.title())
            self.my_tree.column(name, width=width)
        for status in STATUS_COLORS:
            self.my_tree.tag_configure(status, background=STATUS_COLORS[status])
        self.my_tree.pack(fill="both", expand=True)
        self.my_tree.bind("<<TreeviewSelect>>", self.show_my_detail)
        ttk.Label(self.mine_tab, text="Details, AI Reply and Teacher's Remarks", style="Title.TLabel").pack(anchor="w", pady=(10, 4))
        self.my_detail = tk.Text(self.mine_tab, height=10, wrap="word", state="disabled", bg=WHITE,
                                 relief="flat", highlightthickness=1, highlightbackground=LINE)
        self.my_detail.pack(fill="x")

    def load_my_concerns(self):
        self.my_tree.delete(*self.my_tree.get_children())
        for r in self.db.get_my_concerns(self.user.username):
            self.my_tree.insert("", "end", iid=str(r["id"]), tags=(r["status"],),
                                values=(r["id"], r["title"], r["category"], r["status"], r["date_created"]))

    def show_my_detail(self, event=None):
        selected = self.my_tree.selection()
        if not selected:
            return
        r = self.db.get_concern(int(selected[0]))
        remarks = r["remarks"] if r["remarks"] else "(no remarks yet)"
        show_text(self.my_detail, "Your concern:\n" + r["description"] + "\n\nAI reply:\n" +
                  r["ai_reply"] + "\n\nTeacher's remarks:\n" + remarks)

    def build_ask(self):
        tk.Label(self.ask_tab, text="Ask the AI Assistant", font=("Segoe UI", 14, "bold"), fg=NAVY, bg=BG).pack(anchor="w")
        tk.Label(self.ask_tab, text="Have a quick question? Type it here. This is not saved as a concern.",
                 bg=BG).pack(anchor="w", pady=(0, 8))
        row = ttk.Frame(self.ask_tab)
        row.pack(fill="x")
        self.ask_entry = ttk.Entry(row)
        self.ask_entry.pack(side="left", fill="x", expand=True)
        self.ask_entry.bind("<Return>", lambda event: self.ask_ai())
        ttk.Button(row, text="Ask", style="Red.TButton", command=self.ask_ai).pack(side="left", padx=(8, 0))
        self.ask_box = tk.Text(self.ask_tab, wrap="word", state="disabled", bg=WHITE, relief="flat",
                               highlightthickness=1, highlightbackground=LINE)
        self.ask_box.pack(fill="both", expand=True, pady=10)

    def ask_ai(self):
        question = self.ask_entry.get().strip()
        if question == "":
            return
        self.config(cursor="watch")
        self.update()
        category = self.classifier.predict(question)
        answer = self.responder.reply("", question, category)
        self.config(cursor="")
        show_text(self.ask_box, "You: " + question + "\n\nAI Assistant (" + category + "):\n" + answer)
        self.ask_entry.delete(0, "end")


class TeacherWindow(BaseWindow):
    def __init__(self, db, user):
        super().__init__(db, user)
        self.report = Report(db)
        self.selected_id = None
        self.chart_data = []

        self.dash_tab = self.add_tab("Dashboard")
        self.manage_tab = self.add_tab("Manage Concerns")
        self.report_tab = self.add_tab("Reports")
        self.build_dashboard()
        self.build_manage()
        self.build_report()
        self.tabs.bind("<<NotebookTabChanged>>", lambda event: self.refresh_all())
        self.refresh_all()

    def build_dashboard(self):
        row = tk.Frame(self.dash_tab, bg=BG)
        row.pack(fill="x")
        self.count_labels = {}
        for name, color in [("Total", NAVY), ("Pending", RED), ("In Progress", DARK_GOLD), ("Resolved", GREEN)]:
            card = make_card(row)
            card.pack(side="left", expand=True, fill="x", padx=6)
            tk.Frame(card, bg=color, height=6).pack(fill="x")
            label = tk.Label(card, text="0", font=("Segoe UI", 28, "bold"), fg=color, bg=WHITE)
            label.pack(pady=(10, 0))
            tk.Label(card, text=name, font=("Segoe UI", 10, "bold"), bg=WHITE).pack(pady=(0, 12))
            self.count_labels[name] = label
        ttk.Label(self.dash_tab, text="Concerns per Category", style="Title.TLabel").pack(anchor="w", pady=(18, 6))
        self.chart = tk.Canvas(self.dash_tab, bg=WHITE, height=290, highlightthickness=1, highlightbackground=LINE)
        self.chart.pack(fill="x", padx=6)
        self.chart.bind("<Configure>", self.draw_chart)

    def draw_chart(self, event=None):
        self.chart.delete("all")
        width = max(self.chart.winfo_width(), 400)
        biggest = max([count for name, count in self.chart_data] + [1])
        left = 170
        max_bar = width - left - 70
        for i, (name, count) in enumerate(self.chart_data):
            y = 14 + i * 38
            self.chart.create_text(14, y + 12, text=name, anchor="w", font=("Segoe UI", 10), fill=TEXT)
            bar = max(int(max_bar * count / biggest), 3)
            color = NAVY if i % 2 == 0 else RED
            self.chart.create_rectangle(left, y, left + bar, y + 24, fill=color, outline="")
            self.chart.create_text(left + bar + 8, y + 12, text=str(count), anchor="w",
                                   font=("Segoe UI", 10, "bold"), fill=NAVY)

    def refresh_dashboard(self):
        rows = self.db.get_concerns()
        self.count_labels["Total"].config(text=str(len(rows)))
        for status in STATUSES:
            self.count_labels[status].config(text=str(len([r for r in rows if r["status"] == status])))
        self.chart_data = [(c, len([r for r in rows if r["category"] == c])) for c in CATEGORIES]
        self.draw_chart()

    def build_manage(self):
        top = ttk.Frame(self.manage_tab)
        top.pack(fill="x")
        ttk.Label(top, text="Search:", style="Title.TLabel").pack(side="left")
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *args: self.load_table())
        ttk.Entry(top, textvariable=self.search_var, width=34).pack(side="left", padx=8)

        columns = ("id", "student", "title", "category", "status", "date")
        self.tree = ttk.Treeview(self.manage_tab, columns=columns, show="headings", height=7)
        for name, width in zip(columns, (40, 150, 260, 130, 100, 130)):
            self.tree.heading(name, text=name.title())
            self.tree.column(name, width=width)
        for status in STATUS_COLORS:
            self.tree.tag_configure(status, background=STATUS_COLORS[status])
        self.tree.pack(fill="both", expand=True, pady=8)
        self.tree.bind("<<TreeviewSelect>>", self.select_concern)

        card = make_card(self.manage_tab)
        card.pack(fill="x")
        inner = tk.Frame(card, bg=WHITE)
        inner.pack(fill="x", padx=12, pady=10)
        tk.Label(inner, text="Concern and AI reply", font=("Segoe UI", 10, "bold"), bg=WHITE).grid(row=0, column=0, sticky="w")
        self.detail_box = tk.Text(inner, height=7, width=62, wrap="word", state="disabled", bg="#F7F8FC", relief="flat")
        self.detail_box.grid(row=1, column=0, rowspan=4, sticky="w", padx=(0, 16))

        self.category_var = tk.StringVar()
        self.status_var = tk.StringVar()
        tk.Label(inner, text="Category", bg=WHITE).grid(row=0, column=1, sticky="w")
        ttk.Combobox(inner, textvariable=self.category_var, values=CATEGORIES, state="readonly",
                     width=18).grid(row=1, column=1, sticky="w")
        tk.Label(inner, text="Status", bg=WHITE).grid(row=0, column=2, sticky="w", padx=(12, 0))
        ttk.Combobox(inner, textvariable=self.status_var, values=STATUSES, state="readonly",
                     width=14).grid(row=1, column=2, sticky="w", padx=(12, 0))
        tk.Label(inner, text="Remarks for the student", bg=WHITE).grid(row=2, column=1, sticky="w", pady=(6, 0))
        self.remarks_entry = ttk.Entry(inner, width=40)
        self.remarks_entry.grid(row=3, column=1, columnspan=2, sticky="we")
        buttons = tk.Frame(inner, bg=WHITE)
        buttons.grid(row=4, column=1, columnspan=2, sticky="e", pady=(8, 0))
        ttk.Button(buttons, text="Save Changes", style="Red.TButton", command=self.save_changes).pack(side="left", padx=4)
        ttk.Button(buttons, text="Delete", style="Blue.TButton", command=self.delete_concern).pack(side="left")

    def load_table(self):
        self.tree.delete(*self.tree.get_children())
        for r in self.db.get_concerns(self.search_var.get().strip()):
            self.tree.insert("", "end", iid=str(r["id"]), tags=(r["status"],),
                             values=(r["id"], r["student_name"], r["title"], r["category"], r["status"], r["date_created"]))

    def select_concern(self, event=None):
        selected = self.tree.selection()
        if not selected:
            return
        self.selected_id = int(selected[0])
        r = self.db.get_concern(self.selected_id)
        if r:
            show_text(self.detail_box, r["description"] + "\n\n--- AI reply ---\n" + r["ai_reply"])
            self.category_var.set(r["category"])
            self.status_var.set(r["status"])
            self.remarks_entry.delete(0, "end")
            self.remarks_entry.insert(0, r["remarks"] or "")

    def save_changes(self):
        if self.selected_id is None:
            messagebox.showwarning("Select", "Please select a concern first.")
            return
        self.db.update_concern(self.selected_id, self.category_var.get(), self.status_var.get(),
                               self.remarks_entry.get().strip())
        self.refresh_all()
        messagebox.showinfo("Saved", "Concern updated.")

    def delete_concern(self):
        if self.selected_id is None:
            messagebox.showwarning("Select", "Please select a concern first.")
            return
        if messagebox.askyesno("Confirm", "Delete this concern?"):
            self.db.delete_concern(self.selected_id)
            self.selected_id = None
            self.refresh_all()

    def build_report(self):
        bar = ttk.Frame(self.report_tab)
        bar.pack(fill="x")
        ttk.Button(bar, text="Refresh", style="Blue.TButton", command=self.refresh_report).pack(side="left")
        ttk.Button(bar, text="Export CSV", style="Gold.TButton", command=self.export_csv).pack(side="left", padx=8)
        self.report_box = tk.Text(self.report_tab, font=("Consolas", 11), state="disabled", bg=WHITE,
                                  relief="flat", highlightthickness=1, highlightbackground=LINE)
        self.report_box.pack(fill="both", expand=True, pady=10)

    def refresh_report(self):
        show_text(self.report_box, self.report.make_summary())

    def export_csv(self):
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if path:
            self.report.export_csv(path)
            messagebox.showinfo("Exported", "Saved to " + path)

    def refresh_all(self):
        self.refresh_dashboard()
        self.load_table()
        self.refresh_report()


def main():
    db = Database()
    while True:
        login = LoginWindow(db)
        login.mainloop()
        if login.user is None:
            break
        if login.user.role == "Teacher":
            window = TeacherWindow(db, login.user)
        else:
            window = StudentWindow(db, login.user)
        window.mainloop()
        if not window.logged_out:
            break


LOGOS = {
    "icct_lg": (
        "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"
        "HO7/AD0EI154GDBEAAAAAElFTkSuQmCC"
    ),
    "icct_sm": (
        "iVBORw0KGgoAAAANSUhEUgAAADIAAAAyCAMAAAAp4XiDAAABgFBMVEXbpKCfoZ3g19neZ2ArUpXWlmlcbJ7a2JnZGRioYl9TLGdU"
        "Y2+Xe5Aoc3CwHTCjnXCQpsj4sxnPvcYaGWrzyx9Zh3hwi6jSxXTm5uuqqv+rzNb///9APoNspc+UIEatwbzRfYUAH4U+gYV9DztV"
        "VarnPUDVYjwAAAD7+/sAAFf///+JiKgDN5IGBWSWmLJUV41oaJT6AQG1t8nr6OspJ3LHyNIWFmtISIaoprd1dZp2eKTQ1tfX2eP8"
        "/PwBKorrVlI2NXr////rSUVyha4zOIT////nOzjqamjod3bY5eaquLi5ycrWRUny2df+/v7Oh4vuQz3mh4d1mo6LhZOqqqqEe6So"
        "p8PspaVZZZuRqaUUJXuQl4/aNjTkKij29/dGRXkAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAIvpp8AAAAYHRSTlP//+P/////////////"
        "///////+/v////+sA/9d//////////8D//8A/v4F/v/+/v7+//z+/v3+/v7//v76q////i7///5s//////////+Q//////8D//v/"
        "////////x//uYwZeAAAGXUlEQVR42nWWiXriOBKAhc2Z+5ik0z09O7M7s0sJYUmWfNuAMYSbEJLOfb3/W2wZ6O10z7bIZxxTv+tQ"
        "qapI/f1q/IWX7vmZoQJcymidd/HBl8Z3QuQ98CWXN5hwPIvisry0zIyc+g56h+Dj7hnr05X0aq1u+7zVXf34NwRVNFrMob70WBJ4"
        "OeGopOzJPk15q1H/2PgRwQfnKqVWApGTJGKtJdSux0FR+tk9/6aIfCUaFxH1qMMjujFoYyDlzMMf2EXjK0O+Ei1fJGkUu+i51Rby"
        "BpcUj0inritEnIrWV4ZsiNdUQJICCPoYFcxOdokr65gF+UgjAAf//NcNQ1aeN85SGsTC8T2PLbLL4Z0xB60NMhx0Fj3L8R2ZMOq3"
        "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"
        "DY0XAAAAAElFTkSuQmCC"
    ),
    "ccs_lg": (
        "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"
        "RU5ErkJggg=="
    ),
    "ccs_sm": (
        "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"
        "ujJOi9exAAAAAElFTkSuQmCC"
    ),
}

if __name__ == "__main__":
    main()