"""Tiny demo REST API used as the Test Lab's API-runner fixture (PRD §13.6).

A minimal "petty cash transfers" API (Bearer auth, a 50,000 limit, idempotent-by-reference
creates, owner-scoped reads) — enough surface for the PRD's listed API test categories: happy
path, missing/invalid fields, boundary values, auth missing/invalid, permission (IDOR),
idempotency, pagination, schema conformance, error format. FastAPI's own `/openapi.json` is
the spec this fixture serves for the "OpenAPI spec source: URL" runner input — this app IS the
live target too, so there's no separate mock process to keep in sync with a static spec file
(see docs/decisions/007 for why this replaces the PRD's suggested Prism-from-a-spec-file mock).
"""

import os
import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import FastAPI, Header, HTTPException, Query
from pydantic import BaseModel, Field

TRANSFER_LIMIT = float(os.environ.get("DEMO_API_TRANSFER_LIMIT", "50000"))
# token -> owner id. A real app would issue these; a fixed demo set keeps the fixture simple.
TOKENS = {"demo-token-a": "user-a", "demo-token-b": "user-b"}

app = FastAPI(title="QA Forge Demo API", version="1.0.0")

_transfers: dict[str, dict[str, object]] = {}
_by_reference: dict[str, str] = {}  # reference -> transfer id, for idempotency


class TransferIn(BaseModel):
    account_id: str = Field(min_length=1)
    amount: float = Field(gt=0)
    reference: str = Field(min_length=1)


class TransferOut(BaseModel):
    id: str
    account_id: str
    amount: float
    reference: str
    owner_id: str
    status: str
    created_at: str


def _authenticate(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing or malformed Authorization header")
    token = authorization.removeprefix("Bearer ")
    owner_id = TOKENS.get(token)
    if owner_id is None:
        raise HTTPException(401, "Invalid or expired token")
    return owner_id


@app.post("/transfers", response_model=TransferOut, status_code=201)
def create_transfer(
    payload: TransferIn, authorization: Annotated[str | None, Header()] = None
) -> dict[str, object]:
    owner_id = _authenticate(authorization)

    existing_id = _by_reference.get(payload.reference)
    if existing_id is not None:
        return _transfers[existing_id]  # idempotent replay, not a new transfer

    if payload.amount > TRANSFER_LIMIT:
        raise HTTPException(400, f"amount exceeds the transfer limit of {TRANSFER_LIMIT}")

    transfer_id = str(uuid.uuid4())
    record: dict[str, object] = {
        "id": transfer_id,
        "account_id": payload.account_id,
        "amount": payload.amount,
        "reference": payload.reference,
        "owner_id": owner_id,
        "status": "completed",
        "created_at": datetime.now(UTC).isoformat(),
    }
    _transfers[transfer_id] = record
    _by_reference[payload.reference] = transfer_id
    return record


@app.get("/transfers/{transfer_id}", response_model=TransferOut)
def get_transfer(
    transfer_id: str, authorization: Annotated[str | None, Header()] = None
) -> dict[str, object]:
    owner_id = _authenticate(authorization)
    record = _transfers.get(transfer_id)
    if record is None:
        raise HTTPException(404, "Transfer not found")
    if record["owner_id"] != owner_id:
        raise HTTPException(403, "You don't have access to this transfer")
    return record


@app.get("/transfers", response_model=list[TransferOut])
def list_transfers(
    authorization: Annotated[str | None, Header()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[dict[str, object]]:
    owner_id = _authenticate(authorization)
    mine = [r for r in _transfers.values() if r["owner_id"] == owner_id]
    mine.sort(key=lambda r: str(r["created_at"]))
    return mine[offset : offset + limit]


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("PORT", "8991")))
