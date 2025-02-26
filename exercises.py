#!/usr/bin/env python3

import csv
import datetime
import glob
import io
import json
import os
from lxml import etree
from typing import List, Dict, Optional


# Define the various namespaces
nsmap = {
    None: "http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2",
    "ns2": "http://www.garmin.com/xmlschemas/UserProfile/v2",
    "ns3": "http://www.garmin.com/xmlschemas/ActivityExtension/v2",
    "ns4": "http://www.garmin.com/xmlschemas/ProfileExtension/v1",
    "ns5": "http://www.garmin.com/xmlschemas/ActivityGoals/v1",
    "xsi": "http://www.w3.org/2001/XMLSchema-instance",
}

def ns3_tag(name: str) -> etree.QName:
    """ Return the QName for ns3 namespace. """
    return etree.QName(nsmap["ns3"], name)


def fetch_exercise_list() -> List[Dict[str, str]]:
    """
    Fetches the list of exercises from Samsung's CSV file.

    Returns:
        List of exercise data, where each entry is a dictionary.
    """

    exercise_files = glob.glob("com.samsung.shealth.exercise.*.csv")
    if not exercise_files:
        raise FileNotFoundError("No exercise data found.")

    filename = exercise_files[0]
    prefix = "com.samsung.health.exercise."
    fields = [
        prefix + "datauuid",
        prefix + "start_time",
        "total_calorie",
        prefix + "duration",
        prefix + "exercise_type",
        "heart_rate_sample_count",
        prefix + "mean_heart_rate",
        prefix + "max_heart_rate",
        prefix + "min_heart_rate",
        prefix + "mean_speed",
        prefix + "max_speed",
        prefix + "mean_cadence",
        prefix + "max_cadence",
        prefix + "distance",
        prefix + "location_data",
        prefix + "live_data",
    ]

    with open(filename, newline="") as exercise_list:
        # Skip first line
        next(exercise_list)
        reader = csv.DictReader(exercise_list)
        data = []
        for row in reader:
            dataset = {}
            for field in fields:
                dataset[field.replace(prefix, "")] = row[field]
            data.append(dataset)

        return data


