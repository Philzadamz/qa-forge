import json

import pytest

from app.services.execution.api_spec import SpecParseError, parse_curl, parse_openapi, parse_postman

OPENAPI_YAML = """
openapi: 3.0.0
info:
  title: Demo API
  version: "1.0"
servers:
  - url: http://127.0.0.1:8991
components:
  schemas:
    TransferIn:
      type: object
      properties:
        account_id: {type: string}
        amount: {type: number}
        reference: {type: string}
      required: [account_id, amount, reference]
paths:
  /transfers:
    post:
      summary: Create a transfer
      requestBody:
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/TransferIn'
      responses:
        '201':
          content:
            application/json:
              schema:
                type: object
                properties:
                  id: {type: string}
    get:
      summary: List transfers
      parameters:
        - name: limit
          in: query
          required: false
          schema: {type: integer}
  /transfers/{id}:
    get:
      summary: Get a transfer
      parameters:
        - name: id
          in: path
          required: true
          schema: {type: string}
"""


def test_parse_openapi_extracts_endpoints_and_base_url() -> None:
    catalogue = parse_openapi(OPENAPI_YAML)
    assert catalogue.base_url == "http://127.0.0.1:8991"
    methods_paths = {(e.method, e.path) for e in catalogue.endpoints}
    assert methods_paths == {
        ("POST", "/transfers"),
        ("GET", "/transfers"),
        ("GET", "/transfers/{id}"),
    }


def test_parse_openapi_resolves_local_refs_in_request_body() -> None:
    catalogue = parse_openapi(OPENAPI_YAML)
    post_transfer = next(e for e in catalogue.endpoints if e.method == "POST")
    assert post_transfer.request_body_schema is not None
    assert "account_id" in post_transfer.request_body_schema["properties"]


def test_parse_openapi_captures_path_and_query_parameters() -> None:
    catalogue = parse_openapi(OPENAPI_YAML)
    get_by_id = next(e for e in catalogue.endpoints if e.path == "/transfers/{id}")
    assert get_by_id.parameters[0].name == "id"
    assert get_by_id.parameters[0].location == "path"
    assert get_by_id.parameters[0].required is True

    list_transfers = next(
        e for e in catalogue.endpoints if e.method == "GET" and e.path == "/transfers"
    )
    assert list_transfers.parameters[0].name == "limit"
    assert list_transfers.parameters[0].required is False


def test_parse_openapi_rejects_non_openapi_json() -> None:
    with pytest.raises(SpecParseError):
        parse_openapi(json.dumps({"hello": "world"}))


def test_parse_openapi_accepts_json_too() -> None:
    spec_json = json.dumps(
        {
            "openapi": "3.0.0",
            "paths": {"/ping": {"get": {"summary": "Ping"}}},
        }
    )
    catalogue = parse_openapi(spec_json)
    assert len(catalogue.endpoints) == 1
    assert catalogue.endpoints[0].path == "/ping"


POSTMAN_COLLECTION = {
    "info": {"name": "Demo"},
    "item": [
        {
            "name": "Create transfer",
            "request": {
                "method": "POST",
                "url": {
                    "raw": "http://127.0.0.1:8991/transfers?debug=1",
                    "query": [{"key": "debug", "value": "1"}],
                },
                "body": {"mode": "raw", "raw": '{"account_id": "a1", "amount": 100}'},
            },
        },
        {
            "name": "Folder",
            "item": [
                {
                    "name": "Get transfer",
                    "request": {"method": "GET", "url": "http://127.0.0.1:8991/transfers/1"},
                }
            ],
        },
    ],
}


def test_parse_postman_flattens_folders_and_extracts_base_url() -> None:
    catalogue = parse_postman(json.dumps(POSTMAN_COLLECTION))
    assert catalogue.base_url == "http://127.0.0.1:8991"
    paths = {(e.method, e.path) for e in catalogue.endpoints}
    assert paths == {("POST", "/transfers"), ("GET", "/transfers/1")}


def test_parse_postman_extracts_query_params_and_body_schema() -> None:
    catalogue = parse_postman(json.dumps(POSTMAN_COLLECTION))
    create = next(e for e in catalogue.endpoints if e.method == "POST")
    assert create.parameters[0].name == "debug"
    assert create.request_body_schema is not None
    assert "account_id" in create.request_body_schema["properties"]


def test_parse_postman_handles_string_url_without_crashing() -> None:
    collection = {"item": [{"name": "x", "request": {"method": "GET", "url": "http://x/ping"}}]}
    catalogue = parse_postman(json.dumps(collection))
    assert catalogue.endpoints[0].path == "/ping"
    assert catalogue.endpoints[0].parameters == []


def test_parse_postman_rejects_empty_collection() -> None:
    with pytest.raises(SpecParseError):
        parse_postman(json.dumps({"item": []}))


def test_parse_curl_single_command() -> None:
    cmd = (
        'curl -X POST http://127.0.0.1:8991/transfers -H "Authorization: Bearer x" -d \'{"a": 1}\''
    )
    catalogue = parse_curl([cmd])
    assert catalogue.base_url == "http://127.0.0.1:8991"
    assert catalogue.endpoints[0].method == "POST"
    assert catalogue.endpoints[0].path == "/transfers"
    assert catalogue.endpoints[0].request_body_schema is not None


def test_parse_curl_defaults_to_get_without_data() -> None:
    catalogue = parse_curl(["curl http://127.0.0.1:8991/transfers/1"])
    assert catalogue.endpoints[0].method == "GET"


def test_parse_curl_multiple_commands() -> None:
    catalogue = parse_curl(
        [
            "curl http://127.0.0.1:8991/transfers",
            "curl -X DELETE http://127.0.0.1:8991/transfers/1",
        ]
    )
    assert len(catalogue.endpoints) == 2


def test_parse_curl_raises_without_a_url() -> None:
    with pytest.raises(SpecParseError):
        parse_curl(["curl -X GET"])
