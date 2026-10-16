import sqlite3
import tkinter as tk
from pathlib import Path
from tkinter import ttk, messagebox

from TableTab import TableTab


DB_FILE = Path(__file__).resolve().parent.parent / "apartments.db"


class SideBookmark(tk.Canvas):
    def __init__(self, parent, text, command):
        super().__init__(
            parent,
            width=122,
            height=54,
            highlightthickness=0,
            bd=0,
            bg=parent.cget("bg"),
            cursor="hand2",
        )
        self.text = text
        self.command = command
        self.active = False
        self.bind("<Button-1>", self._on_click)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.redraw()

    def _on_click(self, _event):
        self.command()

    def _on_enter(self, _event):
        if not self.active:
            self.itemconfig("tab", fill="#e8edf5")

    def _on_leave(self, _event):
        if not self.active:
            self.itemconfig("tab", fill="#dfe6f0")

    def set_active(self, active):
        self.active = active
        self.redraw()

    def redraw(self):
        self.delete("all")

        if self.active:
            fill = "#cfdaf0"
            outline = "#7488a8"
            text_color = "#1f2d3d"
        else:
            fill = "#dfe6f0"
            outline = "#9aa9bf"
            text_color = "#334155"

        self.create_polygon(
            10, 4,
            106, 4,
            116, 14,
            116, 40,
            106, 50,
            10, 50,
            0, 40,
            0, 14,
            smooth=False,
            fill=fill,
            outline=outline,
            width=2,
            tags="tab",
        )
        self.create_text(
            60,
            27,
            text=self.text,
            fill=text_color,
            font=("Segoe UI", 10, "bold" if self.active else "normal"),
            tags="text",
        )
        self.tag_bind("tab", "<Button-1>", self._on_click)
        self.tag_bind("text", "<Button-1>", self._on_click)
        self.tag_bind("tab", "<Enter>", self._on_enter)
        self.tag_bind("text", "<Enter>", self._on_enter)
        self.tag_bind("tab", "<Leave>", self._on_leave)
        self.tag_bind("text", "<Leave>", self._on_leave)


class ApartmentsApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Analiza rynku nieruchomości – Polska i Melbourne")
        self.geometry("1450x720")
        self.minsize(1000, 550)
        self.connection = None
        self.dataset_tabs = {}
        self.dataset_views = {}
        self.active_dataset = None

        self.open_database()
        if self.connection is not None:
            self.create_widgets()

    def create_widgets(self):
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=15, pady=(22, 15))

        table_container = ttk.Frame(notebook)
        notebook.add(table_container, text="Tabela")

        outer_frame = ttk.Frame(table_container)
        outer_frame.pack(fill="both", expand=True, padx=(8, 10), pady=(12, 10))
        outer_frame.columnconfigure(0, weight=1)
        outer_frame.rowconfigure(0, weight=1)

        self.content_holder = ttk.Frame(outer_frame)
        self.content_holder.grid(row=0, column=0, sticky="nsew")
        self.content_holder.columnconfigure(0, weight=1)
        self.content_holder.rowconfigure(0, weight=1)

        bookmarks_frame = tk.Frame(outer_frame, bg=self.cget("bg"))
        bookmarks_frame.grid(row=0, column=1, sticky="ne", padx=(10, 0), pady=(12, 0))

        poland_tab = TableTab(
            self.content_holder,
            connection=self.connection,
            table_name="apartments",
        )
        self.dataset_views["poland"] = poland_tab

        melbourne_columns = (
            "id", "suburb", "area_m2", "rooms", "build_year",
            "centre_distance_km", "price_aud",
        )
        melbourne_headings = {
            "id": "ID",
            "suburb": "Dzielnica",
            "area_m2": "Powierzchnia [m²]",
            "rooms": "Liczba pokoi",
            "build_year": "Rok budowy",
            "centre_distance_km": "Odległość od centrum [km]",
            "price_aud": "Cena [AUD]",
        }
        melbourne_widths = {
            "id": 70,
            "suburb": 150,
            "area_m2": 150,
            "rooms": 120,
            "build_year": 120,
            "centre_distance_km": 210,
            "price_aud": 150,
        }
        melbourne_tab = TableTab(
            self.content_holder,
            connection=self.connection,
            table_name="apartments_melbourne",
            columns=melbourne_columns,
            headings=melbourne_headings,
            widths=melbourne_widths,
            price_column="price_aud",
        )
        self.dataset_views["melbourne"] = melbourne_tab

        for view in self.dataset_views.values():
            view.grid(row=0, column=0, sticky="nsew")
            view.grid_remove()

        self.dataset_tabs["poland"] = SideBookmark(
            bookmarks_frame,
            text="Polska",
            command=lambda: self.show_dataset("poland"),
        )
        self.dataset_tabs["poland"].pack(anchor="ne", pady=(0, 10))

        self.dataset_tabs["melbourne"] = SideBookmark(
            bookmarks_frame,
            text="Melbourne",
            command=lambda: self.show_dataset("melbourne"),
        )
        self.dataset_tabs["melbourne"].pack(anchor="ne")

        self.notebook = notebook
        self.table_tab = poland_tab
        self.poland_tab = poland_tab
        self.melbourne_tab = melbourne_tab

        self.show_dataset("poland")

    def show_dataset(self, dataset_key):
        if dataset_key == self.active_dataset:
            return

        for key, view in self.dataset_views.items():
            if key == dataset_key:
                view.grid()
                view.tkraise()
            else:
                view.grid_remove()

        for key, tab in self.dataset_tabs.items():
            tab.set_active(key == dataset_key)

        self.active_dataset = dataset_key
        self.table_tab = self.dataset_views[dataset_key]

    def open_database(self):
        if not DB_FILE.exists():
            messagebox.showerror(
                "Brak bazy danych",
                f"Nie znaleziono pliku:\n{DB_FILE}\n\n"
                "Najpierw uruchom csv_to_db.py, aby utworzyć apartments.db.",
            )
            self.destroy()
            return

        try:
            connection = sqlite3.connect(DB_FILE)
            table_names = {
                row[0] for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            if not {"apartments", "apartments_melbourne"}.issubset(table_names):
                connection.close()
                messagebox.showerror(
                    "Nieaktualna baza danych",
                    "W bazie brakuje tabeli z Polską lub Melbourne.\n\n"
                    "Uruchom ponownie csv_to_db.py, aby wczytać oba pliki CSV.",
                )
                self.destroy()
                return
            self.connection = connection
        except sqlite3.Error as error:
            messagebox.showerror("Błąd bazy danych", str(error))
            self.destroy()

    def destroy(self):
        if self.connection is not None:
            self.connection.close()
            self.connection = None
        super().destroy()