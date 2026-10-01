"""Spec parsing (PRD §7.6.2, §10 `POST /api-specs/parse`): OpenAPI (JSON/YAML), Postman
collection v2.1, or pasted cURL commands -> a normalized `EndpointCatalogue`.

Deliberately lightweight: local `$ref` resolution only (`#/components/schemas/...`), no
external-ref fetching, no full JSON Schema draft validation of the spec itself — good enough
for specs an admin/user supplies for their own API (including `infra/demo-api`'s own
auto-generated `/openapi.json`), not a general-purpose OpenAPI toolchain.
"""

import re
import shlex
from urllib.parse import urlparse

import yaml

from app.services.execution.api_models import EndpointCatalogue, EndpointInfo, EndpointParam


class SpecParseError(Exception):
    pass


def _resolve_ref(schema: dict[str, object], components: dict[str, object]) -> dict[str, object]:
    ref = schema.get("$ref")
    if not isinstance(ref, str):
        return schema
    if not ref.startswith("#/components/schemas/"):
        return schema  # external/unsupported ref — leave as-is
    name = ref.rsplit("/", 1)[-1]
    schemas = components.get("schemas", {})
    resolved = schemas.get(name) if isinstance(schemas, dict) else None
    return resolved if isinstance(resolved, dict) else schema


def parse_openapi(content: str) -> EndpointCatalogue:
    try:
        spec = yaml.safe_load(content)  # YAML is a JSON superset, so this parses JSON too
    except yaml.YAMLError as exc:
        raise SpecParseError(f"Could not parse OpenAPI spec: {exc}") from exc
    if not isinstance(spec, dict) or "paths" not in spec:
        raise SpecParseError("Not a recognizable OpenAPI document (no top-level 'paths')")

    components = spec.get("components", {}) if isinstance(spec.get("components"), dict) else {}
    base_url = None
    servers = spec.get("servers")
    if isinstance(servers, list) and servers and isinstance(servers[0], dict):
        base_url = servers[0].get("url")

    endpoints: list[EndpointInfo] = []
    paths = spec.get("paths", {})
    if not isinstance(paths, dict):
        raise SpecParseError("'paths' must be an object")
    for path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        for method in ("get", "post", "put", "patch", "delete"):
            operation = path_item.get(method)
            if not isinstance(operation, dict):
                continue
            params = []
            for p in operation.get("parameters", []) or []:
                if not isinstance(p, dict):
                    continue
                params.append(
                    EndpointParam(
                        name=str(p.get("name", "")),
                        location=p.get("in", "query"),
                        required=bool(p.get("required", False)),
                        schema_type=str((p.get("schema") or {}).get("type", "string")),
                    )
                )
            body_schema = None
            request_body = operation.get("requestBody")
            if isinstance(request_body, dict):
                json_content = (request_body.get("content") or {}).get("application/json")
                if isinstance(json_content, dict) and isinstance(json_content.get("schema"), dict):
                    body_schema = _resolve_ref(json_content["schema"], components)
            response_schemas: dict[str, dict[str, object]] = {}
            for status_code, response in (operation.get("responses") or {}).items():
                if not isinstance(response, dict):
                    continue
                json_content = (response.get("content") or {}).get("application/json")
                if isinstance(json_content, dict) and isinstance(json_content.get("schema"), dict):
                    response_schemas[str(status_code)] = _resolve_ref(
                        json_content["schema"], components
                    )
            endpoints.append(
                EndpointInfo(
                    method=method.upper(),
                    path=path,
                    summary=str(operation.get("summary", "")),
                    parameters=params,
                    request_body_schema=body_schema,
                    response_schemas=response_schemas,
                )
            )
    return EndpointCatalogue(base_url=base_url, endpoints=endpoints)