def fetch_json_data(uuid: str, data_type: str) -> Dict:
    """Fetch JSON data (either live or location data) from file."""
    filename = f"jsons/com.samsung.shealth.exercise/{uuid[0]}/{uuid}.com.samsung.health.exercise.{data_type}.json"
    try:
        with open(filename, encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError:
        return {}


def create_lap(
    start_time: str,
    duration: Optional[str],
    distance: Optional[str],
    calories: Optional[str],
    avg_hr: Optional[str] = "",
    max_hr: Optional[str] = "",
    avg_speed: Optional[str] = "",
    max_speed: Optional[str] = "",
    avg_cadence: Optional[str] = "",
    max_cadence: Optional[str] = "",
) -> etree.Element:
    """
    Take the retrieved and calculated data to create a <Lap> tag.
    The StartTime attribute is required. Every <Lap> must have
    a <TotalTimeSeconds>, a <DistanceMeters>, a <Calories>, an <Intensity>
    and a <TriggerMethod> tag. The following tags are optional:
     * <MaximumSpeed>
     * <AverageHeartRateBpm>
     * <Cadence>
     * <Track>
     * <Notes>, note that these will not be shown in Garmin Connect
     * <Extensions>, which can contain AvgSpeed, AvgRunCadence and MaxRunCadence
    The order and requirements are described in the schemas:
    https://www8.garmin.com/xmlschemas/TrainingCenterDatabasev2.xsd
    https://www8.garmin.com/xmlschemas/ActivityExtensionv2.xsd
    """
    lap = etree.Element("Lap", {"StartTime": start_time})
    if duration:
        duration = int(duration) / 1000
        etree.SubElement(lap, "TotalTimeSeconds").text = str(duration)
    if distance:
        etree.SubElement(lap, "DistanceMeters").text = distance
    if max_speed:
        etree.SubElement(lap, "MaximumSpeed").text = max_speed
    if calories:
        etree.SubElement(lap, "Calories").text = str(int(round(float(calories), 0)))
    if avg_hr and avg_hr != "0.0":
        ahr = etree.SubElement(lap, "AverageHeartRateBpm")
        etree.SubElement(ahr, "Value").text = str(int(float(avg_hr)))
    if max_hr and avg_hr != "0.0":
        mhr = etree.SubElement(lap, "MaximumHeartRateBpm")
        etree.SubElement(mhr, "Value").text = str(int(float(max_hr)))

    etree.SubElement(lap, "Intensity").text = "Active"
    etree.SubElement(lap, "TriggerMethod").text = "Manual"

    if avg_speed or avg_cadence or max_cadence:
        ext = etree.SubElement(lap, "Extensions")
        lx = etree.SubElement(ext, ns3_tag("LX"))
        if avg_speed and avg_speed != "0.0":
            etree.SubElement(lx, ns3_tag("AvgSpeed")).text = avg_speed
        if avg_cadence and avg_cadence != "0.0":
            etree.SubElement(lx, ns3_tag("AvgRunCadence")).text = avg_cadence
        if max_cadence and max_cadence != "0.0":
            etree.SubElement(lx, ns3_tag("MaxRunCadence")).text = max_cadence

    return lap


def create_trackpoint(data: Dict[str, str]) -> Optional[etree.Element]:
    """
    Take the retrieved and calculated data to create a <Trackpoint> tag.
    Every <Trackpoint> must have a <Time> tag. The following tags are optional:
     * <Position>, containing latitude and longitude in degrees
     * <AltitudeMeters>
     * <DistanceMeters>
     * <HeartRateBpm>, note: this must be an integer
     * <Cadence>
     * <SensorState>
     * <Extensions>, which can contain Speed or RunCadence
    The order and requirements are described in the schemas:
    https://www8.garmin.com/xmlschemas/TrainingCenterDatabasev2.xsd
    https://www8.garmin.com/xmlschemas/ActivityExtensionv2.xsd

    Note: We will not use AltitudeMeters and DistanceMeters, because they will interfere
    with the values that Garmin Connect calculates based on the GPS coordinates. This
    can lead to strange effects when viewing the activity details. The same is valid for the
    trackpoint extension Speed.
    """
    trackpoint = etree.Element("Trackpoint")
    etree.SubElement(trackpoint, "Time").text = data["time"]

    if "altitude" in data and "longitude" in data:
        position = etree.SubElement(trackpoint, "Position")
        etree.SubElement(position, "LatitudeDegrees").text = str(data["latitude"])
        etree.SubElement(position, "LongitudeDegrees").text = str(data["longitude"])

    if "heart_rate" in data:
        hr = etree.SubElement(trackpoint, "HeartRateBpm")
        etree.SubElement(hr, "Value").text = str(data["heart_rate"])

    if "cadence" in data:
        etree.SubElement(trackpoint, "Cadence").text = str(data["cadence"])

    return trackpoint if len(trackpoint) > 1 else None


def create_activity(a_id: str, sport: str = "Other") -> etree.Element:
    """
    Take the retrieved and calculated data to create an <Activity> tag.
    Every <Activity> must have an <Id> tag. The following tags are optional:
     * <Position>, containing latitude and longitude in degrees
     * <Lap>
     * <Notes>, note: they will not be shown in Garmin Connect
     * <Training>
     * <Creator>
     * <Extensions>
    The <Activity> must have the "Sport" attibute which must be set to "Running"
    or "Biking" or "Other". Although there are many very specific activity types
    in Garmin Connect, those cannot be used in a TCX file.
    """
    activity = etree.Element("Activity", {"Sport": sport})
    etree.SubElement(activity, "Id").text = a_id

    return activity


def create_root() -> etree.Element:
    """
    Prepare the root element for the TCX XML structure.
    """
    attr_qname = etree.QName(nsmap["xsi"], "schemaLocation")
    root = etree.Element(
        "TrainingCenterDatabase",
        {
            attr_qname: "http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2 "
                        "http://www.garmin.com/xmlschemas/TrainingCenterDatabasev2.xsd"
        },
        nsmap=nsmap,
    )
    etree.SubElement(root, "Activities")

    return root


def build_xml(a_id: str, ex_type: str, lap: etree.Element, trackpoints: List[etree.Element] = []) -> bytes:
    """
    Build the TCX XML file using provided activity data.
    """
    root = create_root()
    activity = create_activity(a_id, ex_type)
    track = etree.Element("Track")
    root.find("*").append(activity)
    activity.append(lap)

    for trackpoint in trackpoints:
        if trackpoint is not None:
            track.append(trackpoint)

    # We only add the track, if it contains at least one trackpoint.
    if len(track) > 0:
        lap.append(track)

    return etree.tostring(root, pretty_print=True, encoding="utf-8", xml_declaration=True)


def convert_activity_type(sport_type: str) -> str:
    """
    This converts Samsung Health's exercise type to a valid sport type for the <Activity>.
    Although Garmin Connect has a wide range of very specific activity types, we can only use
    "Running", "Biking" or "Other" in a TCX file.

    The corresponding types used in Samsung Health are 1002 (running) and 11007 (cycling). For
    a complete list of all exercise types, see:
    https://developer.samsung.com/health/android/data/api-reference/EXERCISE_TYPE.html
    """
    sport_map = {
        "1002": "Running",
        "11007": "Biking"
    }

    return sport_map.get(sport_type, "Other")


def find_nearest_time(ts: int, timestamps: List[int]) -> int:
    """
    This function searches data and finds the timestamp that is closes to ts.
    We need this to avoid having e.g. trackpoints with a heart rate, but no
    GPS information. Garmin Connect will not properly handle that, and we get strange
    results. So it is better to lose some accuracy by shifting the live data a bit.
    """
    return min(timestamps, key=lambda timestamp: abs(timestamp - ts))


def merge_location_and_live_data(locationdata: List[Dict[str, int]], livedata: List[Dict[str, int]]) -> (
        Dict)[int, Dict[str, str]]:
    """
    Merge location data and live data. This includes shifting live data a bit, so it is
    linked to a position. Also, we will duplicate heart rate data to all following trackpoints,
    until we get a new heart rate. Without this, the heart rate will not be shown correctly in
    Garmin Connect. Instead of having a nice diagram, the user will just see a few spikes and
    heart rate will be counted as zero for the trackpoints where HR data is missing.
    """
    merged_data = {}

    for entry in locationdata:
        # Convert the timestamp (milliseconds from Unix epoch) to the proper format.
        time = datetime.datetime.fromtimestamp(entry["start_time"] / 1000, datetime.timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%S.000Z")
        merged_data[entry["start_time"]] = {
            "time": time,
            "latitude": entry["latitude"],
            "longitude": entry["longitude"],
            "altitude": entry.get("altitude")
        }

    # Now for the live data...
    timestamps = list(sorted(map(lambda d: d["start_time"], locationdata)))
    for entry in livedata:
        ts = entry.get("start_time") or entry.get("StartTime")
        ts = ts if ts in merged_data else find_nearest_time(ts, timestamps)

        time = datetime.datetime.fromtimestamp(ts / 1000, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        entry["heart_rate"] = int(entry["heart_rate"]) if "heart_rate" in entry else None

        if ts not in merged_data:
            merged_data[ts] = {"time": time}

        merged_data[ts].update(
            {key: entry.get(key) for key in ["distance", "cadence", "heart_rate", "speed"] if entry.get(key)})

    return merged_data


def prepare_exercise_data(exercise: Dict[str, str]) -> Optional[bytes]:
    """
    Fetch and merge the data for the given exercise and create proper XML.
    """

    # The time code is used as the Id and StartTime for the lap. It is almost in the right format,
    # we just need to add the T separator between the date and the time and append a Z for the UTC
    # time zone.
    time = exercise.get("start_time").replace(" ", "T") + "Z"
    ex_type = convert_activity_type(exercise["exercise_type"])

    lap = create_lap(
        time,
        exercise["duration"],
        exercise["distance"],
        exercise["total_calorie"],
        exercise["mean_heart_rate"],
        exercise["max_heart_rate"],
        exercise["mean_speed"],
        exercise["max_speed"],
        exercise["mean_cadence"],
        exercise["max_cadence"],
    )

    location_data = fetch_json_data(exercise["datauuid"], "location_data")
    if not location_data:
        return None

    live_data = fetch_json_data(exercise["datauuid"], "live_data")

    data = merge_location_and_live_data(location_data, live_data)
    trackpoints = []
    for d in data:
        trackpoint = create_trackpoint(data[d])
        if trackpoint:
            trackpoints.append(trackpoint)

    return build_xml(time, ex_type, lap, trackpoints)


def write_to_file(filename: str, xml: bytes) -> None:
    """
    Write the generated XML data to a file.
    """
    with open(filename, "wb") as file:
        with io.BufferedWriter(file) as buffer:
            buffer.write(xml)


if __name__ == "__main__":
    # We will generate quite a bunch of files, so it is better to have them all in one subdir.
    if not os.path.isdir("exports"):
        os.makedirs("exports")

    print("Fetching exercises...", end="")
    exercises = fetch_exercise_list()
    print(f"done. Found {len(exercises)} exercises.")
    print("Preparing individual TCX files", end="")
    for exercise in exercises:
        print(".", end="", flush=True)
        if "start_time" not in exercise or not exercise["start_time"]:
            continue
        if (xml_data := prepare_exercise_data(exercise)) is not None:
            filename = f"exports/{exercise['datauuid']}.tcx"
            write_to_file(filename, xml_data)
            print(f"Exported exercise {exercise['datauuid']} to {filename}")
        else:
            print(f"Skipping exercise {exercise['datauuid']} due to missing data.")

    print("Export completed successfully.")
