import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv
from sqlalchemy import create_engine, text


BASE_DIR = Path(__file__).resolve().parent
REPORT_DIR = BASE_DIR / "cleaning_reports"

TEXT_TYPES = {"char", "varchar", "tinytext", "text", "mediumtext", "longtext"}
BACKUP_PREFIXES = ("safe_clean_changed_", "safe_clean_backup_")

# Columns excluded because trimming them can change generated unique hashes.
TABLE_COLUMN_EXCLUDES = {
    "magicpin": {"name", "address"},
}


def quote_ident(name):
    return f"`{str(name).replace('`', '``')}`"


def load_engine():
    load_dotenv(BASE_DIR / ".env")
    user = os.getenv("DB_USER")
    password = quote_plus(os.getenv("DB_PASSWORD") or "")
    host = os.getenv("DB_HOST")
    port = os.getenv("DB_PORT", "3306")
    database = os.getenv("DB_NAME")

    missing = [key for key, value in {
        "DB_USER": user,
        "DB_HOST": host,
        "DB_NAME": database,
    }.items() if not value]
    if missing:
        raise RuntimeError(f"Missing database settings in .env: {', '.join(missing)}")

    url = f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}?charset=utf8mb4"
    engine = create_engine(
        url,
        pool_pre_ping=True,
        pool_recycle=120,
        isolation_level="AUTOCOMMIT",
        connect_args={"read_timeout": 600, "write_timeout": 600},
    )
    return engine, database


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
    return [row[0] for row in rows]


def get_columns(conn, database, table_name):
    rows = conn.execute(
        text("""
            SELECT column_name, data_type, column_type, extra, generation_expression
            FROM information_schema.columns
            WHERE table_schema = :db
              AND table_name = :table
            ORDER BY ordinal_position
        """),
        {"db": database, "table": table_name},
    ).fetchall()
    return [
        {
            "name": row[0],
            "data_type": str(row[1]).lower(),
            "column_type": row[2],
            "extra": str(row[3] or "").lower(),
            "generation_expression": row[4],
            "is_generated": bool(row[4]) or "generated" in str(row[3] or "").lower(),
        }
        for row in rows
    ]


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
    return {row[0] for row in rows}


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


def count_rows(conn, table_name):
    return int(conn.execute(text(f"SELECT COUNT(*) FROM {quote_ident(table_name)}")).scalar() or 0)


def is_backup_table(table_name):
    lower = table_name.lower()
    return lower.startswith(BACKUP_PREFIXES) or "_backup_" in lower or lower.endswith("_backup")


def real_column_list(columns):
    return ", ".join(quote_ident(col["name"]) for col in columns if not col["is_generated"])


def dirty_condition(columns):
    parts = []
    for col in columns:
        column = quote_ident(col["name"])
        parts.append(f"({column} IS NOT NULL AND {column} <> TRIM({column}))")
    return " OR ".join(parts) if parts else "1 = 0"


def trimmed_assignments(columns):
    return ", ".join(f"{quote_ident(col['name'])} = TRIM({quote_ident(col['name'])})" for col in columns)


def backup_name_for(table_name, timestamp):
    prefix = f"safe_clean_changed_{timestamp}_"
    return f"{prefix}{table_name[:64 - len(prefix)]}"


def load_table_metadata(engine, database, table_name):
    with engine.connect() as conn:
        all_columns = get_columns(conn, database, table_name)
        primary_key_columns = get_primary_key_columns(conn, database, table_name)
        integer_pk = get_integer_primary_key(conn, database, table_name)
        row_count = count_rows(conn, table_name)

    excluded = TABLE_COLUMN_EXCLUDES.get(table_name, set())
    cleanable_columns = [
        col for col in all_columns
        if col["data_type"] in TEXT_TYPES
        and not col["is_generated"]
        and col["name"] not in primary_key_columns
        and col["name"] not in excluded
    ]

    return {
        "all_columns": all_columns,
        "cleanable_columns": cleanable_columns,
        "integer_pk": integer_pk,
        "row_count": row_count,
        "excluded_columns": sorted(excluded | primary_key_columns),
    }


