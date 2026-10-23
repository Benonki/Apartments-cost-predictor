import sqlite3
import tkinter as tk
from pathlib import Path
from tkinter import ttk, messagebox

from TableTab import TableTab


DB_FILE = Path(__file__).resolve().parent.parent / "apartments.db"


class ApartmentsApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Analiza rynku nieruchomości – Polska i Melbourne")
        self.geometry("1450x720")
        self.minsize(1000, 550)
        self.connection = None

        self.open_database()
        if self.connection is not None:
            self.create_widgets()

    def create_widgets(self):
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=15, pady=(22, 15))

        table_container = ttk.Frame(self.notebook)
        self.notebook.add(table_container, text="Tabela")

        self.dataset_notebook = ttk.Notebook(table_container)
        self.dataset_notebook.pack(fill="both", expand=True, padx=10, pady=10)

        self.poland_tab = TableTab(
            self.dataset_notebook,
            connection=self.connection,
            table_name="apartments",
        )
        self.dataset_notebook.add(self.poland_tab, text="Polska")

        self.melbourne_tab = TableTab(
            self.dataset_notebook,
            connection=self.connection,
            table_name="apartments_melbourne",
            columns=(
                "id", "suburb", "area_m2", "rooms", "build_year",
                "centre_distance_km", "price_aud",
            ),
            headings={
                "id": "ID",
                "suburb": "Dzielnica",
                "area_m2": "Powierzchnia [m²]",
                "rooms": "Liczba pokoi",
                "build_year": "Rok budowy",
                "centre_distance_km": "Odległość od centrum [km]",
                "price_aud": "Cena [AUD]",
            },
            widths={
                "id": 70,
                "suburb": 150,
                "area_m2": 150,
                "rooms": 120,
                "build_year": 120,
                "centre_distance_km": 210,
                "price_aud": 150,
            },
            price_column="price_aud",
        )
        self.dataset_notebook.add(self.melbourne_tab, text="Melbourne")

        self.table_tab = self.poland_tab
        self.dataset_notebook.bind(
            "<<NotebookTabChanged>>",
            lambda event: setattr(
                self, "table_tab",
                event.widget.nametowidget(event.widget.select()),
            ),
        )

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