import sqlite3
from datetime import date
from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent
DB_FILE = BASE_DIR / "apartments.db"

DATASETS = [
    {
        "path": BASE_DIR / "datasets/pl/apartments_pl_2023_08.csv",
        "table": "apartments",
        "location": "city",
        "price": "price_pln",
        "fields": {
            "city": "city", "type": "property_type", "squareMeters": "area_m2",
            "rooms": "rooms", "buildYear": "build_year",
            "centreDistance": "centre_distance_km", "price": "price_pln",
        },
    },
    {
        "path": BASE_DIR / "datasets/au/melb_data.csv",
        "table": "apartments_melbourne",
        "location": "suburb",
        "price": "price_aud",
        "fields": {
            "Suburb": "suburb", "Type": "property_type", "Date": "sale_date",
            "BuildingArea": "area_m2", "Rooms": "rooms",
            "YearBuilt": "build_year", "Distance": "centre_distance_km",
            "Price": "price_aud",
        },
    },
]

LIMITS = {
    "area_m2": (10, 2000),
    "rooms": (1, 20),
    "build_year": (1800, date.today().year),
    "centre_distance_km": (0, 100),
    "price": (1, 100_000_000),
}
MIN_GROUP_SIZE = 5
INTEGER_COLUMNS = {"rooms", "build_year", "price_pln", "price_aud"}
PROPERTY_TYPES = {
    "blockOfFlats": "Blok", "tenement": "Kamienica",
    "apartmentBuilding": "Apartamentowiec", "h": "Dom",
    "u": "Mieszkanie", "t": "Szeregowiec",
}
CITY_NAMES = {
    "bialystok": "Białystok", "bydgoszcz": "Bydgoszcz",
    "czestochowa": "Częstochowa", "gdansk": "Gdańsk",
    "gdynia": "Gdynia", "katowice": "Katowice", "krakow": "Kraków",
    "lodz": "Łódź", "lublin": "Lublin", "poznan": "Poznań",
    "radom": "Radom", "rzeszow": "Rzeszów", "szczecin": "Szczecin",
    "warszawa": "Warszawa", "wroclaw": "Wrocław",
}
CITY_ALIASES = CITY_NAMES | {name.casefold(): name for name in CITY_NAMES.values()}


def clean_dataset(data, location, price):
    df = data.copy()

    names = df[location].astype("string").str.strip()
    if location == "city":
        names = names.str.casefold().map(CITY_ALIASES).fillna(names)
    df[location] = names.mask(names.isna() | names.eq(""), "nieznana")

    types = df["property_type"].astype("string").fillna("").str.strip()
    df["property_type"] = types.map(PROPERTY_TYPES).fillna(types).replace("", "Nieznany")

    if "sale_date" in df:
        dates = pd.to_datetime(df["sale_date"], format="%d/%m/%Y", errors="coerce")
        df["sale_date"] = dates.dt.strftime("%Y-%m-%d").where(dates.notna(), None)
    else:
        df["sale_date"] = None

    numeric_cols = ["area_m2", "rooms", "build_year", "centre_distance_km", price]
    for col in numeric_cols:
        values = pd.to_numeric(df[col], errors="coerce")
        low, high = LIMITS["price" if col == price else col]
        valid = values.between(low, high).fillna(False)
        if col in {"rooms", "build_year"}:
            valid &= values.mod(1).eq(0).fillna(False)
        df[col] = values.where(valid, float("nan")).astype("float64")
        df[f"{col}_imputed"] = (~valid).astype("int64")

    for col in ["rooms", "area_m2", "build_year", "centre_distance_km", price]:
        median = df[col].median()
        if pd.isna(median):
            raise ValueError(f"Nie ma poprawnych wartości w kolumnie: {col}")

        groups = ([[location]] if col == "rooms" else
                  [[location, "rooms"], [location], ["rooms"]])
        for group in groups:
            if not df[col].isna().any():
                break
            grouped = df.groupby(group, dropna=False)[col]
            replacement = grouped.transform("median").where(
                grouped.transform("count") >= MIN_GROUP_SIZE
            )
            df[col] = df[col].fillna(replacement)
        df[col] = df[col].fillna(median)

        if col in INTEGER_COLUMNS:
            df[col] = df[col].round().astype("int64")

    if df[[location, "property_type", *numeric_cols]].isna().any().any():
        raise ValueError("Po czyszczeniu nadal występują brakujące wartości.")
    for col in numeric_cols:
        low, high = LIMITS["price" if col == price else col]
        if not df[col].between(low, high).all():
            raise ValueError(f"Po czyszczeniu pozostały błędne wartości: {col}")

    return df


def replace_table(db, config, df):
    table, location, price = config["table"], config["location"], config["price"]
    db.execute(f'DROP TABLE IF EXISTS "{table}"')
    db.execute(f'''
        CREATE TABLE "{table}" (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            "{location}" TEXT NOT NULL,
            area_m2 REAL NOT NULL,
            rooms INTEGER NOT NULL,
            build_year INTEGER NOT NULL,
            centre_distance_km REAL NOT NULL,
            "{price}" INTEGER NOT NULL,
            property_type TEXT NOT NULL,
            sale_date TEXT,
            area_m2_imputed INTEGER NOT NULL CHECK (area_m2_imputed IN (0, 1)),
            rooms_imputed INTEGER NOT NULL CHECK (rooms_imputed IN (0, 1)),
            build_year_imputed INTEGER NOT NULL CHECK (build_year_imputed IN (0, 1)),
            centre_distance_km_imputed INTEGER NOT NULL CHECK (centre_distance_km_imputed IN (0, 1)),
            "{price}_imputed" INTEGER NOT NULL CHECK ("{price}_imputed" IN (0, 1))
        )
    ''')

    cols = [location, "area_m2", "rooms", "build_year", "centre_distance_km",
            price, "property_type", "sale_date"]
    cols += [f"{col}_imputed" for col in
             ("area_m2", "rooms", "build_year", "centre_distance_km", price)]
    column_names = ", ".join(f'"{col}"' for col in cols)
    marks = ", ".join("?" for _ in cols)
    records = (
        tuple(None if pd.isna(v) else v.item() if hasattr(v, "item") else v
              for v in row)
        for row in df[cols].itertuples(index=False, name=None)
    )
    db.executemany(f'INSERT INTO "{table}" ({column_names}) VALUES ({marks})', records)
    db.execute(f'CREATE INDEX "idx_{table}_location" ON "{table}" ("{location}")')
    db.execute(f'CREATE INDEX "idx_{table}_price" ON "{table}" ("{price}")')


def main():
    cleaned = []
    for config in DATASETS:
        if not config["path"].is_file():
            raise FileNotFoundError(f'Nie znaleziono pliku: {config["path"]}')
        source = pd.read_csv(config["path"], usecols=list(config["fields"]))
        source = source.rename(columns=config["fields"])
        cleaned.append(clean_dataset(source, config["location"], config["price"]))

    with sqlite3.connect(DB_FILE) as db:
        for config, df in zip(DATASETS, cleaned):
            replace_table(db, config, df)

    print("Konwersja zakończona pomyślnie.")


if __name__ == "__main__":
    main()
