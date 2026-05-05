import sqlite3
import csv
import os

DB_NAME = 'travel_data.db'
CSV_FILE = 'destinations.csv'


def init_db():

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute('DROP TABLE IF EXISTS destinations')

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

    if os.path.exists(CSV_FILE):
        with open(CSV_FILE, mode='r', encoding='utf-8') as file:
            reader = csv.DictReader(file)

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
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("SELECT country, city, type, climate, cost_level, popularity, lat, lon, country_code FROM destinations")
    results = cursor.fetchall()

    conn.close()
    return results


if __name__ == "__main__":
    init_db()