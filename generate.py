#!/usr/bin/env python3

import argparse
import csv
import io
import json
import logging
import os
import sqlite3
from urllib.request import Request, urlopen

import openpyxl
import sqlite_utils
from bs4 import BeautifulSoup


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
    logging.debug("Evaluate value: %s" % obj)
    if isinstance(obj, list):
        return list(map(autocast, obj))
    elif isinstance(obj, dict):
        return {key: autocast(value) for key, value in obj.items()}
    elif isinstance(obj, str):
        for function in (int, float):
            try:
                casted = function(obj)
                logging.debug("Casted to %s" % function)
                return casted
            except ValueError:
                pass
        else:
            logging.debug("Fallback to string")
        return obj
    else:
        logging.debug("Keeping type %s" % type(obj))
        return obj


def recipe_fab2023():
    url = "https://artsdatabanken.no/lister/fremmedartslista/2023?Export=true"
    logging.info("Fetching " + url)
    return autocast(parse_excel(fetch(url), "Vurderinger"))


def recipe_fab2018():
    url = "https://artsdatabanken.no/Fab2018/api/export/csv"
    logging.info("Fetching " + url)
    return autocast(parse_csv(fetch(url), encoding="utf-16le", delimiter=";"))


def recipe_rodlista():
    url = "https://artsdatabanken.no/lister/rodlisteforarter/2021?Export=true"
    logging.info("Fetching " + url)
    return autocast(parse_excel(fetch(url), "Vurderinger"))


def recipe_ninkode_1or2(version):
    url = f"https://nin-kode-api.artsdatabanken.no/{version}/koder/allekoder"
    logging.info("Fetching " + url)
    casted = autocast(parse_json(fetch(url)))
    for row in casted:
        yield {
            "KodeId": row["Kode"]["Id"],
            "KodeDefinisjon": row["Kode"]["Definisjon"],
            "OverordnetKodeId": row.get("Overordnet", {}).get("Kode", {}).get("Id"),
            "Navn": row["Navn"],
            "Kategori": row["Kategori"],
        }


def recipe_ninkode_3(version):
    url = f"https://nin-kode-api.artsdatabanken.no/{version}/variabler/allekoder"
    logging.info("Fetching " + url)
    casted = autocast(parse_json(fetch(url)))
    for row in casted["typer"]:
        yield {
            "KodeId": row["kode"]["id"],
            "KodeDefinisjon": row["kode"]["definisjon"],
            # "OverordnetKodeId"?
            "Navn": row["navn"],
            "Kategori": row["kategori"],
        }


def recipe_ninkode(version):
    if version == "v1" or version.startswith("v2."):
        return recipe_ninkode_1or2(version)
    elif version.startswith("v3."):
        return recipe_ninkode_3(version)
    else:
        raise Exception("Version not supported")


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


def recipe_artsvariabler():
    url = "https://www.artsdatabanken.no/Pages/221282/Kodeliste_artsvariabler"
    soup = BeautifulSoup(fetch(url), features="html.parser")
    rows = soup.find("table").findAll("tr")
    header = [el.text for el in rows[0].findAll("td")]
    artsgruppe = None
    for row in rows[1:]:
        artsgruppe_new, kode, navn = [el.text for el in row.findAll("td")]
        if artsgruppe_new.strip():
            artsgruppe = artsgruppe_new
        yield dict(zip(header, [artsgruppe, kode, navn]))


def main(database_path, recreate):
    connection = sqlite3.connect(database_path)
    db = sqlite_utils.Database(connection, recreate=recreate)
    db["species"].insert_all(recipe_species(), pk="Id")
    db["fab-2023"].insert_all(recipe_fab2023(), pk="Id for vurderingen")
    db["fab-2018"].insert_all(recipe_fab2018(), pk="Id")
    db["rødlista-2021"].insert_all(recipe_rodlista(), pk="Id")
    db["ninkode-2_3"].insert_all(recipe_ninkode(version="v2.3"), pk="KodeId")
    db["ninkode-3_0"].insert_all(recipe_ninkode(version="v3.0"), pk="KodeId")
    db["artsvariabler"].insert_all(recipe_artsvariabler(), pk="Kode")

    # Add FTS Support
    connection.execute(
        'CREATE VIRTUAL TABLE IF NOT EXISTS species_fts USING FTS5(ValidScientificName, tokenize="trigram", content="species", content_rowid="Id");'
    )
    connection.execute(
        "INSERT INTO species_fts (rowid, ValidScientificName) SELECT Id, ValidScientificName FROM species;"
    )
    connection.commit()


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
