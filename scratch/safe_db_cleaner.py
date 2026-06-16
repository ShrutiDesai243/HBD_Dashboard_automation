import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv
from sqlalchemy import create_engine, text


ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
REPORT_DIR = ROOT / "scratch" / "reports"


TEXT_TYPES = {
    "char",
    "varchar",
    "tinytext",
    "text",
    "mediumtext",
    "longtext",
}

BACKUP_PREFIXES = (
    "safe_clean_backup_",
    "safe_clean_changed_",
)

TABLE_COLUMN_EXCLUDES = {
    # Trimming these two can collide with magicpin.unique_name_address.
    "magicpin": {"name", "address"},
}


def quote_ident(name):
    return f"`{str(name).replace('`', '``')}`"


def load_engine():
    load_dotenv(BACKEND_DIR / ".env")
    user = os.getenv("DB_USER")
    password = quote_plus(os.getenv("DB_PASSWORD") or "")
    host = os.getenv("DB_HOST")
    port = os.getenv("DB_PORT", "3306")
    database = os.getenv("DB_NAME")

    missing = [k for k, v in {
        "DB_USER": user,
        "DB_HOST": host,
        "DB_NAME": database,
    }.items() if not v]
    if missing:
        raise RuntimeError(f"Missing database settings in backend/.env: {', '.join(missing)}")

    url = f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}?charset=utf8mb4"
    return create_engine(
        url,
        pool_pre_ping=True,
        pool_recycle=120,
        isolation_level="AUTOCOMMIT",
        connect_args={"read_timeout": 600, "write_timeout": 600},
    ), database


