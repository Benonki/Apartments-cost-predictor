import sqlite3
from contextlib import closing
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd


BASE_DIR = Path(__file__).resolve().parent
POLAND_CSV = BASE_DIR / "datasets" / "pl" / "apartments_pl_2023_08.csv"
MELBOURNE_CSV = BASE_DIR / "datasets" / "au" / "melb_data.csv"
DB_FILE = BASE_DIR / "apartments.db"
REPORT_FILE = BASE_DIR / "raport_czyszczenia.txt"

POLAND_FIELDS = {
    "city": "city",
    "type": "property_type",
    "squareMeters": "area_m2",
    "rooms": "rooms",
    "buildYear": "build_year",
    "centreDistance": "centre_distance_km",
    "price": "price_pln",
}
MELBOURNE_FIELDS = {
    "Suburb": "suburb",
    "Type": "property_type",
    "Date": "sale_date",
    "BuildingArea": "area_m2",
    "Rooms": "rooms",
    "YearBuilt": "build_year",
    "Distance": "centre_distance_km",
    "Price": "price_aud",
}

LIMITS = {
    "area_m2": (10, 2000),
    "rooms": (1, 20),
    "build_year": (1800, date.today().year),
    "centre_distance_km": (0, 100),
    "price": (1, 100_000_000),
}
INTEGER_COLUMNS = {"rooms", "build_year", "price_pln", "price_aud"}
MIN_GROUP_SIZE = 5
PROPERTY_TYPES = {
    "blockOfFlats": "Blok", "tenement": "Kamienica",
    "apartmentBuilding": "Apartamentowiec",
    "h": "Dom", "u": "Mieszkanie", "t": "Szeregowiec",
}
POLAND_CITY_NAMES = {
    "bialystok": "Białystok", "bydgoszcz": "Bydgoszcz",
    "czestochowa": "Częstochowa", "gdansk": "Gdańsk", "gdynia": "Gdynia",
    "katowice": "Katowice", "krakow": "Kraków", "lodz": "Łódź",
    "lublin": "Lublin", "poznan": "Poznań", "radom": "Radom",
    "rzeszow": "Rzeszów", "szczecin": "Szczecin", "warszawa": "Warszawa",
    "wroclaw": "Wrocław",
}

POLAND_CITY_ALIASES = POLAND_CITY_NAMES | {
    name.casefold(): name for name in POLAND_CITY_NAMES.values()
}


def read_csv(path, fields):
    return pd.read_csv(path, usecols=list(fields)).rename(columns=fields)