def parse_postman(content: str) -> EndpointCatalogue:
    import json

    try:
        collection = json.loads(content)
    except json.JSONDecodeError as exc:
        raise SpecParseError(f"Could not parse Postman collection: {exc}") from exc

    endpoints: list[EndpointInfo] = []
    base_url: str | None = None

    def walk(items: list[object]) -> None:
        nonlocal base_url
        for item in items:
            if not isinstance(item, dict):
                continue
            if isinstance(item.get("item"), list):  # a folder
                walk(item["item"])
                continue
            request = item.get("request")
            if not isinstance(request, dict):
                continue
            method = str(request.get("method", "GET")).upper()
            url = request.get("url")
            raw_url = url.get("raw", "") if isinstance(url, dict) else str(url or "")
            parsed = urlparse(raw_url)
            if base_url is None and parsed.scheme and parsed.netloc:
                base_url = f"{parsed.scheme}://{parsed.netloc}"
            path = parsed.path or "/"
            # `url` is only sometimes an object with a `query` list (Postman also allows a
            # plain string URL) — guard before calling `.get` on it, or a string-URL request
            # crashes the whole parse instead of just skipping that request's query params.
            params = (
                [
                    EndpointParam(name=q.get("key", ""), location="query")
                    for q in (url.get("query") or [])
                    if isinstance(q, dict) and q.get("key")
                ]
                if isinstance(url, dict)
                else []
            )
            body_schema = None
            body = request.get("body")
            if isinstance(body, dict) and body.get("mode") == "raw":
                try:
                    parsed_body = json.loads(body.get("raw", ""))
                    if isinstance(parsed_body, dict):
                        body_schema = {
                            "type": "object",
                            "properties": {k: {} for k in parsed_body},
                        }
                except (json.JSONDecodeError, TypeError):
                    pass
            endpoints.append(
                EndpointInfo(
                    method=method,
                    path=path,
                    summary=str(item.get("name", "")),
                    parameters=params,
                    request_body_schema=body_schema,
                )
            )

    walk(collection.get("item", []) if isinstance(collection, dict) else [])
    if not endpoints:
        raise SpecParseError("No requests found in this Postman collection")
    return EndpointCatalogue(base_url=base_url, endpoints=endpoints)


_CURL_METHOD_RE = re.compile(r"-X\s*|--request\s*")
_CURL_HEADER_FLAGS = {"-H", "--header"}
_CURL_DATA_FLAGS = {"-d", "--data", "--data-raw", "--data-binary"}
_CURL_METHOD_FLAGS = {"-X", "--request"}


def parse_curl(commands: list[str]) -> EndpointCatalogue:
    import json

    endpoints: list[EndpointInfo] = []
    base_url: str | None = None

    for raw in commands:
        raw = raw.strip()
        if not raw:
            continue
        if raw.startswith("curl "):
            raw = raw[len("curl ") :]
        try:
            tokens = shlex.split(raw)
        except ValueError as exc:
            raise SpecParseError(f"Could not parse cURL command: {exc}") from exc

        method = None
        url = None
        body_schema = None
        i = 0
        while i < len(tokens):
            tok = tokens[i]
            if tok in _CURL_METHOD_FLAGS and i + 1 < len(tokens):
                method = tokens[i + 1].upper()
                i += 2
            elif tok in _CURL_HEADER_FLAGS and i + 1 < len(tokens):
                i += 2  # headers become part of the generated request plan later, not parsed here
            elif tok in _CURL_DATA_FLAGS and i + 1 < len(tokens):
                if method is None:
                    method = "POST"
                try:
                    parsed_body = json.loads(tokens[i + 1])
                    if isinstance(parsed_body, dict):
                        body_schema = {"type": "object", "properties": {k: {} for k in parsed_body}}
                except (json.JSONDecodeError, TypeError):
                    pass
                i += 2
            elif tok.startswith("-"):
                i += 1  # skip unrecognized flags (e.g. -s, -k, --compressed)
            else:
                if url is None:
                    url = tok
                i += 1

        if url is None:
            raise SpecParseError(f"Could not find a URL in: {raw!r}")
        parsed = urlparse(url)
        if parsed.scheme and parsed.netloc:
            base_url = base_url or f"{parsed.scheme}://{parsed.netloc}"
        endpoints.append(
            EndpointInfo(
                method=method or "GET",
                path=parsed.path or "/",
                request_body_schema=body_schema,
            )
        )

    return EndpointCatalogue(base_url=base_url, endpoints=endpoints)
