"""Internal Server A API for hydrating Pinecone hits from MongoDB."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from mongo_store import database, ensure_indexes


class BatchRequest(BaseModel):
    unit_ids: list[str] = Field(min_length=1, max_length=100)


@asynccontextmanager
async def lifespan(app: FastAPI):
    client, db = database()
    ensure_indexes(db)
    app.state.mongo_client = client
    app.state.mongo_db = db
    yield
    client.close()


app = FastAPI(title="GrantPilot Server A Legal Units API", lifespan=lifespan)


def serialize(row: dict) -> dict:
    row.pop("_id", None)
    return row


@app.post("/internal/legal-units/batch")
def batch_units(payload: BatchRequest):
    rows = list(app.state.mongo_db.legal_units.find({"unit_id": {"$in": payload.unit_ids}, "is_current": True}, {"_id": 0}))
    by_id = {row["unit_id"]: row for row in rows}
    return {
        "items": [by_id[unit_id] for unit_id in payload.unit_ids if unit_id in by_id],
        "missing_unit_ids": [unit_id for unit_id in payload.unit_ids if unit_id not in by_id],
    }


@app.get("/internal/legal-units/exact")
def exact_unit(
    document_number: str,
    article: str,
    clause: str = "",
    point: str = "",
):
    query = {
        "document_number": document_number,
        "article": article,
        "clause": clause,
        "point": point,
        "is_current": True,
    }
    rows = list(app.state.mongo_db.legal_units.find(query, {"_id": 0}).limit(100))
    return {"items": rows}


@app.get("/health")
def health():
    app.state.mongo_db.command("ping")
    return {"status": "ok", "database": os.getenv("MONGODB_DB") or os.getenv("MONGO_DB", "grantpilot")}
