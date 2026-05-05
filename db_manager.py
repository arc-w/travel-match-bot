import sqlite3
import csv
import os

DB_NAME = 'travel_data.db'
CSV_FILE = 'destinations.csv'


def init_db():

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Usuwamy starą tabelę, jeśli istnieje
    cursor.execute('DROP TABLE IF EXISTS destinations')

    # Tworzymy nową strukturę tabeli
    cursor.execute('''
                   CREATE TABLE IF NOT EXISTS destinations
                   (
                       id
                       INTEGER
                       PRIMARY
                       KEY
                       AUTOINCREMENT,
                       country
                       TEXT,
                       city
                       TEXT,
                       type
                       TEXT,
                       climate
                       TEXT,
                       cost_level
                       INTEGER,
                       popularity
                       INTEGER,
                       lat
                       REAL,
                       lon
                       REAL,
                       country_code
                       TEXT
                   )
                   ''')

    # Wczytujemy dane z pliku CSV
    if os.path.exists(CSV_FILE):
        with open(CSV_FILE, mode='r', encoding='utf-8') as file:
            # Używamy DictReader dla wygodnej pracy z nagłówkami kolumn
            reader = csv.DictReader(file)

            # Przygotowujemy dane do wstawienia
            data_to_insert = []
            for row in reader:
                data_to_insert.append((
                    row['country'],
                    row['city'],
                    row['type'],
                    row['climate'],
                    int(row['cost_level']),
                    int(row['popularity']),
                    float(row['lat']),
                    float(row['lon']),
                    row['country_code']
                ))

            # Masowo wstawiamy wszystkie wiersze (wydajniej niż pojedynczo)
            cursor.executemany('''
                               INSERT INTO destinations (country, city, type, climate, cost_level, popularity, lat, lon,
                                                         country_code)
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                               ''', data_to_insert)

        print(f"Baza danych zaktualizowana! Wczytano {len(data_to_insert)} rekordów z {CSV_FILE}.")
    else:
        print(f"BŁĄD: Nie znaleziono pliku {CSV_FILE}!")

    conn.commit()
    conn.close()


def get_all_destinations():
    """
    Pobiera wszystkie kierunki z bazy danych wraz ze szczegółami (m.in. koszt, popularność, współrzędne).
    Logika filtrowania i sprawdzania pogody odbywa się po stronie aplikacji (w main.py).
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("SELECT country, city, type, cost_level, popularity, lat, lon, country_code FROM destinations")
    results = cursor.fetchall()

    conn.close()
    return results


if __name__ == "__main__":
    # Szybki skrypt do ręcznego przeładowania bazy po edycji pliku CSV
    init_db()