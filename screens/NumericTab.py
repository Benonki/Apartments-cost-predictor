import math
import sqlite3
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import numpy as np
import pandas as pd

from analysis_core import descriptive_statistics, finite_pairs, linear_regression
from PlotPanel import PlotPanel


LABELS = {
    "area_m2": "Powierzchnia [m²]", "rooms": "Liczba pokoi",
    "build_year": "Rok budowy", "centre_distance_km": "Odległość od centrum [km]",
    "price_pln": "Cena [PLN]", "price_aud": "Cena [AUD]",
    "city": "Miasto", "suburb": "Dzielnica", "property_type": "Typ nieruchomości",
}
STAT_LABELS = {
    "count": "N", "min": "Minimum", "max": "Maksimum", "mean": "Średnia",
    "std": "Odch. stand.", "median": "Mediana", "q1": "Q1", "q3": "Q3",
    "p10": "Kwantyl 0,1", "p90": "Kwantyl 0,9",
}
PLOT_TYPES = (
    "Histogram", "Wykres pudełkowy", "Wykres wiolinowy",
    "Wykres rozrzutu i regresja", "Wykres słupkowy klas",
    "Wykres kołowy klas", "Szereg czasowy",
)
ALL = "Wszystkie"


def format_number(value):
    if pd.isna(value) or not math.isfinite(float(value)):
        return "nieokreślone"
    return f"{value:,.4f}".rstrip("0").rstrip(".").replace(",", " ")


