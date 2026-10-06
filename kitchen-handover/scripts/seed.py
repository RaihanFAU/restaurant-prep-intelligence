"""Idempotent demo/seed data loader.

Run with: python scripts/seed.py   (from the kitchen-handover/ directory,
with the venv active and `alembic upgrade head` already applied).

Safe to re-run — every row is "get or create by its natural key", so
running this twice never creates duplicates. Station/section/product names
here are demo data only, not verified restaurant truth (see
docs/mvp/kitchen-handover.md §28/§6) — edit the CSVs freely.

NOTE: this script no longer seeds demo Worker accounts. The old
"Michael"/"Anna" no-password placeholder workers were the free
worker-selection mechanism removed when real login was added — a Worker
now needs an email + password, which isn't something to fabricate in a
seed script. Create the first real account with `python
scripts/create_admin.py`, then create everyone else through /admin/users.
"""

import csv
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
DATA_DIR = PROJECT_ROOT / "data"

from app.db.session import SessionLocal  # noqa: E402
from app.models import PreparedProduct, Section, Station  # noqa: E402


def get_or_create_station(db, name: str) -> Station:
    station = db.query(Station).filter_by(name=name).first()
    if station is None:
        station = Station(name=name)
        db.add(station)
        db.commit()
        print(f"  + station {name!r}")
    return station


def get_or_create_section(db, station: Station, name: str) -> Section:
    section = db.query(Section).filter_by(station_id=station.id, name=name).first()
    if section is None:
        section = Section(station_id=station.id, name=name)
        db.add(section)
        db.commit()
        print(f"  + section {station.name}/{name!r}")
    return section


def get_or_create_product(db, station: Station, section: Section | None, name_de: str) -> PreparedProduct:
    product = (
        db.query(PreparedProduct)
        .filter_by(station_id=station.id, section_id=section.id if section else None, name_de=name_de)
        .first()
    )
    if product is None:
        product = PreparedProduct(station_id=station.id, section_id=section.id if section else None, name_de=name_de)
        db.add(product)
        db.commit()
        where = f"{station.name}/{section.name}" if section else station.name
        print(f"  + product {where}/{name_de!r}")
    return product


def main() -> None:
    db = SessionLocal()
    try:
        print("Stations:")
        stations: dict[str, Station] = {}
        with open(DATA_DIR / "stations.csv", newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                station = get_or_create_station(db, row["name"])
                stations[station.name] = station

        print("Sections:")
        sections: dict[tuple[str, str], Section] = {}
        with open(DATA_DIR / "sections.csv", newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                station = stations[row["station_name"]]
                section = get_or_create_section(db, station, row["name"])
                sections[(station.name, section.name)] = section

        print("Prepared products:")
        with open(DATA_DIR / "prepared_products.csv", newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                station = stations[row["station_name"]]
                section_name = row["section_name"].strip()
                section = sections[(station.name, section_name)] if section_name else None
                get_or_create_product(db, station, section, row["name_de"])

        print("Seed complete.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