def get_tables(conn, database):
    rows = conn.execute(
        text("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = :db
              AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """),
        {"db": database},
    ).fetchall()
    return [r[0] for r in rows]


def get_columns(conn, database, table_name):
    rows = conn.execute(
        text("""
            SELECT column_name, data_type, column_type, is_nullable, extra, generation_expression
            FROM information_schema.columns
            WHERE table_schema = :db
              AND table_name = :table
            ORDER BY ordinal_position
        """),
        {"db": database, "table": table_name},
    ).fetchall()
    return [
        {
            "name": r[0],
            "data_type": str(r[1]).lower(),
            "column_type": r[2],
            "is_nullable": r[3],
            "extra": str(r[4] or "").lower(),
            "generation_expression": r[5],
            "is_generated": bool(r[5]) or "generated" in str(r[4] or "").lower(),
        }
        for r in rows
    ]


def get_integer_primary_key(conn, database, table_name):
    row = conn.execute(
        text("""
            SELECT c.column_name, c.data_type
            FROM information_schema.key_column_usage k
            INNER JOIN information_schema.columns c
                ON c.table_schema = k.table_schema
               AND c.table_name = k.table_name
               AND c.column_name = k.column_name
            WHERE k.table_schema = :db
              AND k.table_name = :table
              AND k.constraint_name = 'PRIMARY'
            ORDER BY k.ordinal_position
            LIMIT 1
        """),
        {"db": database, "table": table_name},
    ).fetchone()
    if not row:
        return None
    return row[0] if str(row[1]).lower() in {"tinyint", "smallint", "mediumint", "int", "bigint"} else None


def get_primary_key_columns(conn, database, table_name):
    rows = conn.execute(
        text("""
            SELECT column_name
            FROM information_schema.key_column_usage
            WHERE table_schema = :db
              AND table_name = :table
              AND constraint_name = 'PRIMARY'
            ORDER BY ordinal_position
        """),
        {"db": database, "table": table_name},
    ).fetchall()
    return {r[0] for r in rows}


def count_rows(conn, table_name):
    return int(conn.execute(text(f"SELECT COUNT(*) FROM {quote_ident(table_name)}")).scalar() or 0)


def is_backup_table(table_name):
    lower = table_name.lower()
    return lower.startswith(BACKUP_PREFIXES) or "_backup_" in lower or lower.endswith("_backup")


def dirty_condition(columns):
    parts = []
    for col in columns:
        column_q = quote_ident(col["name"])
        parts.append(f"({column_q} IS NOT NULL AND {column_q} <> TRIM({column_q}))")
    return " OR ".join(parts) if parts else "1 = 0"


def trimmed_assignments(columns):
    return ", ".join(f"{quote_ident(col['name'])} = TRIM({quote_ident(col['name'])})" for col in columns)


def real_column_list(columns):
    names = [quote_ident(col["name"]) for col in columns if not col.get("is_generated")]
    return ", ".join(names)


def changed_backup_name(table_name, timestamp):
    prefix = f"safe_clean_changed_{timestamp}_"
    max_table_len = 64 - len(prefix)
    return f"{prefix}{table_name[:max_table_len]}"


def audit_text_column(conn, table_name, column_name):
    table_q = quote_ident(table_name)
    column_q = quote_ident(column_name)
    return conn.execute(
        text(f"""
            SELECT
                SUM(CASE WHEN {column_q} IS NOT NULL AND {column_q} <> TRIM({column_q}) THEN 1 ELSE 0 END) AS edge_space_rows,
                SUM(CASE WHEN {column_q} IS NOT NULL AND TRIM({column_q}) = '' AND {column_q} <> '' THEN 1 ELSE 0 END) AS whitespace_only_rows,
                SUM(CASE WHEN {column_q} IS NOT NULL AND LOWER(TRIM({column_q})) IN ('null', 'none', 'nan', 'n/a') THEN 1 ELSE 0 END) AS literal_null_rows
            FROM {table_q}
        """)
    ).mappings().first()


def audit_text_column_chunked(engine, table_name, column_name, pk_column, chunk_size=100000):
    table_q = quote_ident(table_name)
    column_q = quote_ident(column_name)
    pk_q = quote_ident(pk_column)
    totals = {
        "edge_space_rows": 0,
        "whitespace_only_rows": 0,
        "literal_null_rows": 0,
    }

    with engine.connect() as conn:
        bounds = conn.execute(
            text(f"SELECT MIN({pk_q}), MAX({pk_q}) FROM {table_q}")
        ).fetchone()
    if not bounds or bounds[0] is None or bounds[1] is None:
        return totals

    start = int(bounds[0])
    max_id = int(bounds[1])
    while start <= max_id:
        end = start + chunk_size - 1
        with engine.connect() as conn:
            row = conn.execute(
                text(f"""
                    SELECT
                        SUM(CASE WHEN {column_q} IS NOT NULL AND {column_q} <> TRIM({column_q}) THEN 1 ELSE 0 END) AS edge_space_rows,
                        SUM(CASE WHEN {column_q} IS NOT NULL AND TRIM({column_q}) = '' AND {column_q} <> '' THEN 1 ELSE 0 END) AS whitespace_only_rows,
                        SUM(CASE WHEN {column_q} IS NOT NULL AND LOWER(TRIM({column_q})) IN ('null', 'none', 'nan', 'n/a') THEN 1 ELSE 0 END) AS literal_null_rows
                    FROM {table_q}
                    WHERE {pk_q} BETWEEN :start_id AND :end_id
                """),
                {"start_id": start, "end_id": end},
            ).mappings().first()
        for key in totals:
            totals[key] += int(row[key] or 0)
        start = end + 1

    return totals


def audit_database():
    engine, database = load_engine()
    report = {
        "database": database,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "tables": [],
        "summary": {
            "tables_scanned": 0,
            "tables_with_text_cleanup": 0,
            "text_columns_with_cleanup": 0,
            "edge_space_rows": 0,
            "whitespace_only_rows": 0,
            "literal_null_rows": 0,
        },
    }

    conn = engine.connect()
    try:
        table_names = get_tables(conn, database)
    finally:
        conn.close()

    for table_name in table_names:
        conn = engine.connect()
        try:
            columns = get_columns(conn, database, table_name)
            row_count = count_rows(conn, table_name)
            pk_column = get_integer_primary_key(conn, database, table_name)
        finally:
            conn.close()

        table_report = {
            "table": table_name,
            "row_count": row_count,
            "chunked_by": pk_column,
            "text_columns": [],
        }

        for col in columns:
            if col["data_type"] not in TEXT_TYPES:
                continue
            error = None
            try:
                col_conn = engine.connect()
                try:
                    stats = audit_text_column(col_conn, table_name, col["name"])
                finally:
                    col_conn.close()
            except Exception as exc:
                engine.dispose()
                if not pk_column:
                    stats = {"edge_space_rows": 0, "whitespace_only_rows": 0, "literal_null_rows": 0}
                    error = str(exc)
                else:
                    try:
                        stats = audit_text_column_chunked(engine, table_name, col["name"], pk_column)
                    except Exception as chunk_exc:
                        engine.dispose()
                        stats = {"edge_space_rows": 0, "whitespace_only_rows": 0, "literal_null_rows": 0}
                        error = str(chunk_exc)

            edge = int(stats["edge_space_rows"] or 0)
            whitespace = int(stats["whitespace_only_rows"] or 0)
            literal_null = int(stats["literal_null_rows"] or 0)
            needs_cleanup = edge > 0 or whitespace > 0
            table_report["text_columns"].append({
                "column": col["name"],
                "type": col["column_type"],
                "nullable": col["is_nullable"],
                "edge_space_rows": edge,
                "whitespace_only_rows": whitespace,
                "literal_null_rows": literal_null,
                "safe_cleanup_needed": needs_cleanup,
                "audit_error": error,
            })

            report["summary"]["edge_space_rows"] += edge
            report["summary"]["whitespace_only_rows"] += whitespace
            report["summary"]["literal_null_rows"] += literal_null
            if needs_cleanup:
                report["summary"]["text_columns_with_cleanup"] += 1

        if any(c["safe_cleanup_needed"] for c in table_report["text_columns"]):
            report["summary"]["tables_with_text_cleanup"] += 1

        report["tables"].append(table_report)
        report["summary"]["tables_scanned"] += 1

    return report


def backup_table(conn, table_name, timestamp):
    prefix = f"safe_clean_backup_{timestamp}_"
    max_table_len = 64 - len(prefix)
    backup_name = f"{prefix}{table_name[:max_table_len]}"
    conn.execute(text(f"DROP TABLE IF EXISTS {quote_ident(backup_name)}"))
    conn.execute(text(f"CREATE TABLE {quote_ident(backup_name)} LIKE {quote_ident(table_name)}"))
    conn.execute(text(f"INSERT INTO {quote_ident(backup_name)} SELECT * FROM {quote_ident(table_name)}"))
    return backup_name


def apply_safe_cleanup():
    audit = audit_database()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    engine, _database = load_engine()
    result = {
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "audit_summary": audit["summary"],
        "tables": [],
    }

    with engine.begin() as conn:
        for table in audit["tables"]:
            cleanup_columns = [c for c in table["text_columns"] if c["safe_cleanup_needed"]]
            if not cleanup_columns:
                continue

            row_count_before = count_rows(conn, table["table"])
            backup_name = backup_table(conn, table["table"], timestamp)
            table_q = quote_ident(table["table"])
            table_result = {
                "table": table["table"],
                "backup_table": backup_name,
                "row_count_before": row_count_before,
                "columns_cleaned": [],
            }

            for col in cleanup_columns:
                column_q = quote_ident(col["column"])
                before = dict(audit_text_column(conn, table["table"], col["column"]))
                conn.execute(
                    text(f"""
                        UPDATE {table_q}
                        SET {column_q} = TRIM({column_q})
                        WHERE {column_q} IS NOT NULL
                          AND {column_q} <> TRIM({column_q})
                    """)
                )
                after = dict(audit_text_column(conn, table["table"], col["column"]))
                table_result["columns_cleaned"].append({
                    "column": col["column"],
                    "before": {k: int(v or 0) for k, v in before.items()},
                    "after": {k: int(v or 0) for k, v in after.items()},
                })

            row_count_after = count_rows(conn, table["table"])
            table_result["row_count_after"] = row_count_after
            table_result["row_count_unchanged"] = row_count_before == row_count_after
            result["tables"].append(table_result)

    result["completed_at"] = datetime.now().isoformat(timespec="seconds")
    return result


def apply_chunked_cleanup(chunk_size=50000, only_tables=None):
    engine, database = load_engine()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    result = {
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "database": database,
        "chunk_size": chunk_size,
        "tables": [],
        "skipped_tables": [],
    }

    conn = engine.connect()
    try:
        tables = get_tables(conn, database)
    finally:
        conn.close()

    requested_tables = set(only_tables or [])
    for table_name in tables:
        if requested_tables and table_name not in requested_tables:
            continue
        if is_backup_table(table_name):
            result["skipped_tables"].append({"table": table_name, "reason": "backup table skipped"})
            continue

        conn = engine.connect()
        try:
            all_columns = get_columns(conn, database, table_name)
            excluded_columns = TABLE_COLUMN_EXCLUDES.get(table_name, set())
            primary_key_columns = get_primary_key_columns(conn, database, table_name)
            text_columns = [
                c for c in all_columns
                if c["data_type"] in TEXT_TYPES
                and not c.get("is_generated")
                and c["name"] not in excluded_columns
                and c["name"] not in primary_key_columns
            ]
            backup_columns = real_column_list(all_columns)
            pk_column = get_integer_primary_key(conn, database, table_name)
            row_count_before = count_rows(conn, table_name)
        finally:
            conn.close()

        if not text_columns:
            continue

        table_q = quote_ident(table_name)
        condition = dirty_condition(text_columns)
        assignments = trimmed_assignments(text_columns)
        backup_name = changed_backup_name(table_name, timestamp)
        backup_q = quote_ident(backup_name)

        table_result = {
            "table": table_name,
            "row_count_before": row_count_before,
            "row_count_after": None,
            "row_count_unchanged": None,
            "backup_table": backup_name,
            "pk_column": pk_column,
            "changed_rows_reported": 0,
            "status": "completed",
            "error": None,
        }

        try:
            with engine.begin() as conn:
                conn.execute(text(f"DROP TABLE IF EXISTS {backup_q}"))
                conn.execute(text(f"CREATE TABLE {backup_q} LIKE {table_q}"))

                if pk_column:
                    pk_q = quote_ident(pk_column)
                    bounds = conn.execute(text(f"SELECT MIN({pk_q}), MAX({pk_q}) FROM {table_q}")).fetchone()
                    if bounds and bounds[0] is not None and bounds[1] is not None:
                        start = int(bounds[0])
                        max_id = int(bounds[1])
                        while start <= max_id:
                            end = start + chunk_size - 1
                            range_filter = f"{pk_q} BETWEEN :start_id AND :end_id"
                            conn.execute(
                                text(f"""
                                    INSERT IGNORE INTO {backup_q} ({backup_columns})
                                    SELECT {backup_columns} FROM {table_q}
                                    WHERE {range_filter}
                                      AND ({condition})
                                """),
                                {"start_id": start, "end_id": end},
                            )
                            update_result = conn.execute(
                                text(f"""
                                    UPDATE {table_q}
                                    SET {assignments}
                                    WHERE {range_filter}
                                      AND ({condition})
                                """),
                                {"start_id": start, "end_id": end},
                            )
                            table_result["changed_rows_reported"] += int(update_result.rowcount or 0)
                            start = end + 1
                else:
                    if row_count_before > 100000 and not requested_tables:
                        table_result["status"] = "skipped"
                        table_result["error"] = "large table without integer primary key"
                    else:
                        conn.execute(text(f"INSERT INTO {backup_q} ({backup_columns}) SELECT {backup_columns} FROM {table_q} WHERE {condition}"))
                        update_result = conn.execute(
                            text(f"UPDATE {table_q} SET {assignments} WHERE {condition}")
                        )
                        table_result["changed_rows_reported"] = int(update_result.rowcount or 0)

                row_count_after = count_rows(conn, table_name)
                table_result["row_count_after"] = row_count_after
                table_result["row_count_unchanged"] = row_count_before == row_count_after

                if table_result["changed_rows_reported"] == 0:
                    conn.execute(text(f"DROP TABLE IF EXISTS {backup_q}"))
                    table_result["backup_table"] = None

        except Exception as exc:
            engine.dispose()
            table_result["status"] = "failed"
            table_result["error"] = str(exc)

        result["tables"].append(table_result)
        print(
            f"{table_name}: {table_result['status']}, changed={table_result['changed_rows_reported']}, "
            f"rows_unchanged={table_result['row_count_unchanged']}"
        )

    result["completed_at"] = datetime.now().isoformat(timespec="seconds")
    result["summary"] = {
        "tables_seen": len(tables),
        "tables_processed": len(result["tables"]),
        "tables_changed": sum(1 for t in result["tables"] if t["changed_rows_reported"] > 0),
        "tables_failed": sum(1 for t in result["tables"] if t["status"] == "failed"),
        "tables_skipped": len(result["skipped_tables"]) + sum(1 for t in result["tables"] if t["status"] == "skipped"),
        "all_processed_row_counts_unchanged": all(
            t["row_count_unchanged"] for t in result["tables"] if t["status"] == "completed"
        ),
    }
    return result


def write_report(name, payload):
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORT_DIR / name
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return path


def print_summary(payload):
    summary = payload.get("summary") or payload.get("audit_summary") or {}
    print(json.dumps(summary, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Audit and safely clean text columns without deleting rows.")
    parser.add_argument("--mode", choices=["audit", "apply", "chunk-clean"], default="audit")
    parser.add_argument("--chunk-size", type=int, default=50000)
    parser.add_argument("--tables", help="Comma-separated table list for chunk-clean mode.")
    args = parser.parse_args()

    if args.mode == "audit":
        payload = audit_database()
        path = write_report(f"db_clean_audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json", payload)
        print(f"Audit report: {path}")
        print_summary(payload)
    elif args.mode == "apply":
        payload = apply_safe_cleanup()
        path = write_report(f"db_safe_cleanup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json", payload)
        print(f"Cleanup report: {path}")
        print_summary(payload)
        changed_tables = len(payload["tables"])
        unchanged = all(t["row_count_unchanged"] for t in payload["tables"])
        print(f"Tables cleaned: {changed_tables}")
        print(f"Row counts unchanged: {unchanged}")
    else:
        only_tables = [t.strip() for t in args.tables.split(",")] if args.tables else None
        payload = apply_chunked_cleanup(args.chunk_size, only_tables=only_tables)
        path = write_report(f"db_chunk_cleanup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json", payload)
        print(f"Chunk cleanup report: {path}")
        print_summary(payload)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