class NumericTab(ttk.Frame):
    def __init__(self, parent, connection):
        super().__init__(parent)
        self.connection = connection
        self.frames = {}
        self.frame = pd.DataFrame()
        self.statistics = pd.DataFrame()
        self.model = None
        self.dataset = tk.StringVar(value="Polska")
        self.location = tk.StringVar(value=ALL)
        self.property_type = tk.StringVar(value=ALL)
        self.original_only = tk.BooleanVar(value=False)
        self.x_choice = tk.StringVar()
        self.y_choice = tk.StringVar()
        self.variable_choice = tk.StringVar()
        self.category_choice = tk.StringVar()
        self.plot_type = tk.StringVar(value=PLOT_TYPES[0])
        self.prediction_x = tk.StringVar()
        self.summary = tk.StringVar()
        self.regression_text = tk.StringVar()
        self.prediction_text = tk.StringVar()
        self.build_widgets()
        self.refresh_data()

    def build_widgets(self):
        filters = ttk.Frame(self, padding=8)
        filters.pack(fill="x")
        ttk.Label(filters, text="Zbiór:").pack(side="left")
        dataset = ttk.Combobox(filters, textvariable=self.dataset,
                               values=("Polska", "Melbourne"), width=13, state="readonly")
        dataset.pack(side="left", padx=(4, 12))
        dataset.bind("<<ComboboxSelected>>", self.change_dataset)
        ttk.Label(filters, text="Lokalizacja:").pack(side="left")
        self.location_box = ttk.Combobox(filters, textvariable=self.location,
                                         state="readonly", width=20)
        self.location_box.pack(side="left", padx=(4, 12))
        self.location_box.bind("<<ComboboxSelected>>", self.apply_filters)
        ttk.Label(filters, text="Typ:").pack(side="left")
        self.type_box = ttk.Combobox(filters, textvariable=self.property_type,
                                    state="readonly", width=19)
        self.type_box.pack(side="left", padx=(4, 12))
        self.type_box.bind("<<ComboboxSelected>>", self.apply_filters)
        ttk.Checkbutton(filters, text="Tylko bez uzupełnień liczbowych",
                        variable=self.original_only, command=self.apply_filters).pack(side="left")
        ttk.Label(self, textvariable=self.summary, wraplength=1350,
                  padding=(8, 0, 8, 6)).pack(fill="x")

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        stats_tab = ttk.Frame(notebook, padding=6)
        model_tab = ttk.Frame(notebook, padding=8)
        charts_tab = ttk.Frame(notebook, padding=6)
        notebook.add(stats_tab, text="Statystyki opisowe")
        notebook.add(model_tab, text="Korelacja i regresja")
        notebook.add(charts_tab, text="Wykresy")

        ttk.Label(stats_tab, text="Odchylenie standardowe próby (n−1); kwantyle z interpolacją liniową.").pack(anchor="w")
        table_area = ttk.Frame(stats_tab)
        table_area.pack(fill="both", expand=True, pady=8)
        columns = ("variable", *STAT_LABELS)
        self.stats_tree = ttk.Treeview(table_area, columns=columns, show="headings", height=8)
        self.stats_tree.heading("variable", text="Zmienna")
        self.stats_tree.column("variable", width=245, minwidth=180, stretch=False)
        for key, label in STAT_LABELS.items():
            self.stats_tree.heading(key, text=label)
            self.stats_tree.column(key, width=115, minwidth=90, anchor="e", stretch=False)
        self.stats_tree.grid(row=0, column=0, sticky="nsew")
        horizontal = ttk.Scrollbar(table_area, orient="horizontal", command=self.stats_tree.xview)
        horizontal.grid(row=1, column=0, sticky="ew")
        vertical = ttk.Scrollbar(table_area, orient="vertical", command=self.stats_tree.yview)
        vertical.grid(row=0, column=1, sticky="ns")
        self.stats_tree.configure(xscrollcommand=horizontal.set, yscrollcommand=vertical.set)
        table_area.columnconfigure(0, weight=1)
        table_area.rowconfigure(0, weight=1)
        ttk.Button(stats_tab, text="Eksportuj statystyki do CSV", command=self.export_statistics).pack(anchor="w")

        pair_controls = ttk.Frame(model_tab)
        pair_controls.pack(fill="x")
        ttk.Label(pair_controls, text="X:").pack(side="left")
        self.x_box = ttk.Combobox(pair_controls, textvariable=self.x_choice, width=31, state="readonly")
        self.x_box.pack(side="left", padx=(4, 16))
        ttk.Label(pair_controls, text="Y:").pack(side="left")
        self.y_box = ttk.Combobox(pair_controls, textvariable=self.y_choice, width=31, state="readonly")
        self.y_box.pack(side="left", padx=4)
        self.x_box.bind("<<ComboboxSelected>>", self.update_regression)
        self.y_box.bind("<<ComboboxSelected>>", self.update_regression)
        ttk.Label(model_tab, textvariable=self.regression_text, justify="left",
                  wraplength=1250, font=("TkDefaultFont", 11)).pack(anchor="w", pady=18)
        prediction = ttk.LabelFrame(model_tab, text="Oszacowanie Y dla podanego X", padding=12)
        prediction.pack(fill="x")
        ttk.Label(prediction, text="Wartość X:").pack(side="left")
        ttk.Entry(prediction, textvariable=self.prediction_x, width=18).pack(side="left", padx=8)
        ttk.Button(prediction, text="Oblicz", command=self.predict).pack(side="left")
        ttk.Label(model_tab, textvariable=self.prediction_text, wraplength=1250,
                  justify="left").pack(anchor="w", pady=12)
        ttk.Label(model_tab, text=(
            "Regresja opisuje zależność w wybranej próbie. R² i RMSE są obliczone na danych dopasowania; "
            "nie stanowią oceny jakości prognoz na nowych danych. Korelacja nie dowodzi przyczynowości. "
            "Wybierz zmienne X i Y tutaj; wykres rozrzutu korzysta z tej samej pary."
        ), wraplength=1250, justify="left").pack(anchor="w", pady=12)

        chart_controls = ttk.Frame(charts_tab)
        chart_controls.pack(fill="x", pady=(0, 6))
        self.chart_box = ttk.Combobox(chart_controls, textvariable=self.plot_type,
                                      values=PLOT_TYPES, state="readonly", width=26)
        self.chart_box.pack(side="left", padx=(0, 10))
        self.chart_box.bind("<<ComboboxSelected>>", self.draw_plot)
        ttk.Label(chart_controls, text="Zmienna:").pack(side="left")
        self.variable_box = ttk.Combobox(chart_controls, textvariable=self.variable_choice,
                                         state="readonly", width=28)
        self.variable_box.pack(side="left", padx=(4, 10))
        self.variable_box.bind("<<ComboboxSelected>>", self.draw_plot)
        ttk.Label(chart_controls, text="Klasy:").pack(side="left")
        self.category_box = ttk.Combobox(chart_controls, textvariable=self.category_choice,
                                         state="readonly", width=21)
        self.category_box.pack(side="left", padx=4)
        self.category_box.bind("<<ComboboxSelected>>", self.draw_plot)
        self.plot = PlotPanel(charts_tab)
        self.plot.pack(fill="both", expand=True)

    def refresh_data(self):
        self.frames = {}
        try:
            for title, table in (("Polska", "apartments"), ("Melbourne", "apartments_melbourne")):
                self.frames[title] = pd.read_sql_query(f'SELECT * FROM "{table}"', self.connection)
        except (sqlite3.Error, pd.errors.DatabaseError) as error:
            self.summary.set(f"Nie można wczytać danych: {error}")
            return
        self.change_dataset()

    def change_dataset(self, event=None):
        frame = self.frames.get(self.dataset.get(), pd.DataFrame())
        self.location_column = "city" if self.dataset.get() == "Polska" else "suburb"
        self.price_column = "price_pln" if self.dataset.get() == "Polska" else "price_aud"
        self.numeric_columns = [column for column in
                                ("area_m2", "rooms", "build_year", "centre_distance_km", self.price_column)
                                if column in frame]
        self.column_by_label = {LABELS[column]: column for column in self.numeric_columns}
        values = list(self.column_by_label)
        for box in (self.x_box, self.y_box, self.variable_box):
            box.configure(values=values)
        self.x_choice.set(LABELS["area_m2"] if "area_m2" in frame else (values[0] if values else ""))
        self.y_choice.set(LABELS[self.price_column] if self.price_column in frame else (values[-1] if values else ""))
        self.variable_choice.set(self.y_choice.get())
        locations = sorted(frame[self.location_column].dropna().astype(str).unique()) if self.location_column in frame else []
        types = sorted(frame["property_type"].dropna().astype(str).unique()) if "property_type" in frame else []
        self.location_box.configure(values=(ALL, *locations))
        self.type_box.configure(values=(ALL, *types))
        self.location.set(ALL)
        self.property_type.set(ALL)
        category_columns = [column for column in (self.location_column, "property_type", "rooms") if column in frame]
        self.category_by_label = {LABELS[column]: column for column in category_columns}
        self.category_box.configure(values=list(self.category_by_label))
        self.category_choice.set(LABELS[self.location_column] if category_columns else "")
        self.apply_filters()

    def apply_filters(self, event=None):
        frame = self.frames.get(self.dataset.get(), pd.DataFrame()).copy()
        if self.location.get() != ALL and self.location_column in frame:
            frame = frame.loc[frame[self.location_column].astype(str).eq(self.location.get())]
        if self.property_type.get() != ALL and "property_type" in frame:
            frame = frame.loc[frame["property_type"].astype(str).eq(self.property_type.get())]
        flag_columns = [column for column in frame if column.endswith("_imputed")
                        and column.removesuffix("_imputed") in self.numeric_columns]
        imputed = frame[flag_columns].fillna(0).astype(bool).any(axis=1) if flag_columns else pd.Series(False, index=frame.index)
        imputed_count = int(imputed.sum())
        if self.original_only.get():
            frame = frame.loc[~imputed]
        self.frame = frame
        self.summary.set(
            f"{self.dataset.get()}: {len(frame):,} rekordów po filtrach. "
            f"Rekordy z uzupełnieniami liczbowymi przed ostatnim filtrem: {imputed_count:,}. "
            "Polska: mieszkania; Melbourne: różne typy nieruchomości. Waluty analizowane oddzielnie."
        )
        self.statistics = descriptive_statistics(frame, self.numeric_columns)
        self.stats_tree.delete(*self.stats_tree.get_children())
        for column, row in self.statistics.iterrows():
            self.stats_tree.insert("", "end", values=(LABELS[column], *(format_number(value) for value in row)))
        self.update_regression()

    def update_regression(self, event=None):
        self.model = None
        self.prediction_text.set("")
        x_column = self.column_by_label.get(self.x_choice.get())
        y_column = self.column_by_label.get(self.y_choice.get())
        if x_column and y_column:
            try:
                self.model = linear_regression(self.frame[x_column], self.frame[y_column])
                result = self.model
                sign = "+" if result["intercept"] >= 0 else "−"
                self.regression_text.set(
                    f"X: {self.x_choice.get()}    |    Y: {self.y_choice.get()}\n\n"
                    f"Wzór regresji: ŷ = {result['slope']:.6g} · x {sign} {abs(result['intercept']):.6g}\n"
                    f"Pearson r = {format_number(result['r'])}    R² = {format_number(result['r_squared'])}\n"
                    f"RMSE = {format_number(result['rmse'])} (jednostka Y)    Liczba par: {result['n']}\n"
                    f"Zakres obserwowanego X: {format_number(result['x_min'])} – {format_number(result['x_max'])}"
                )
            except ValueError as error:
                self.regression_text.set(str(error))
        else:
            self.regression_text.set("Brak zmiennych do analizy.")
        self.draw_plot()

    def predict(self):
        if self.model is None:
            self.prediction_text.set("Najpierw wybierz parę zmiennych umożliwiającą regresję.")
            return
        try:
            value = float(self.prediction_x.get().replace(" ", "").replace(",", "."))
            if not math.isfinite(value):
                raise ValueError
        except ValueError:
            self.prediction_text.set("Podaj skończoną wartość liczbową X.")
            return
        estimate = self.model["slope"] * value + self.model["intercept"]
        outside = value < self.model["x_min"] or value > self.model["x_max"]
        warning = " Ekstrapolacja: X znajduje się poza zakresem danych, więc oszacowanie jest szczególnie niepewne." if outside else ""
        self.prediction_text.set(f"Oszacowanie {self.y_choice.get()}: {format_number(estimate)}.{warning}")

    def export_statistics(self):
        path = filedialog.asksaveasfilename(parent=self, title="Zapisz statystyki",
                                          defaultextension=".csv", filetypes=(("CSV", "*.csv"),))
        if path:
            try:
                self.statistics.rename(index=LABELS, columns=STAT_LABELS).to_csv(path, encoding="utf-8-sig")
            except OSError as error:
                messagebox.showerror("Błąd zapisu", str(error), parent=self)

    def draw_plot(self, event=None):
        axes = self.plot.reset()
        kind = self.plot_type.get()
        variable = self.column_by_label.get(self.variable_choice.get())
        category = self.category_by_label.get(self.category_choice.get())
        if self.frame.empty or not variable:
            self.plot_message(axes, "Brak danych dla wybranych filtrów.")
            return
        values = pd.to_numeric(self.frame[variable], errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
        if values.empty:
            self.plot_message(axes, "Brak poprawnych wartości wybranej zmiennej.")
            return
        if kind == "Histogram":
            axes.hist(values, bins="auto", color="#3583b8", edgecolor="white")
            axes.set_xlabel(self.variable_choice.get())
            axes.set_ylabel("Liczba rekordów")
        elif kind == "Wykres pudełkowy":
            axes.boxplot(values.to_numpy(), vert=True)
            axes.set_xticks([1], [self.variable_choice.get()])
            axes.set_ylabel(self.variable_choice.get())
        elif kind == "Wykres wiolinowy":
            if len(values) < 2 or values.nunique() < 2:
                axes.axhline(float(values.iloc[0]), color="#3583b8")
                axes.text(0.5, 0.9, "Stała zmienna: brak rozkładu do estymacji gęstości.",
                          transform=axes.transAxes, ha="center")
            else:
                axes.violinplot(values.to_numpy(), showmeans=True, showmedians=True)
            axes.set_xticks([1], [self.variable_choice.get()])
            axes.set_ylabel(self.variable_choice.get())
        elif kind == "Wykres rozrzutu i regresja":
            x_column = self.column_by_label[self.x_choice.get()]
            y_column = self.column_by_label[self.y_choice.get()]
            x, y = finite_pairs(self.frame[x_column], self.frame[y_column])
            axes.scatter(x, y, s=8, alpha=0.25, color="#3583b8", label=f"Obserwacje (n={len(x)})")
            if self.model:
                endpoints = np.array([self.model["x_min"], self.model["x_max"]])
                axes.plot(endpoints, self.model["slope"] * endpoints + self.model["intercept"],
                          color="#d55636", linewidth=2, label="Regresja liniowa")
            axes.set_xlabel(self.x_choice.get())
            axes.set_ylabel(self.y_choice.get())
            axes.legend()
        elif kind in ("Wykres słupkowy klas", "Wykres kołowy klas"):
            if not category:
                self.plot_message(axes, "Wybierz zmienną definiującą klasy.")
                return
            counts = self.frame[category].fillna("nieznana").astype(str).value_counts()
            if len(counts) > 15:
                top = counts.iloc[:14].copy()
                remainder_label = "Pozostałe (łącznie)"
                while remainder_label in top.index:
                    remainder_label += "*"
                top.loc[remainder_label] = counts.iloc[14:].sum()
                counts = top
            if kind == "Wykres słupkowy klas":
                axes.barh(counts.index[::-1], counts.to_numpy()[::-1], color="#3583b8")
                axes.set_xlabel("Liczba rekordów")
                axes.set_ylabel(self.category_choice.get())
            else:
                axes.pie(counts.to_numpy(), labels=counts.index, autopct="%1.1f%%", textprops={"fontsize": 9})
            kind += f" — {self.category_choice.get()} (n={len(self.frame)})"
        elif kind == "Szereg czasowy":
            if "sale_date" not in self.frame or self.frame["sale_date"].isna().all():
                self.plot_message(axes, "Ten zbiór nie zawiera dat sprzedaży.\nWybierz Melbourne, aby zobaczyć szereg czasowy.")
                return
            dates = pd.to_datetime(self.frame["sale_date"], errors="coerce")
            series = pd.DataFrame({"date": dates, "value": self.frame[variable]}).dropna()
            monthly = series.set_index("date")["value"].resample("MS").mean().dropna()
            if monthly.empty:
                self.plot_message(axes, "Brak poprawnych dat i wartości do szeregu czasowego.")
                return
            axes.plot(monthly.index, monthly.to_numpy(), "o-", color="#3583b8", label="Średnia miesięczna")
            if len(monthly) >= 2:
                elapsed = (monthly.index - monthly.index[0]).days.to_numpy(dtype=float)
                trend = linear_regression(elapsed, monthly.to_numpy())
                axes.plot(monthly.index, trend["slope"] * elapsed + trend["intercept"],
                          "--", color="#d55636", label="Historyczny trend liniowy")
            axes.set_xlabel("Miesiąc sprzedaży (bez miesięcy bez obserwacji)")
            axes.set_ylabel(self.variable_choice.get())
            axes.tick_params(axis="x", rotation=25)
            axes.legend()
        axes.set_title(f"{self.dataset.get()} — {kind}")
        if kind != "Wykres kołowy klas" and not kind.startswith("Wykres kołowy klas"):
            axes.grid(axis="y", alpha=0.2)
        self.plot.draw()

    def plot_message(self, axes, text):
        axes.text(0.5, 0.5, text, ha="center", va="center", transform=axes.transAxes)
        axes.set_axis_off()
        self.plot.draw()
