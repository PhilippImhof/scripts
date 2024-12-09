#!/usr/bin/env python3


import csv
import datetime
import glob


def fetch_floor_data():
    """
    Fetch and consolidate the floors climbed data. There are normally multiple entries per day,
    because floors climbed seem to be stored whenever they are registered. So we have to group
    them all and add them up.
    """
    floor_files = glob.glob("com.samsung.health.floors_climbed.*.csv")
    if len(floor_files) == 0:
        raise Exception("No floors data found.")
    filename = floor_files[0]

    with open(filename, newline="") as floor_data:
        # Skip first line
        next(floor_data)
        reader = csv.DictReader(floor_data)
        floor_data = {}
        for row in reader:
            date = row["start_time"][0:10]
            floors = int(float(row["floor"]))
            # If there are floors for this date, add the newly read data to the existing value.
            # Otherwise, create a new key.
            if date in floor_data:
                floor_data[date] += floors
            else:
                floor_data[date] = floors

    return floor_data


def fetch_calorie_data():
    """
    Fetch the calorie data.
    """

    calorie_files = glob.glob("com.samsung.shealth.calories_burned.details.*.csv")
    if len(calorie_files) == 0:
        raise Exception("No calorie data found.")
    filename = calorie_files[0]

    with open(filename, newline="") as calories_data:
        # Skip first line
        next(calories_data)
        reader = csv.DictReader(calories_data)
        calorie_data = {}
        prefix = "com.samsung.shealth.calories_burned."
        for row in reader:
            date = datetime.datetime.fromtimestamp(
                int(row[prefix + "day_time"]) / 1000
            ).strftime("%Y-%m-%d")
            rest_calorie = float(row[prefix + "rest_calorie"])
            active_calorie = float(row[prefix + "active_calorie"])
            calorie_data[date] = int(round(rest_calorie + active_calorie, 0))

        return calorie_data


def fetch_activity_data():
    """
    Fetch the activity data.
    """

    activity_files = glob.glob("com.samsung.shealth.activity.day_summary.*.csv")
    if len(activity_files) == 0:
        raise Exception("No activity data found.")
    filename = activity_files[0]

    with open(filename, newline="") as activity_data:
        # Skip first line
        next(activity_data)
        reader = csv.DictReader(activity_data)
        activity_data = {}
        for row in reader:
            try:
                date = datetime.datetime.fromtimestamp(
                    int(row["day_time"]) / 1000
                ).strftime("%Y-%m-%d")
            except ValueError:
                date = datetime.datetime.fromisoformat(
                    row["day_time"]
                ).strftime("%Y-%m-%d")
            step_count = int(row["step_count"])
            # Samsung Health stores the distance in m, Garmin Connect expects it to be in km.
            distance = round(float(row["distance"]) / 1000, 2)
            calorie = float(row["calorie"])
            # Times are stored in milliseconds.
            run_time = int(row["run_time"]) / 60000
            walk_time = int(row["walk_time"]) / 60000
            activity_data[date] = {
                "Steps": step_count,
                "Distance": distance,
                "Minutes Sedentary": 0,  # We set this to zero, because Garmin won't show it anyway.
                "Minutes Lightly Active": int(walk_time),
                "Minutes Fairly Active": 0,
                "Minutes Very Active": int(run_time),
                "Activity Calories": int(calorie),
            }

        return activity_data


def merge_data(floors, calories, activities):
    merged_data = {}

    for date, cals in calories.items():
        merged_data[date] = {"Calories Burned": cals}

    for date, f in floors.items():
        if date not in merged_data:
            merged_data[date]["Calories"] = 0
        merged_data[date]["Floors"] = f

    for date, dic in activities.items():
        # If no steps have been recorded for a given date, we can drop that entry entirely,
        # because that means other data will not be useful anyway: no activity calories, no distance
        # no intensity minutes.
        dropkey = dic["Steps"] == 0
        if date in merged_data:
            if dropkey:
                merged_data.pop(date)
            else:
                merged_data[date].update(dic)
        else:
            merged_data[date] = dic

    return dict(sorted(merged_data.items()))


def write_to_file(data):
    """
    Write the data to a series of CSV files. We can only store a certain number of lines per file,
    because if the files become too large, Garmin Connect will fail importing them.
    Note: Garmin Connect might still show an error message. This does not mean the import failed.
          Please check your data. The CSV files generated will be sorted by date, so when you go
          back in time, you can easily check if your data is there or not.
    """
    LINES_PER_FILE = 100

    dest = None
    lines_written = 0
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
    for d in data:
        # Add the date key to the row.
        data[d]["Date"] = d
        if lines_written % LINES_PER_FILE == 0:
            filename = f"activities-export-{lines_written // LINES_PER_FILE + 1}.csv"
            if hasattr(dest, "close"):
                dest.close()

            dest = open(filename, "w", newline="")
            dest.write("Activities\n")
            writer = csv.DictWriter(
                dest, fieldnames=columns, lineterminator="\n", quoting=csv.QUOTE_ALL
            )
            writer.writeheader()

        writer.writerow(data[d])
        lines_written += 1

    try:
        dest.close()
    except:
        pass


data = merge_data(fetch_floor_data(), fetch_calorie_data(), fetch_activity_data())
write_to_file(data)