def estimate_dirty_rows(conn, table_name, columns):
    if not columns:
        return 0
    table = quote_ident(table_name)
    condition = dirty_condition(columns)
    return int(conn.execute(text(f"SELECT COUNT(*) FROM {table} WHERE {condition}")).scalar() or 0)


def estimate_dirty_rows_chunked(conn, table_name, columns, pk_column, chunk_size):
    table = quote_ident(table_name)
    pk = quote_ident(pk_column)
    condition = dirty_condition(columns)
    bounds = conn.execute(text(f"SELECT MIN({pk}), MAX({pk}) FROM {table}")).fetchone()
    if not bounds or bounds[0] is None or bounds[1] is None:
        return 0

    total = 0
    start = int(bounds[0])
    max_id = int(bounds[1])
    while start <= max_id:
        end = start + chunk_size - 1
        total += int(conn.execute(
            text(f"""
                SELECT COUNT(*)
                FROM {table}
                WHERE {pk} BETWEEN :start_id AND :end_id
                  AND ({condition})
            """),
            {"start_id": start, "end_id": end},
        ).scalar() or 0)
        start = end + 1
    return total


def clean_table(engine, database, table_name, timestamp, chunk_size, dry_run, force_large_no_pk):
    metadata = load_table_metadata(engine, database, table_name)
    columns = metadata["cleanable_columns"]
    if not columns:
        return None

    table = quote_ident(table_name)
    condition = dirty_condition(columns)
    assignments = trimmed_assignments(columns)
    backup_table = backup_name_for(table_name, timestamp)
    backup = quote_ident(backup_table)
    backup_columns = real_column_list(metadata["all_columns"])

    result = {
        "table": table_name,
        "row_count_before": metadata["row_count"],
        "row_count_after": None,
        "row_count_unchanged": None,
        "backup_table": None if dry_run else backup_table,
        "integer_pk": metadata["integer_pk"],
        "excluded_columns": metadata["excluded_columns"],
        "changed_rows_reported": 0,
        "status": "completed",
        "error": None,
        "dry_run": dry_run,
    }

    try:
        with engine.begin() as conn:
            if dry_run:
                if metadata["integer_pk"]:
                    result["changed_rows_reported"] = estimate_dirty_rows_chunked(
                        conn, table_name, columns, metadata["integer_pk"], chunk_size
                    )
                elif metadata["row_count"] > 100000 and not force_large_no_pk:
                    result["status"] = "skipped"
                    result["error"] = "large table without integer primary key; use --force-large-no-pk for selected tables"
                else:
                    result["changed_rows_reported"] = estimate_dirty_rows(conn, table_name, columns)
                result["row_count_after"] = result["row_count_before"]
                result["row_count_unchanged"] = True
                return result

            conn.execute(text(f"DROP TABLE IF EXISTS {backup}"))
            conn.execute(text(f"CREATE TABLE {backup} LIKE {table}"))

            pk = metadata["integer_pk"]
            if pk:
                pk_q = quote_ident(pk)
                bounds = conn.execute(text(f"SELECT MIN({pk_q}), MAX({pk_q}) FROM {table}")).fetchone()
                if bounds and bounds[0] is not None and bounds[1] is not None:
                    start = int(bounds[0])
                    max_id = int(bounds[1])
                    while start <= max_id:
                        end = start + chunk_size - 1
                        range_filter = f"{pk_q} BETWEEN :start_id AND :end_id"
                        params = {"start_id": start, "end_id": end}
                        conn.execute(
                            text(f"""
                                INSERT IGNORE INTO {backup} ({backup_columns})
                                SELECT {backup_columns} FROM {table}
                                WHERE {range_filter}
                                  AND ({condition})
                            """),
                            params,
                        )
                        update_result = conn.execute(
                            text(f"""
                                UPDATE {table}
                                SET {assignments}
                                WHERE {range_filter}
                                  AND ({condition})
                            """),
                            params,
                        )
                        result["changed_rows_reported"] += int(update_result.rowcount or 0)
                        start = end + 1
            else:
                if metadata["row_count"] > 100000 and not force_large_no_pk:
                    result["status"] = "skipped"
                    result["error"] = "large table without integer primary key; use --force-large-no-pk for selected tables"
                else:
                    conn.execute(
                        text(f"INSERT IGNORE INTO {backup} ({backup_columns}) SELECT {backup_columns} FROM {table} WHERE {condition}")
                    )
                    update_result = conn.execute(text(f"UPDATE {table} SET {assignments} WHERE {condition}"))
                    result["changed_rows_reported"] = int(update_result.rowcount or 0)

            result["row_count_after"] = count_rows(conn, table_name)
            result["row_count_unchanged"] = result["row_count_before"] == result["row_count_after"]

            if result["changed_rows_reported"] == 0:
                conn.execute(text(f"DROP TABLE IF EXISTS {backup}"))
                result["backup_table"] = None
    except Exception as exc:
        engine.dispose()
        result["status"] = "failed"
        result["error"] = str(exc)

    return result


