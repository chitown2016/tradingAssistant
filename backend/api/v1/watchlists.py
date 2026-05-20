"""
Watchlist endpoints — server-side persistence for the chart sidebar.
"""
import logging
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
import psycopg2
from psycopg2 import errors as pg_errors
from backend.db import get_db

router = APIRouter()
logger = logging.getLogger(__name__)


# ----- Pydantic models -----

class Watchlist(BaseModel):
    id: int
    name: str
    position: int
    item_count: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class WatchlistCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)


class WatchlistRename(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)


class WatchlistItemCreate(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=20)


# ----- Helpers -----

def _fetch_watchlist(cursor, wid: int) -> Watchlist:
    cursor.execute(
        """
        SELECT w.id, w.name, w.position, w.created_at, w.updated_at,
               COALESCE(c.cnt, 0) AS item_count
        FROM watchlists w
        LEFT JOIN (
            SELECT watchlist_id, COUNT(*) AS cnt
            FROM watchlist_items
            GROUP BY watchlist_id
        ) c ON c.watchlist_id = w.id
        WHERE w.id = %s
        """,
        (wid,),
    )
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Watchlist {wid} not found")
    return Watchlist(
        id=row[0], name=row[1], position=row[2],
        created_at=row[3], updated_at=row[4], item_count=row[5],
    )


# ----- Watchlist routes -----

@router.get("", response_model=List[Watchlist])
async def list_watchlists(db: psycopg2.extensions.connection = Depends(get_db)):
    cursor = db.cursor()
    try:
        cursor.execute(
            """
            SELECT w.id, w.name, w.position, w.created_at, w.updated_at,
                   COALESCE(c.cnt, 0) AS item_count
            FROM watchlists w
            LEFT JOIN (
                SELECT watchlist_id, COUNT(*) AS cnt
                FROM watchlist_items
                GROUP BY watchlist_id
            ) c ON c.watchlist_id = w.id
            ORDER BY w.position, w.id
            """
        )
        return [
            Watchlist(
                id=r[0], name=r[1], position=r[2],
                created_at=r[3], updated_at=r[4], item_count=r[5],
            )
            for r in cursor.fetchall()
        ]
    finally:
        cursor.close()


@router.post("", response_model=Watchlist, status_code=201)
async def create_watchlist(
    payload: WatchlistCreate,
    db: psycopg2.extensions.connection = Depends(get_db),
):
    cursor = db.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO watchlists (name, position)
            VALUES (%s, COALESCE((SELECT MAX(position) + 1 FROM watchlists), 0))
            RETURNING id
            """,
            (payload.name.strip(),),
        )
        wid = cursor.fetchone()[0]
        return _fetch_watchlist(cursor, wid)
    except pg_errors.UniqueViolation:
        db.rollback()
        raise HTTPException(status_code=409, detail=f"Watchlist '{payload.name}' already exists")
    finally:
        cursor.close()


@router.patch("/{wid}", response_model=Watchlist)
async def rename_watchlist(
    wid: int,
    payload: WatchlistRename,
    db: psycopg2.extensions.connection = Depends(get_db),
):
    cursor = db.cursor()
    try:
        cursor.execute(
            "UPDATE watchlists SET name = %s, updated_at = NOW() WHERE id = %s",
            (payload.name.strip(), wid),
        )
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail=f"Watchlist {wid} not found")
        return _fetch_watchlist(cursor, wid)
    except pg_errors.UniqueViolation:
        db.rollback()
        raise HTTPException(status_code=409, detail=f"Watchlist '{payload.name}' already exists")
    finally:
        cursor.close()


@router.delete("/{wid}", status_code=204)
async def delete_watchlist(wid: int, db: psycopg2.extensions.connection = Depends(get_db)):
    cursor = db.cursor()
    try:
        cursor.execute("DELETE FROM watchlists WHERE id = %s", (wid,))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail=f"Watchlist {wid} not found")
        return Response(status_code=204)
    finally:
        cursor.close()


# ----- Watchlist-item routes -----

@router.get("/{wid}/items", response_model=List[str])
async def list_items(wid: int, db: psycopg2.extensions.connection = Depends(get_db)):
    cursor = db.cursor()
    try:
        cursor.execute("SELECT 1 FROM watchlists WHERE id = %s", (wid,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail=f"Watchlist {wid} not found")

        cursor.execute(
            "SELECT symbol FROM watchlist_items WHERE watchlist_id = %s ORDER BY position, added_at",
            (wid,),
        )
        return [r[0] for r in cursor.fetchall()]
    finally:
        cursor.close()


@router.post("/{wid}/items", status_code=201)
async def add_item(
    wid: int,
    payload: WatchlistItemCreate,
    db: psycopg2.extensions.connection = Depends(get_db),
):
    symbol = payload.symbol.upper().strip()
    cursor = db.cursor()
    try:
        cursor.execute("SELECT 1 FROM watchlists WHERE id = %s", (wid,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail=f"Watchlist {wid} not found")

        cursor.execute("SELECT 1 FROM tickers WHERE symbol = %s", (symbol,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail=f"Symbol '{symbol}' not found in tickers")

        try:
            cursor.execute(
                """
                INSERT INTO watchlist_items (watchlist_id, symbol, position)
                VALUES (
                    %s, %s,
                    COALESCE(
                        (SELECT MAX(position) + 1 FROM watchlist_items WHERE watchlist_id = %s),
                        0
                    )
                )
                """,
                (wid, symbol, wid),
            )
        except pg_errors.UniqueViolation:
            db.rollback()
            raise HTTPException(status_code=409, detail=f"'{symbol}' is already in this watchlist")

        cursor.execute(
            "UPDATE watchlists SET updated_at = NOW() WHERE id = %s", (wid,)
        )
        return {"watchlist_id": wid, "symbol": symbol}
    finally:
        cursor.close()


@router.delete("/{wid}/items/{symbol}", status_code=204)
async def remove_item(
    wid: int,
    symbol: str,
    db: psycopg2.extensions.connection = Depends(get_db),
):
    symbol = symbol.upper().strip()
    cursor = db.cursor()
    try:
        cursor.execute(
            "DELETE FROM watchlist_items WHERE watchlist_id = %s AND symbol = %s",
            (wid, symbol),
        )
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail=f"'{symbol}' not in watchlist {wid}")
        cursor.execute(
            "UPDATE watchlists SET updated_at = NOW() WHERE id = %s", (wid,)
        )
        return Response(status_code=204)
    finally:
        cursor.close()
