#!/usr/bin/env python3
"""Exercise the task 5 Postman flow against running Compose services."""

import argparse
from datetime import datetime
import json
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen
import uuid


ROOT = Path(__file__).resolve().parents[1]


def request(base, path, method="GET", body=None, expected=200):
    data = json.dumps(body, ensure_ascii=False).encode() if body is not None else None
    headers = {"Content-Type": "application/json"} if data is not None else {}
    req = Request(base.rstrip("/") + path, data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=15) as response:
            assert response.status == expected, (path, response.status)
            return json.load(response)
    except HTTPError as error:
        raise AssertionError(f"{method} {path}: HTTP {error.code}: {error.read().decode()}") from error


def validate_sensor(sensor):
    assert sensor["type"] == "temperature", sensor
    assert sensor["status"] == "active", sensor
    assert 15 <= sensor["value"] <= 30, sensor
    datetime.fromisoformat(sensor["last_updated"].replace("Z", "+00:00"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--temperature-url", default="http://127.0.0.1:8081")
    args = parser.parse_args()

    collection = json.loads((ROOT / "apps/smarthome-api.postman_collection.json").read_text())
    items = {item["name"]: item["request"] for item in collection["item"]}
    create = items["Create Sensor"]
    read_all = items["Get All Sensors"]
    create_path = urlsplit(create["url"]["raw"]).path
    list_path = urlsplit(read_all["url"]["raw"]).path

    assert request(args.base_url, "/health")["status"] == "ok"
    assert request(args.temperature_url, "/health")["status"] == "ok"
    for path, sensor_id, location in [
        ("/temperature?location=Living%20Room", "1", "Living Room"),
        ("/temperature?location=Bedroom", "2", "Bedroom"),
        ("/temperature?location=Kitchen", "3", "Kitchen"),
        ("/temperature/42", "42", "Unknown"),
        ("/temperature", "0", "Unknown"),
    ]:
        reading = request(args.temperature_url, path)
        assert reading["sensor_id"] == sensor_id and reading["location"] == location, reading
        assert reading["unit"] == "°C" and reading["sensor_type"] == "temperature", reading
        assert 15 <= reading["value"] <= 30 and reading["status"] == "active", reading
        datetime.fromisoformat(reading["timestamp"].replace("Z", "+00:00"))

    locations = ["Living Room", "Bedroom", "Kitchen", "Office"]
    owned = {}
    previous = {}
    try:
        for index, location in enumerate(locations):
            body = json.loads(create["body"]["raw"])
            body.update(name=f"smoke_{uuid.uuid4().hex}_{index}", location=location)
            sensor = request(args.base_url, create_path, method=create["method"], body=body, expected=201)
            assert isinstance(sensor["id"], int) and sensor["name"] == body["name"], sensor
            owned[sensor["id"]] = body
            assert sensor["type"] == body["type"] and sensor["location"] == body["location"], sensor
        for round_number in range(1, 4):
            sensors = request(args.base_url, list_path, method=read_all["method"])
            actual = {sensor["id"]: sensor for sensor in sensors}
            values = {}
            for sensor_id, body in owned.items():
                sensor = actual[sensor_id]
                validate_sensor(sensor)
                assert sensor["name"] == body["name"] and sensor["location"] == body["location"], sensor
                if sensor_id in previous:
                    assert sensor["value"] != previous[sensor_id], (sensor_id, sensor["value"])
                previous[sensor_id] = sensor["value"]
                values[sensor_id] = sensor["value"]
            print(f"Get All Sensors, round {round_number}: {values}", flush=True)
        for sensor_id in owned:
            sensor = request(args.base_url, list_path + "/" + str(sensor_id))
            validate_sensor(sensor)
            assert sensor["value"] != previous[sensor_id], sensor
        room = "Спальня & кабинет #1"
        reading = request(args.temperature_url, "/temperature?location=" + quote(room, safe=""))
        assert reading["location"] == room and 15 <= reading["value"] <= 30, reading
        print("OK: Postman Create Sensor → repeated Get All Sensors, IDs beyond 3, single sensor and direct Temperature API with encoded location.")
    finally:
        for sensor_id, body in owned.items():
            sensor = request(args.base_url, list_path + "/" + str(sensor_id))
            if sensor["name"] != body["name"]:
                raise RuntimeError("Refusing to remove a sensor that does not match this test's fixture.")
            request(args.base_url, list_path + "/" + str(sensor_id), method="DELETE")


if __name__ == "__main__":
    main()