def run_cleaning(table_names=None, chunk_size=10000, dry_run=True, force_large_no_pk=False):
    engine, database = load_engine()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    requested = set(table_names or [])

    with engine.connect() as conn:
        tables = get_tables(conn, database)

    report = {
        "database": database,
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "dry_run": dry_run,
        "chunk_size": chunk_size,
        "tables": [],
        "skipped_tables": [],
    }

    for table_name in tables:
        if requested and table_name not in requested:
            continue
        if is_backup_table(table_name):
            report["skipped_tables"].append({"table": table_name, "reason": "backup table skipped"})
            continue

        result = clean_table(engine, database, table_name, timestamp, chunk_size, dry_run, force_large_no_pk)
        if result:
            report["tables"].append(result)
            print(
                f"{table_name}: {result['status']}, "
                f"changed={result['changed_rows_reported']}, "
                f"rows_unchanged={result['row_count_unchanged']}"
            )

    report["completed_at"] = datetime.now().isoformat(timespec="seconds")
    report["summary"] = {
        "tables_seen": len(tables),
        "tables_processed": len(report["tables"]),
        "tables_changed": sum(1 for row in report["tables"] if row["changed_rows_reported"] > 0),
        "tables_failed": sum(1 for row in report["tables"] if row["status"] == "failed"),
        "tables_skipped": len(report["skipped_tables"]) + sum(1 for row in report["tables"] if row["status"] == "skipped"),
        "all_processed_row_counts_unchanged": all(
            row["row_count_unchanged"] for row in report["tables"] if row["status"] == "completed"
        ),
    }
    return report


def write_report(report):
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    mode = "dry_run" if report["dry_run"] else "cleanup"
    path = REPORT_DIR / f"safe_db_{mode}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    return path


def main():
    parser = argparse.ArgumentParser(description="Safely trim text columns in the DB configured by backend/.env.")
    parser.add_argument("--apply", action="store_true", help="Actually update data. Default is dry-run only.")
    parser.add_argument("--tables", help="Comma-separated table names. Default: all non-backup tables.")
    parser.add_argument("--chunk-size", type=int, default=10000)
    parser.add_argument("--force-large-no-pk", action="store_true", help="Allow selected large tables without integer PK.")
    args = parser.parse_args()

    table_names = [name.strip() for name in args.tables.split(",")] if args.tables else None
    report = run_cleaning(
        table_names=table_names,
        chunk_size=args.chunk_size,
        dry_run=not args.apply,
        force_large_no_pk=args.force_large_no_pk,
    )
    path = write_report(report)
    print(f"Report: {path}")
    print(json.dumps(report["summary"], indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
