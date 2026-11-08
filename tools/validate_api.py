#!/usr/bin/env python3
"""Validate the API specifications, examples and selected contract invariants."""

from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path
import sys

try:
    from jsonschema import Draft7Validator, Draft202012Validator, FormatChecker
    from jsonschema.exceptions import ValidationError
    from openapi_spec_validator import validate_spec
    from referencing import Registry, Resource
    from referencing.jsonschema import DRAFT7, DRAFT202012
except ImportError as error:
    raise SystemExit("Установите tools/requirements-api.txt в отдельное Python-окружение.") from error


ROOT = Path(__file__).resolve().parents[1]
FORMATS = FormatChecker()


def pointer(document, reference):
    if not reference.startswith("#/"):
        raise ValueError(f"Контракт должен быть самостоятельным; внешний $ref: {reference}")
    value = document
    for part in reference[2:].split("/"):
        value = value[part.replace("~1", "/").replace("~0", "~")]
    return value


def walk(value):
    yield value
    if isinstance(value, dict):
        for item in value.values():
            yield from walk(item)
    elif isinstance(value, list):
        for item in value:
            yield from walk(item)


def checker(document, draft, dialect, uri):
    resource = Resource.from_contents(document, default_specification=dialect)
    registry = Registry().with_resource(uri, resource)

    def absolute(node):
        if isinstance(node, dict):
            return {
                key: (uri + item if key == "$ref" and item.startswith("#/") else absolute(item))
                for key, item in node.items()
            }
        if isinstance(node, list):
            return [absolute(item) for item in node]
        return node

    def check(schema, value):
        # Resolve component refs against the whole specification, not the example fragment.
        draft(absolute(schema), registry=registry, format_checker=FORMATS).validate(value)

    return check


def validate_examples(document, check):
    count = 0
    for node in walk(document):
        if not isinstance(node, dict):
            continue
        if "$ref" in node:
            pointer(document, node["$ref"])
        if "schema" in node:
            for item in node.get("examples", {}).values():
                check(node["schema"], item["value"])
                count += 1
            if "example" in node:
                check(node["schema"], node["example"])
                count += 1
    return count


