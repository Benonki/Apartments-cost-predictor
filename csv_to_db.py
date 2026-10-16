import sqlite3
from pathlib import Path

import pandas as pd


CSV_FILE = Path("datasets/apartments_pl_2023_08.csv")
DB_FILE = Path("apartments.db")
TABLE_NAME = "apartments"


def main():
    columns = [
        "city",
        "squareMeters",
        "rooms",
        "buildYear",
        "centreDistance",
        "price",
    ]

    df = pd.read_csv(CSV_FILE, usecols=columns)

    df = df.rename(
        columns={
            "squareMeters": "area_m2",
            "buildYear": "build_year",
            "centreDistance": "centre_distance_km",
            "price": "price_pln",
        }
    )

    df["city"] = df["city"].astype(str).str.strip().str.lower()
    df["area_m2"] = pd.to_numeric(df["area_m2"], errors="coerce")
    df["rooms"] = pd.to_numeric(df["rooms"], errors="coerce").astype("Int64")
    df["build_year"] = pd.to_numeric(df["build_year"], errors="coerce").astype("Int64")
    df["centre_distance_km"] = pd.to_numeric(
        df["centre_distance_km"], errors="coerce"
    )
    df["price_pln"] = pd.to_numeric(df["price_pln"], errors="coerce").astype("Int64")

    df = df.dropna(
        subset=["city", "area_m2", "rooms", "centre_distance_km", "price_pln"]
    )

    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()

        cursor.execute(f"DROP TABLE IF EXISTS {TABLE_NAME}")

        cursor.execute(
            f"""
            CREATE TABLE {TABLE_NAME} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                city TEXT NOT NULL,
                area_m2 REAL NOT NULL,
                rooms INTEGER NOT NULL,
                build_year INTEGER,
                centre_distance_km REAL NOT NULL,
                price_pln INTEGER NOT NULL
            )
            """
        )

        rows = []
        for row in df.itertuples(index=False):
            rows.append(
                (
                    row.city,
                    float(row.area_m2),
                    int(row.rooms),
                    None if pd.isna(row.build_year) else int(row.build_year),
                    float(row.centre_distance_km),
                    int(row.price_pln),
                )
            )

        cursor.executemany(
            f"""
            INSERT INTO {TABLE_NAME}
                (city, area_m2, rooms, build_year, centre_distance_km, price_pln)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            rows,
        )

        cursor.execute(
            f"CREATE INDEX idx_{TABLE_NAME}_city ON {TABLE_NAME}(city)"
        )
        cursor.execute(
            f"CREATE INDEX idx_{TABLE_NAME}_price ON {TABLE_NAME}(price_pln)"
        )

        conn.commit()

        count = cursor.execute(
            f"SELECT COUNT(*) FROM {TABLE_NAME}"
        ).fetchone()[0]

    print(f"Gotowe. Utworzono bazę: {DB_FILE.resolve()}")
    print(f"Tabela: {TABLE_NAME}")
    print(f"Liczba rekordów: {count}")


if __name__ == "__main__":
    main()