def clean_dataset(source, location_col, price_col):
    df = source.copy()
    before = len(df)
    columns = [location_col, "area_m2", "rooms", "build_year",
               "centre_distance_km", price_col]

    metadata = [name for name in ("property_type", "sale_date") if name in df]
    df = df.loc[:, columns + metadata]
    report = {"records_before": before, "fields": {}, "duplicates": 0}

    loc = df[location_col].astype("string").str.strip()
    if location_col == "city":
        normalized = loc.str.casefold().map(POLAND_CITY_ALIASES).fillna(loc)
        report["city_names_normalized"] = int(loc.ne(normalized).fillna(False).sum())
        loc = normalized
    unknown = loc.isna() | loc.eq("").fillna(False)
    report["fields"][location_col] = {
        "missing": int(unknown.sum()), "invalid": 0,
        "filled": int(unknown.sum()),
    }
    df[location_col] = loc.mask(unknown, "nieznana")

    raw_type = (source["property_type"] if "property_type" in source
                else pd.Series("", index=source.index))
    raw_type = raw_type.astype("string").fillna("").str.strip()
    df["property_type"] = raw_type.map(PROPERTY_TYPES).fillna(raw_type).replace("", "Nieznany")
    if "sale_date" in source:
        raw_dates = source["sale_date"].astype("string").str.strip()
        parsed_dates = pd.to_datetime(raw_dates, format="%d/%m/%Y", errors="coerce")
        report["sale_dates_missing_or_invalid"] = int(parsed_dates.isna().sum())
        df["sale_date"] = parsed_dates.dt.strftime("%Y-%m-%d").where(parsed_dates.notna(), None)
    else:
        df["sale_date"] = None

    for col in columns[1:]:
        original = df[col]
        empty = original.isna() | original.astype("string").str.strip().eq("").fillna(False)
        value = pd.to_numeric(original, errors="coerce")
        low, high = LIMITS["price" if col == price_col else col]
        valid = value.between(low, high, inclusive="both").fillna(False)

        if col in {"rooms", "build_year"}:
            valid &= value.mod(1).eq(0).fillna(False)

        wrong = (~empty) & (~valid)
        df[col] = value.where(valid, np.nan).astype("float64")
        df[f"{col}_imputed"] = (~valid).astype("int64")
        report["fields"][col] = {
            "missing": int(empty.sum()), "invalid": int(wrong.sum()),
            "filled": int(df[col].isna().sum()),
        }

    fill_order = ["rooms", "area_m2", "build_year", "centre_distance_km", price_col]
    for col in fill_order:
        global_median = df[col].median()
        if pd.isna(global_median):
            raise ValueError(
                f"W kolumnie '{col}' nie ma żadnej poprawnej wartości. "
                "Nie można wiarygodnie obliczyć mediany do uzupełnień."
            )

        group_sets = ([[location_col]] if col == "rooms" else [
            [location_col, "rooms"], [location_col], ["rooms"]
        ])
        for group_cols in group_sets:
            if not df[col].isna().any():
                break
            grouped = df.groupby(group_cols, dropna=False)[col]
            median_in_group = grouped.transform("median")
            size_in_group = grouped.transform("count")
            df[col] = df[col].fillna(
                median_in_group.where(size_in_group >= MIN_GROUP_SIZE)
            )
        df[col] = df[col].fillna(global_median)

        if col in INTEGER_COLUMNS:
            df[col] = df[col].round().astype("int64")

    report["duplicates"] = int(df.duplicated(subset=columns).sum())
    report["records_after"] = len(df)
    report["missing_after"] = int(df[columns + ["property_type"]].isna().sum().sum())
    if report["missing_after"]:
        raise ValueError("Po czyszczeniu pozostały puste komórki.")

    for col in columns[1:]:
        lower, upper = LIMITS["price" if col == price_col else col]
        if not df[col].between(lower, upper).all():
            raise ValueError(f"Po czyszczeniu kolumna {col} nadal zawiera błędy.")

    return df, report


def db_value(value):
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


def replace_table(connection, table_name, location_col, price_col, frame):
    assert table_name in {"apartments", "apartments_melbourne"}
    assert location_col in {"city", "suburb"}
    assert price_col in {"price_pln", "price_aud"}

    connection.execute(f'DROP TABLE IF EXISTS "{table_name}"')
    connection.execute(f'''
        CREATE TABLE "{table_name}" (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            "{location_col}" TEXT NOT NULL,
            area_m2 REAL NOT NULL,
            rooms INTEGER NOT NULL,
            build_year INTEGER NOT NULL,
            centre_distance_km REAL NOT NULL,
            "{price_col}" INTEGER NOT NULL,
            property_type TEXT NOT NULL,
            sale_date TEXT,
            area_m2_imputed INTEGER NOT NULL CHECK (area_m2_imputed IN (0, 1)),
            rooms_imputed INTEGER NOT NULL CHECK (rooms_imputed IN (0, 1)),
            build_year_imputed INTEGER NOT NULL CHECK (build_year_imputed IN (0, 1)),
            centre_distance_km_imputed INTEGER NOT NULL CHECK (centre_distance_km_imputed IN (0, 1)),
            "{price_col}_imputed" INTEGER NOT NULL CHECK ("{price_col}_imputed" IN (0, 1))
        )
    ''')
    columns = [location_col, "area_m2", "rooms", "build_year",
               "centre_distance_km", price_col, "property_type", "sale_date"]
    columns.extend(f"{name}_imputed" for name in (
        "area_m2", "rooms", "build_year", "centre_distance_km", price_col
    ))
    quoted_columns = ", ".join(f'"{name}"' for name in columns)
    placeholders = ", ".join("?" for _ in columns)
    sql = f'INSERT INTO "{table_name}" ({quoted_columns}) VALUES ({placeholders})'
    records = (
        tuple(db_value(v) for v in row)
        for row in frame[columns].itertuples(index=False, name=None)
    )
    connection.executemany(sql, records)
    connection.execute(
        f'CREATE INDEX "idx_{table_name}_location" '
        f'ON "{table_name}" ("{location_col}")'
    )
    connection.execute(
        f'CREATE INDEX "idx_{table_name}_price" '
        f'ON "{table_name}" ("{price_col}")'
    )


