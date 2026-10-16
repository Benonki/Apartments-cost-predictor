import sqlite3
from tkinter import ttk, messagebox


ROWS_PER_PAGE = 250


class TableTab(ttk.Frame):
    def __init__(self, parent, connection, table_name):
        super().__init__(parent)

        self.connection = connection
        self.table_name = table_name
        self.current_page = 0
        self.total_rows = 0

        self.create_widgets()
        self.refresh_count()
        self.load_page()

    def create_widgets(self):
        table_frame = ttk.Frame(self)
        table_frame.pack(fill="both", expand=True, padx=10, pady=(10, 5))

        columns = (
            "id",
            "city",
            "area_m2",
            "rooms",
            "build_year",
            "centre_distance_km",
            "price_pln",
        )

        self.tree = ttk.Treeview(
            table_frame,
            columns=columns,
            show="headings"
        )

        headings = {
            "id": "ID",
            "city": "Miasto",
            "area_m2": "Powierzchnia [m²]",
            "rooms": "Liczba pokoi",
            "build_year": "Rok budowy",
            "centre_distance_km": "Odległość od centrum [km]",
            "price_pln": "Cena [zł]",
        }

        widths = {
            "id": 70,
            "city": 150,
            "area_m2": 150,
            "rooms": 120,
            "build_year": 120,
            "centre_distance_km": 210,
            "price_pln": 150,
        }

        for column in columns:
            self.tree.heading(column, text=headings[column])
            self.tree.column(column, width=widths[column], anchor="center")

        vertical_scrollbar = ttk.Scrollbar(
            table_frame,
            orient="vertical",
            command=self.tree.yview
        )
        horizontal_scrollbar = ttk.Scrollbar(
            table_frame,
            orient="horizontal",
            command=self.tree.xview
        )

        self.tree.configure(
            yscrollcommand=vertical_scrollbar.set,
            xscrollcommand=horizontal_scrollbar.set
        )

        self.tree.grid(row=0, column=0, sticky="nsew")
        vertical_scrollbar.grid(row=0, column=1, sticky="ns")
        horizontal_scrollbar.grid(row=1, column=0, sticky="ew")

        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)

        bottom_frame = ttk.Frame(self)
        bottom_frame.pack(fill="x", padx=10, pady=(5, 10))

        self.prev_button = ttk.Button(
            bottom_frame,
            text="← Poprzednia",
            command=self.previous_page
        )
        self.prev_button.pack(side="left")

        self.page_label = ttk.Label(bottom_frame, text="")
        self.page_label.pack(side="left", padx=15)

        self.next_button = ttk.Button(
            bottom_frame,
            text="Następna →",
            command=self.next_page
        )
        self.next_button.pack(side="left")

        self.count_label = ttk.Label(bottom_frame, text="")
        self.count_label.pack(side="right")

    def refresh_count(self):
        try:
            cursor = self.connection.cursor()
            cursor.execute(f"SELECT COUNT(*) FROM {self.table_name}")
            self.total_rows = cursor.fetchone()[0]
        except sqlite3.Error as error:
            messagebox.showerror("Błąd bazy danych", str(error))
            self.total_rows = 0

    def load_page(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        offset = self.current_page * ROWS_PER_PAGE

        try:
            cursor = self.connection.cursor()
            cursor.execute(
                f"""
                SELECT
                    id,
                    city,
                    area_m2,
                    rooms,
                    build_year,
                    centre_distance_km,
                    price_pln
                FROM {self.table_name}
                ORDER BY id
                LIMIT ? OFFSET ?
                """,
                (ROWS_PER_PAGE, offset),
            )

            for row in cursor.fetchall():
                display_row = list(row)

                if display_row[4] is None:
                    display_row[4] = "brak danych"

                if display_row[6] is not None:
                    display_row[6] = f"{display_row[6]:,}".replace(",", " ")

                self.tree.insert("", "end", values=display_row)

        except sqlite3.Error as error:
            messagebox.showerror("Błąd bazy danych", str(error))
            return

        self.update_pagination_controls()

    def update_pagination_controls(self):
        total_pages = max(1, (self.total_rows + ROWS_PER_PAGE - 1) // ROWS_PER_PAGE)

        self.page_label.config(
            text=f"Strona {self.current_page + 1} z {total_pages}"
        )
        self.count_label.config(
            text=f"Liczba mieszkań w bazie: {self.total_rows}"
        )

        self.prev_button.config(
            state="normal" if self.current_page > 0 else "disabled"
        )
        self.next_button.config(
            state="normal"
            if self.current_page < total_pages - 1
            else "disabled"
        )

    def previous_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self.load_page()

    def next_page(self):
        total_pages = max(1, (self.total_rows + ROWS_PER_PAGE - 1) // ROWS_PER_PAGE)
        if self.current_page < total_pages - 1:
            self.current_page += 1
            self.load_page()