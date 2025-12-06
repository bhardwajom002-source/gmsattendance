# school_hackathon_material.py
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sqlite3, os, csv, json
from datetime import datetime
from shutil import copyfile

DB_PATH = "students.db"

# ---------------- Database Setup ----------------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Teacher table
    c.execute('''
    CREATE TABLE IF NOT EXISTS teacher (
        id INTEGER PRIMARY KEY,
        username TEXT UNIQUE,
        password TEXT
    );
    ''')

    # Students table
    c.execute('''
    CREATE TABLE IF NOT EXISTS students (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        sclass TEXT,
        father TEXT,
        mother TEXT,
        aadhar TEXT,
        dob TEXT,
        phone TEXT,
        whatsapp TEXT,
        present INTEGER DEFAULT 0,
        absent INTEGER DEFAULT 0,
        created_at TEXT
    );
    ''')

    # Ensure sclass column exists (fix for old DBs)
    c.execute("PRAGMA table_info(students)")
    cols = [col[1] for col in c.fetchall()]
    if "sclass" not in cols:
        c.execute("ALTER TABLE students ADD COLUMN sclass TEXT")

    # Ensure teacher exists
    c.execute("SELECT id FROM teacher WHERE username = ?", (TEACHER_USERNAME,))
    if not c.fetchone():
        c.execute("INSERT INTO teacher (username, password) VALUES (?, ?)",
                  (TEACHER_USERNAME, DEFAULT_TEACHER_PASSWORD))
    conn.commit()
    conn.close()


# ---------------- Student CRUD ----------------
def add_student(name, dob, sclass, fee_status):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO students (name, dob, sclass, fee_status) VALUES (?, ?, ?, ?)", (name, dob, sclass, fee_status))
    conn.commit()
    conn.close()

def get_students():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM students")
    data = c.fetchall()
    conn.close()
    return data

def update_student(student_id, name, dob, sclass, fee_status):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE students SET name=?, dob=?, sclass=?, fee_status=? WHERE id=?", (name, dob, sclass, fee_status, student_id))
    conn.commit()
    conn.close()

def delete_student(student_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM students WHERE id=?", (student_id,))
    conn.commit()
    conn.close()

# ---------------- Backup ----------------
def backup_db():
    backup_file = f"students_backup_{datetime.now().strftime('%Y%m%d%H%M%S')}.db"
    copyfile(DB_PATH, backup_file)
    messagebox.showinfo("Backup", f"Database backed up as {backup_file}")

# ---------------- CSV Import/Export ----------------
def export_csv():
    students = get_students()
    if not students:
        messagebox.showwarning("Export CSV", "No students to export!")
        return
    file = filedialog.asksaveasfilename(defaultextension=".csv")
    if file:
        with open(file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["ID", "Name", "DOB", "Class", "Fee Status"])
            writer.writerows(students)
        messagebox.showinfo("Export CSV", "CSV exported successfully!")

def import_csv():
    file = filedialog.askopenfilename(filetypes=[("CSV Files", "*.csv")])
    if file:
        with open(file, newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                add_student(row["Name"], row["DOB"], row["Class"], row["Fee Status"])
        messagebox.showinfo("Import CSV", "CSV imported successfully!")
        refresh_tree()

# ---------------- UI ----------------
root = tk.Tk()
root.title("Student Management System")
root.geometry("900x600")
root.configure(bg="#f5f5f5")

style = ttk.Style(root)
style.theme_use("clam")
style.configure("Treeview.Heading", font=('Poppins', 12, 'bold'))
style.configure("Treeview", font=('Poppins', 11), rowheight=25)

# Login Window
def login_ui():
    login_win = tk.Toplevel(root)
    login_win.title("Login")
    login_win.geometry("300x200")
    login_win.configure(bg="#e1f5fe")

    tk.Label(login_win, text="Username:", bg="#e1f5fe").pack(pady=5)
    username_entry = tk.Entry(login_win)
    username_entry.pack(pady=5)
    tk.Label(login_win, text="Password:", bg="#e1f5fe").pack(pady=5)
    password_entry = tk.Entry(login_win, show="*")
    password_entry.pack(pady=5)

    def check_login():
        username = username_entry.get()
        password = password_entry.get()
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT * FROM admin WHERE username=? AND password=?", (username, password))
        if c.fetchone():
            login_win.destroy()
        else:
            messagebox.showerror("Login Failed", "Invalid credentials")
        conn.close()

    tk.Button(login_win, text="Login", command=check_login, bg="#0288d1", fg="white").pack(pady=10)

# Student Table
tree = ttk.Treeview(root, columns=("ID", "Name", "DOB", "Class", "Fee Status"), show="headings")
for col in ("ID", "Name", "DOB", "Class", "Fee Status"):
    tree.heading(col, text=col)
tree.pack(expand=True, fill="both", pady=20, padx=20)

def refresh_tree():
    for i in tree.get_children():
        tree.delete(i)
    for row in get_students():
        tree.insert("", "end", values=row)

# Student Form
def add_student_ui():
    form = tk.Toplevel(root)
    form.title("Add Student")
    form.geometry("300x300")
    form.configure(bg="#e8f5e9")

    tk.Label(form, text="Name:", bg="#e8f5e9").pack(pady=5)
    name_entry = tk.Entry(form)
    name_entry.pack(pady=5)
    tk.Label(form, text="DOB (YYYY-MM-DD):", bg="#e8f5e9").pack(pady=5)
    dob_entry = tk.Entry(form)
    dob_entry.pack(pady=5)
    tk.Label(form, text="Class:", bg="#e8f5e9").pack(pady=5)
    class_entry = tk.Entry(form)
    class_entry.pack(pady=5)
    tk.Label(form, text="Fee Status:", bg="#e8f5e9").pack(pady=5)
    fee_entry = tk.Entry(form)
    fee_entry.pack(pady=5)

    def submit():
        add_student(name_entry.get(), dob_entry.get(), class_entry.get(), fee_entry.get())
        refresh_tree()
        form.destroy()

    tk.Button(form, text="Add", command=submit, bg="#43a047", fg="white").pack(pady=10)

# Buttons
btn_frame = tk.Frame(root, bg="#f5f5f5")
btn_frame.pack(pady=10)

tk.Button(btn_frame, text="Add Student", command=add_student_ui, bg="#0288d1", fg="white").grid(row=0, column=0, padx=5)
tk.Button(btn_frame, text="Delete Selected", command=lambda: delete_selected(), bg="#d32f2f", fg="white").grid(row=0, column=1, padx=5)
tk.Button(btn_frame, text="Export CSV", command=export_csv, bg="#fbc02d").grid(row=0, column=2, padx=5)
tk.Button(btn_frame, text="Import CSV", command=import_csv, bg="#7b1fa2", fg="white").grid(row=0, column=3, padx=5)
tk.Button(btn_frame, text="Backup DB", command=backup_db, bg="#00796b", fg="white").grid(row=0, column=4, padx=5)

def delete_selected():
    sel = tree.selection()
    if sel:
        student_id = tree.item(sel[0])['values'][0]
        delete_student(student_id)
        refresh_tree()
    else:
        messagebox.showwarning("Delete", "No student selected!")

# Initialize DB and login
init_db()
login_ui()
refresh_tree()
root.mainloop()