def timestamp(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def main():
    openapi = json.loads((ROOT / "docs/api/openapi.json").read_text())
    asyncapi = json.loads((ROOT / "docs/api/asyncapi.json").read_text())
    validate_spec(openapi)
    operations = [operation for path in openapi["paths"].values()
                  for method, operation in path.items()
                  if method in {"get", "post", "put", "patch", "delete"}]
    assert len(operations) == 5, "Требуются пять документированных HTTP-операций."
    assert len({operation["operationId"] for operation in operations}) == 5

    meta = json.loads((ROOT / "tools/schemas/asyncapi-3.0.0.json").read_text())
    registry = Registry().with_resource(meta["$id"], Resource.from_contents(meta)).crawl()
    Draft7Validator(meta, registry=registry, format_checker=FORMATS).validate(asyncapi)
    assert len(asyncapi["operations"]) == 3
    for operation in asyncapi["operations"].values():
        channel_reference = operation["channel"]["$ref"]
        channel = pointer(asyncapi, channel_reference)
        for message in operation["messages"]:
            assert message["$ref"].startswith(channel_reference + "/messages/")
            assert message["$ref"].rsplit("/", 1)[-1] in channel["messages"]

    rest_check = checker(openapi, Draft202012Validator, DRAFT202012, "urn:warmhouse:openapi")
    event_check = checker(asyncapi, Draft7Validator, DRAFT7, "urn:warmhouse:asyncapi")
    examples = validate_examples(openapi, rest_check) + validate_examples(asyncapi, event_check)
    for message in asyncapi["components"]["messages"].values():
        for item in message["examples"]:
            payload = item["payload"]
            event_check(message["payload"], payload)
            examples += 1
            if payload["eventType"] == "CommandRequested.v1":
                assert payload["correlationId"] == payload["commandId"]
                assert payload["data"]["action"].split(".")[0] == payload["origin"]
                assert timestamp(payload["expiresAt"]) > timestamp(payload["occurredAt"])
            if payload["eventType"] == "TelemetryReceived.v1":
                for key in ("houseId", "deviceId", "bindingVersion"):
                    assert payload[key] == payload["data"][key]

    common = openapi["components"]["schemas"].keys() & asyncapi["components"]["schemas"].keys()
    for name in common:
        assert openapi["components"]["schemas"][name] == asyncapi["components"]["schemas"][name], name

    paths = openapi["paths"]
    command_post = paths["/houses/{houseId}/{domain}/devices/{deviceId}/commands"]["post"]
    requests = command_post["requestBody"]["content"]["application/json"]["examples"]
    for item in requests.values():
        domain = item["x-path-parameters"]["domain"]
        assert item["value"]["action"] in command_post["x-domain-actions"][domain]
    telemetry_examples = paths["/houses/{houseId}/devices/{deviceId}/telemetry"]["get"]["responses"]["200"]["content"]["application/json"]["examples"]
    for item in telemetry_examples.values():
        page = item["value"]
        for measurement in page["items"]:
            for key in ("houseId", "deviceId", "bindingVersion", "metric"):
                assert measurement[key] == page[key]
            age = max(0, int((timestamp(page["asOf"]) - timestamp(measurement["observedAt"])).total_seconds()))
            assert age == measurement["ageSeconds"]
            assert measurement["stale"] == (age > page["freshnessThresholdSeconds"])

    command_examples = command_post["responses"]["200"]["content"]["application/json"]["examples"]
    accepted = deepcopy(command_examples["replayAccepted"]["value"])
    succeeded = deepcopy(command_examples["replaySucceeded"]["value"])
    claim = paths["/houses/{houseId}/device-claims"]["post"]["requestBody"]["content"]["application/json"]["examples"]["connectHeatingKit"]["value"]
    bad_claim = deepcopy(claim); del bad_claim["claimCode"]
    spoofed = {**claim, "ownerSub": "someone-else"}
    bad_enabled = deepcopy(requests["enableHeating"]["value"]); bad_enabled["payload"]["enabled"] = "true"
    bad_accepted = deepcopy(accepted); bad_accepted["result"] = succeeded["result"]
    bad_success = deepcopy(succeeded); bad_success["result"] = None
    bad_unknown = deepcopy(accepted); bad_unknown.update(status="UNKNOWN", result=succeeded["result"], failure={"code":"ACK_TIMEOUT","message":"No ACK"})
    bad_event = deepcopy(asyncapi["components"]["messages"]["CommandRequested"]["examples"][0]["payload"]); bad_event["origin"] = "gates"
    bad_measurement = deepcopy(asyncapi["components"]["messages"]["TelemetryReceived"]["examples"][0]["payload"]); bad_measurement["bindingVersion"] = 0
    bad_latest = deepcopy(telemetry_examples["latest"]["value"]); bad_latest["items"] *= 2
    rejected = 0
    for check, name, value in [
        (rest_check, "ClaimRequest", bad_claim), (rest_check, "ClaimRequest", spoofed),
        (rest_check, "CommandRequest", bad_enabled), (rest_check, "CommandResource", bad_accepted),
        (rest_check, "CommandResource", bad_success), (rest_check, "CommandResource", bad_unknown),
        (event_check, "CommandRequestedEvent", bad_event), (event_check, "TelemetryReceivedEvent", bad_measurement),
        (rest_check, "TelemetryPage", bad_latest),
    ]:
        try:
            check({"$ref": "#/components/schemas/" + name}, value)
        except ValidationError:
            rejected += 1
        else:
            raise ValueError(f"Невалидный пример неожиданно принят: {name}")
    rest_check({"$ref":"#/components/schemas/CommandRequest"}, requests["disableHeating"]["value"])

    print("OpenAPI 3.1: 5 операций — OK")
    print("AsyncAPI 3.0: 3 канала/операции, официальная метасхема — OK")
    print(f"Примеры: {examples}; отклонены негативные случаи: {rejected}; общих схем согласовано: {len(common)}")


if __name__ == "__main__":
    main()
