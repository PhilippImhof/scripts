#!/usr/bin/env python3

import csv
import glob
import os
from typing import List, Tuple, Optional, TextIO


def fetch_weight_data() -> List[Tuple[str, float, float, float, float]]:
    """
    Fetch weight data from the Samsung Health CSV export.

    Returns:
        List[Tuple[str, float, float, float, float]]:
        A list of tuples containing:
        - Date (YYYY-MM-DD)
        - Weight (kg)
        - Height (cm)
        - BMI
        - Fat percentage
    """

    weight_files = glob.glob("com.samsung.health.weight.*.csv")
    if not weight_files:
        raise FileNotFoundError("No weight data found.")

    filename: str = weight_files[0]
    weight_data = []

    with open(filename, newline="", encoding="utf-8") as file:
        next(file)
        reader = csv.reader(file)

        # Extract column headers
        headers = next(reader, None)
        if not headers:
            raise ValueError("CSV file is empty.")

        try:
            idx_weight = headers.index("weight")
            idx_height = headers.index("height")
            idx_fat_mass = headers.index("body_fat_mass")
            idx_start_time = headers.index("start_time")
        except ValueError as e:
            raise KeyError(f"Missing required column: {e}")

        for row in reader:
            try:
                weight = float(row[idx_weight])
            except (ValueError, IndexError):
                continue  # Skip invalid weight entries

            height = float(row[idx_height]) if row[idx_height] else 178.0
            fat_mass = float(row[idx_fat_mass]) if row[idx_fat_mass] else 0.0

            bmi = round(weight / ((height / 100) ** 2), 2) if height else 0.0
            fat_percentage = round(fat_mass / weight * 100, 1) if fat_mass else 0.0
            date = row[idx_start_time][:10]

            weight_data.append((date, weight, height, bmi, fat_percentage))

    return weight_data


def write_to_file(weight_data: List[Tuple[str, float, float, float, float]]) -> None:
    """
    Writes weight data into CSV files, ensuring each file remains small enough for Garmin Connect import.

    Args:
        weight_data (List[Tuple[str, float, float, float, float]]): Processed weight records.
    """

    if not weight_data:
        print("No valid weight data to export.")
        return

    os.makedirs("Weight_exports", exist_ok=True)

    lines_per_file: int = 75
    lines_written: int = 0
    dest: Optional[TextIO] = None
    writer: Optional[csv.writer] = None

    columns = ["Date", "Weight", "Height", "BMI", "Fat"]

    for wd in weight_data:
        if lines_written % lines_per_file == 0:
            if dest:
                dest.close()

            filename = f"weight-export-{lines_written // lines_per_file + 1}.csv"
            dest = open(f"Weight_exports/{filename}", "w", newline="")
            dest.write("Body\n")
            writer = csv.writer(dest, lineterminator="\n", quoting=csv.QUOTE_ALL)
            writer.writerow(columns)

        if writer:
            writer.writerow(wd)

        lines_written += 1

    if dest:
        dest.close()


if __name__ == "__main__":
    try:
        weight_data = fetch_weight_data()
        write_to_file(weight_data)
        print("Export completed successfully.")
    except Exception as e:
        print(f"Error: {e}")
