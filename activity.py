#!/usr/bin/env python3

import csv
import datetime
import glob
import os
from collections import defaultdict
from typing import Dict, Optional, TextIO


def fetch_floor_data() -> Dict[str, int]:
    """
    Fetch and consolidate the floors climbed data from Samsung Health CSV exports.
    Since floors climbed are recorded multiple times per day, they need to be summed up per date.

    Returns:
        Dict[str, int]: A dictionary mapping dates (YYYY-MM-DD) to total floors climbed.
    """
    floor_files = glob.glob("com.samsung.health.floors_climbed.*.csv")
    if not floor_files:
        raise FileNotFoundError("No floors data found.")

    filename = floor_files[0]
    floor_dict: Dict[str, int] = defaultdict(int)

    with open(filename, newline="") as floor_data:
        next(floor_data)
        reader = csv.DictReader(floor_data)
        for row in reader:
            date = row["start_time"][:10]
            floors = int(float(row["floor"]))
            floor_dict[date] = floors

    return floor_dict


def fetch_calorie_data() -> Dict[str, int]:
    """
    Fetch the calorie data and sum rest and active calories.

    Returns:
        Dict[str, int]: A dictionary mapping dates (YYYY-MM-DD) to total calories burned.
    """

    calorie_files = glob.glob("com.samsung.shealth.calories_burned.details.*.csv")
    if not calorie_files:
        raise FileNotFoundError("No calorie data found.")

    filename = calorie_files[0]
    calorie_dict: Dict[str, int] = {}
    prefix = "com.samsung.shealth.calories_burned."

    with open(filename, newline="") as calories_data:
        next(calories_data)
        reader = csv.DictReader(calories_data)

        for row in reader:
            date = datetime.datetime.fromtimestamp(
                int(row[prefix + "day_time"]) / 1000
            ).strftime("%Y-%m-%d")
            rest_calorie = float(row[prefix + "rest_calorie"])
            active_calorie = float(row[prefix + "active_calorie"])
            calorie_dict[date] = int(round(rest_calorie + active_calorie, 0))

        return calorie_dict


def fetch_activity_data() -> Dict[str, Dict[str, float]]:
    """
    Fetch daily activity data including steps, distance, and activity duration.

    Returns:
        Dict[str, Dict[str, float]]: A dictionary mapping dates (YYYY-MM-DD) to activity stats.
    """

    activity_files = glob.glob("com.samsung.shealth.activity.day_summary.*.csv")
    if not activity_files:
        raise FileNotFoundError("No activity data found.")

    filename = activity_files[0]
    activity_dict: Dict[str, Dict[str, float]] = {}

    with open(filename, newline="") as activity_data:
        next(activity_data)
        reader = csv.DictReader(activity_data)

        for row in reader:
            date = row["day_time"][:10]
            step_count = int(row["step_count"])
            # Samsung Health stores the distance in m, Garmin Connect expects it to be in km.
            distance = round(float(row["distance"]) / 1000, 2)
            calorie = float(row["calorie"])
            # Times are stored in milliseconds.
            run_time = int(row["run_time"]) / 60000
            walk_time = int(row["walk_time"]) / 60000
            activity_dict[date] = {
                "Steps": step_count,
                "Distance": distance,
                "Minutes Lightly Active": int(walk_time),
                "Minutes Very Active": int(run_time),
                "Activity Calories": int(calorie),
            }

        return activity_dict


def merge_data(    floors: Dict[str, int], calories: Dict[str, int], activities: Dict[str, Dict[str, float]]) -> (
        Dict)[str, Dict[str, float]]:
    """
    Merge floors, calorie, and activity data into a single dataset.

    Returns:
        Dict[str, Dict[str, float]]: A dictionary mapping dates (YYYY-MM-DD) to merged activity data.
    """

    merged_data = defaultdict(lambda: {
        "Date": "",
        "Calories Burned": 0,
        "Steps": 0,
        "Distance": 0.0,
        "Floors": 0,
        "Minutes Sedentary": 0,
        "Minutes Lightly Active": 0,
        "Minutes Fairly Active": 0,
        "Minutes Very Active": 0,
        "Activity Calories": 0,
    })

    # Add Calories and Floors data
    for date, calories_value in calories.items():
        merged_data[date]["Calories Burned"] = calories_value

    for date, floors_value in floors.items():
        merged_data[date]["Floors"] = floors_value

    # Add Activities data and ensure the date is set correctly
    for date, activity in activities.items():
        merged_data[date].update(activity)
        merged_data[date]["Date"] = date

    return dict(sorted(merged_data.items()))


def write_to_file(data: Dict[str, Dict[str, float]]) -> None:
    """
    Write merged data to CSV files in chunks of 75 lines per file.

    Garmin Connect has a limit on file sizes, so we generate multiple smaller files.

    Args:
        data: Merged activity data dictionary.
    """

    os.makedirs("Activity_exports", exist_ok=True)

    lines_per_file: int = 75
    lines_written: int = 0
    dest: Optional[TextIO] = None
    writer: Optional[csv.writer] = None

    columns = [
        "Date",
        "Calories Burned",
        "Steps",
        "Distance",
        "Floors",
        "Minutes Sedentary",
        "Minutes Lightly Active",
        "Minutes Fairly Active",
        "Minutes Very Active",
        "Activity Calories",
    ]

    for date, row in data.items():
        if lines_written % lines_per_file == 0:
            filename = f"Activity_exports/activities-export-{lines_written // lines_per_file + 1}.csv"
            if dest:
                dest.close()

            dest = open(filename, "w", newline="")
            dest.write("Activities\n")
            writer = csv.DictWriter(dest, fieldnames=columns, lineterminator="\n", quoting=csv.QUOTE_ALL)
            writer.writeheader()

        writer.writerow(row)
        lines_written += 1

    if dest:
        dest.close()

    print("Export completed successfully.")


if __name__ == "__main__":
    try:
        write_to_file(merge_data(fetch_floor_data(), fetch_calorie_data(), fetch_activity_data()))
    except FileNotFoundError as e:
        print(f"Error: {e}")