def format_report(name, report):
    lines = [
        f"=== {name} ===",
        f"Rekordów przed: {report['records_before']}",
        f"Rekordów po:    {report['records_after']}",
        "Kolumna                 Brakujące     Niepoprawne    Uzupełnione",
        "-" * 69,
    ]
    for col, stats in report["fields"].items():
        lines.append(
            f"{col:<24} {stats['missing']:>9} {stats['invalid']:>14}"
            f" {stats['filled']:>13}"
        )
    lines.extend([
        f"Puste komórki po czyszczeniu: {report['missing_after']}",
        f"Powtarzające się układy sześciu cech (NIE usuwano): {report['duplicates']}",
        "Uzupełnienia liczb: mediana podobnych nieruchomości lub całego zbioru.",
        "Uwaga: uzupełnione liczby to wartości szacowane, nie oryginalne.",
        "Flagi *_imputed w bazie wskazują wartości uzupełnione (1) i oryginalne (0).",
    ])
    if "sale_dates_missing_or_invalid" in report:
        lines.append(f"Brakujące lub błędne daty sprzedaży (pozostawiono NULL): {report['sale_dates_missing_or_invalid']}")
    if "city_names_normalized" in report:
        lines.append(f"Ujednolicone nazwy miast (wielkie litery i polskie znaki): {report['city_names_normalized']}")
    return "\n".join(lines)


def main():
    for path in (POLAND_CSV, MELBOURNE_CSV):
        if not path.is_file():
            raise FileNotFoundError(
                f"Brak pliku: {path}\n"
                "Oczekiwane foldery: datasets/pl/ i datasets/au/."
            )

    print("Weryfikacja i czyszczenie danych z Polski...")
    poland, poland_report = clean_dataset(
        read_csv(POLAND_CSV, POLAND_FIELDS), "city", "price_pln"
    )
    print("Weryfikacja i czyszczenie danych z Melbourne...")
    melbourne, melbourne_report = clean_dataset(
        read_csv(MELBOURNE_CSV, MELBOURNE_FIELDS), "suburb", "price_aud"
    )

    with closing(sqlite3.connect(DB_FILE)) as connection:
        with connection:
            connection.execute("BEGIN")
            replace_table(connection, "apartments", "city", "price_pln", poland)
            replace_table(
                connection, "apartments_melbourne", "suburb", "price_aud", melbourne
            )

    report_text = "\n\n".join([
        "RAPORT CZYSZCZENIA DANYCH (CSV -> SQLite)",
        f"Zakresy: {LIMITS}. Grupowe mediany wymagają min. {MIN_GROUP_SIZE} wartości.",
        "UWAGA: rekordów z identycznymi sześcioma cechami nie usunięto,",
        "bo mogą dotyczyć odrębnych nieruchomości.",
        format_report("POLSKA", poland_report),
        format_report("MELBOURNE", melbourne_report),
    ])
    REPORT_FILE.write_text(report_text + "\n", encoding="utf-8")
    print("\n" + report_text)
    print(f"\nUtworzono bazę: {DB_FILE}")
    print(f"Raport: {REPORT_FILE}")


if __name__ == "__main__":
    main()
