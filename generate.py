#!/usr/bin/env python3

import argparse
import csv
import io
import json
import logging
import os
from urllib.request import Request, urlopen

import openpyxl
import sqlite_utils


def fetch(url):
    return urlopen(
        Request(
            url,
            headers={
                "User-Agent": "NINA-importer/1.0",
            },
        )
    )  # has artsdatabanken blocked Python-urllib/* user-agent?


def parse_csv(fp, encoding="utf-8", lineterminator="\r\n", **kwargs):
    decoded = fp.read().decode(encoding)
    return csv.DictReader(decoded.split(lineterminator), **kwargs)


def parse_excel(fp, sheet):
    buffer = io.BytesIO(fp.read())
    workbook = openpyxl.load_workbook(buffer)
    values = workbook[sheet].values
    header = next(values)
    return (dict(zip(header, row)) for row in values)


def parse_json(fp):
    return json.load(fp)


def autocast(obj):
    for row in obj:
        for key, value in row.items():
            logging.debug("Evaluate value: %s" % value)
            if not isinstance(value, str):
                logging.debug("Keeping type %s" % type(value))
                continue
            for function in (int, float):
                try:
                    row[key] = function(value)
                    logging.debug("Casted to %s" % type(row[key]))
                    break
                except ValueError:
                    pass
            else:
                logging.debug("Fallback to string")
        yield row


def recipe_fab2018():
    url = "https://artsdatabanken.no/Fab2018/api/export/csv"
    logging.info("Fetching " + url)
    return autocast(parse_csv(fetch(url), encoding="utf-16le", delimiter=";"))


def recipe_rodlista():
    url = "https://artsdatabanken.no/lister/rodlisteforarter/2021?Export=true"
    logging.info("Fetching " + url)
    return autocast(parse_excel(fetch(url), "Vurderinger"))


def recipe_ninkode():
    url = "https://nin-kode-api.artsdatabanken.no/v2.3/koder/allekoder"
    logging.info("Fetching " + url)
    for row in autocast(parse_json(fetch(url))):
        yield {
            "KodeId": row["Kode"]["Id"],
            "KodeDefinisjon": row["Kode"]["Definisjon"],
            "OverordnetKodeId": row.get("Overordnet", {}).get("Kode", {}).get("Id"),
            "Navn": row["Navn"],
            "Kategori": row["Kategori"],
        }


def recipe_taxongroups():
    url = "https://artskart.artsdatabanken.no/publicapi/api/lookup?context=taxongroup"
    logging.info("Fetching " + url)
    return autocast(parse_json(fetch(url)))


def recipe_specie_by_group(group):
    url = f"https://artskart.artsdatabanken.no/publicapi/api/taxon?term=&taxonGroups={group}&take=-1"
    logging.info("Fetching " + url)
    for row in parse_json(fetch(url)):
        simple_row = {}
        for key, value in row.items():
            if isinstance(value, dict):
                pass
            elif isinstance(value, list):
                pass
            else:
                simple_row[key] = value
        yield simple_row


def recipe_species():
    for taxongroup in recipe_taxongroups():
        yield from recipe_specie_by_group(taxongroup["Key"])


def main(database_path, recreate):
    db = sqlite_utils.Database(database_path, recreate=recreate)
    db["species"].insert_all(recipe_species(), pk="Id")
    db["fab-2018"].insert_all(recipe_fab2018(), pk="Id")
    db["rødlista-2021"].insert_all(recipe_rodlista(), pk="Id")
    db["ninkode-2_3"].insert_all(recipe_ninkode(), pk="KodeId")
    # db["taxongroups"].insert_all(recipe_taxongroups(), pk="Key")


if __name__ == "__main__":
    logging.basicConfig(level=os.getenv("LOGGING_LEVEL", "WARNING"))
    parser = argparse.ArgumentParser(
        description="Fetch common data from artsdatabanken.no",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--database_path",
        help="Path of the database to create or update",
        default="common.sqlite",
    )
    parser.add_argument(
        "--recreate",
        help="Recreate the database",
        action=argparse.BooleanOptionalAction,
        default=False,
    )
    args = parser.parse_args()
    main(args.database_path, args.recreate)
