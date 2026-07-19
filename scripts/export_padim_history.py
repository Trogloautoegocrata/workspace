#!/usr/bin/env python3
"""
PADIM History Export — Genera el dump público semanal de snapshots.
Se ejecuta cada domingo vía cron.
Output: /home/polaris/workspace/data/padim-history.parquet
Schema: PADIM spec/schema-history.json
"""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

DB_NAME = "backbone"
DB_USER = "backbone"
OUTPUT_DIR = Path("/home/polaris/workspace/data")


def export_snapshots():
    """Exporta todos los snapshots a JSONL."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    jsonl_path = OUTPUT_DIR / "padim-history.jsonl"

    sql = """
    COPY (
        SELECT json_build_object(
            'property_id', ps.property_id::text,
            'scraped_at', ps.scraped_at::text,
            'content_hash', ps.content_hash,
            'price', ps.price::text,
            'price_m2', ps.price_m2::text,
            'status', COALESCE(ps.status, 'unknown'),
            'm2_constructed', ps.m2_constructed::text,
            'm2_land', ps.m2_land::text,
            'bedrooms', ps.bedrooms,
            'bathrooms', ps.bathrooms::text,
            'source_url', ps.source_url,
            'is_deleted', ps.is_deleted,
            'source', p.source,
            'colony', p.colony,
            'municipality', p.municipality,
            'state', p.state,
            'property_type', p.property_type,
            'business_type', p.business_type
        )::text
        FROM property_snapshots ps
        JOIN properties p ON p.id = ps.property_id
        ORDER BY ps.scraped_at DESC
    ) TO '/tmp/padim-snapshots-export.jsonl';
    """

    print("1. Exporting from PostgreSQL...")
    cmds = [
        "docker exec -i backbone-postgres psql -U {} -d {} <<'EOSQL'\n{}\nEOSQL".format(DB_USER, DB_NAME, sql),
        "docker cp backbone-postgres:/tmp/padim-snapshots-export.jsonl {}".format(jsonl_path),
        "docker exec backbone-postgres rm -f /tmp/padim-snapshots-export.jsonl",
    ]

    for cmd in cmds:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=120)
        if r.returncode != 0 and "COPY" not in cmd:
            print(f"  WARN: {r.stderr[:200]}")

    # Count lines
    count = 0
    with open(jsonl_path) as f:
        for _ in f:
            count += 1

    size_mb = jsonl_path.stat().st_size / (1024 * 1024)
    print(f"  → {count} snapshots ({size_mb:.1f} MB)")
    return count > 0


def convert_to_parquet():
    """Convierte JSONL a Parquet."""
    jsonl_path = OUTPUT_DIR / "padim-history.jsonl"
    parquet_path = OUTPUT_DIR / "padim-history.parquet"

    try:
        import pyarrow.json as paj
        import pyarrow.parquet as pq
        table = paj.read_json(str(jsonl_path))
        pq.write_table(table, str(parquet_path), compression='snappy')
        size_mb = parquet_path.stat().st_size / (1024 * 1024)
        print(f"2. Parquet: {parquet_path} ({size_mb:.1f} MB)")
        return True
    except ImportError:
        print("2. pyarrow not installed. JSONL available at:", jsonl_path)
        return False


if __name__ == "__main__":
    print("── PADIM History Export ──")
    print("Date:", datetime.utcnow().isoformat())
    if export_snapshots():
        convert_to_parquet()
    print("── Done ──")
