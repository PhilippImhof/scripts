#!/usr/bin/env python3

import csv
import glob
from typing import Dict, List


def fetch_weight_data() -> List[Dict[str, float]]:
    """
    Fetch the weight data from the Samsung Health data export, which is
    a CSV file. Return a list of dicts, one dict per dataset.
    """

    weight_files = glob.glob("com.samsung.health.weight.*.csv")
    if len(weight_files) == 0:
        raise Exception("No weight data found.")
    filename = weight_files[0]

    weight_data = []
    with open(filename, newline="") as f:
        next(f)
        reader = csv.DictReader(f)
        for row in reader:
            try:
                weight = float(row["weight"])
            except ValueError:
                weight = 0
            try:
                height = float(row["height"])
            except ValueError:
                height = 0
            # If body fat is recorded, we will include it. However, Garmin Connect
            # will not show it.
            try:
                fat_mass = float(row["body_fat_mass"])
            except ValueError:
                fat_mass = 0

            weight_data.append(
                {
                    "Date": row["start_time"][0:10],
                    "Weight": weight,
                    "Height": height,
                    "BMI": round(weight / ((height / 100) ** 2), 2),
                    "Fat": round(fat_mass / weight * 100, 1),
                }
            )

    return weight_data


def write_to_file(weight_data: List[Dict[str, float]]) -> None:
    """
    Write the data to a series of CSV files. We can only store a certain number of lines per file,
    because if the files become too large, Garmin Connect will fail importing them. Everything
    below 4 KB seems to be fine.
    """
    LINES_PER_FILE = 75

    dest = None
    lines_written = 0
    columns = list(weight_data[0].keys())
    for wd in weight_data:
        if lines_written % LINES_PER_FILE == 0:
            filename = f"weight-export-{lines_written // LINES_PER_FILE + 1}.csv"
            if hasattr(dest, "close"):
                dest.close()

            dest = open(filename, "w", newline="")
            dest.write("Body\n")
            writer = csv.DictWriter(
                dest, fieldnames=columns, lineterminator="\n", quoting=csv.QUOTE_ALL
            )
            writer.writeheader()

        writer.writerow(wd)
        lines_written += 1

    try:
        dest.close()
    except:
        pass


write_to_file(fetch_weight_data())
