import argparse
import json
import re
from pathlib import Path


COLUMNS = [
    "id",
    "area_id",
    "area_name",
    "city_name",
    "state_short_code",
    "state_full_name",
    "country_name",
]

STATE_CODE_BY_NAME = {
    "andhra pradesh": "AP",
    "arunachal pradesh": "AR",
    "assam": "AS",
    "bihar": "BR",
    "chhattisgarh": "CG",
    "delhi": "DL",
    "goa": "GA",
    "gujarat": "GJ",
    "haryana": "HR",
    "himachal pradesh": "HP",
    "jammu & kashmir": "JK",
    "jammu and kashmir": "JK",
    "jharkhand": "JH",
    "karnataka": "KA",
    "kerala": "KL",
    "madhya pradesh": "MP",
    "maharashtra": "MH",
    "manipur": "MN",
    "meghalaya": "ML",
    "mizoram": "MZ",
    "nagaland": "NL",
    "odisha": "OD",
    "orissa": "OD",
    "punjab": "PB",
    "rajasthan": "RJ",
    "sikkim": "SK",
    "tamil nadu": "TN",
    "telangana": "TS",
    "tripura": "TR",
    "uttar pradesh": "UP",
    "uttarakhand": "UK",
    "west bengal": "WB",
    "puducherry": "PY",
}

CITY_FIXES = {
    "nuz id": "Nuzvid",
    "vijaywada": "Vijayawada",
    "banglore": "Bangalore",
    "bengaluru": "Bangalore",
    "gurgaon": "Gurugram",
    "bombay": "Mumbai",
    "calcutta": "Kolkata",
    "poona": "Pune",
}

STATE_FIXES = {
    "orissa": "Odisha",
    "jammu and kashmir": "Jammu & Kashmir",
    "jammu & kashmir": "Jammu & Kashmir",
}

UNKNOWN_CITY_STATE_FIXES = {
    "nraipur": ("AR", "Arunachal Pradesh"),
    "chaglagam": ("AR", "Arunachal Pradesh"),
    "nurpur": ("HP", "Himachal Pradesh"),
    "saligao": ("GA", "Goa"),
    "sundarnagar": ("HP", "Himachal Pradesh"),
    "paonta sahib": ("HP", "Himachal Pradesh"),
    "puducherry": ("PY", "Puducherry"),
    "betalbatim": ("GA", "Goa"),
    "varca": ("GA", "Goa"),
    "santa cruz": ("GA", "Goa"),
    "piyong": ("AR", "Arunachal Pradesh"),
    "yol cantonment": ("HP", "Himachal Pradesh"),
    "manmao": ("AR", "Arunachal Pradesh"),
    "goiliang": ("AR", "Arunachal Pradesh"),
    "raia": ("GA", "Goa"),
    "britona": ("GA", "Goa"),
    "chicalim": ("GA", "Goa"),
    "santokhgarh": ("HP", "Himachal Pradesh"),
    "guirim": ("GA", "Goa"),
    "shahjanpur": ("UP", "Uttar Pradesh"),
    "cortalim": ("GA", "Goa"),
    "mariyang": ("AR", "Arunachal Pradesh"),
    "baddi": ("HP", "Himachal Pradesh"),
    "siolim": ("GA", "Goa"),
    "merces": ("GA", "Goa"),
    "vijoynagar": ("AR", "Arunachal Pradesh"),
    "aldona": ("GA", "Goa"),
    "morjim": ("GA", "Goa"),
    "boleng": ("AR", "Arunachal Pradesh"),
    "walong": ("AR", "Arunachal Pradesh"),
    "borivali": ("MH", "Maharashtra"),
    "mechuka": ("AR", "Arunachal Pradesh"),
    "sagalee": ("AR", "Arunachal Pradesh"),
    "deomali": ("AR", "Arunachal Pradesh"),
    "diyun": ("AR", "Arunachal Pradesh"),
    "basmat": ("MH", "Maharashtra"),
    "aurangabad": ("MH", "Maharashtra"),
    "bhayandar": ("MH", "Maharashtra"),
    "kibithu": ("AR", "Arunachal Pradesh"),
    "jengging": ("AR", "Arunachal Pradesh"),
    "khadki": ("MH", "Maharashtra"),
    "lonavla": ("MH", "Maharashtra"),
    "puttur": ("KA", "Karnataka"),
    "kottayam-malabar": ("KL", "Kerala"),
}


def clean_text(value):
    if value is None:
        return None
    value = re.sub(r"\s+", " ", str(value)).strip()
    if value == "" or value.lower() in {"null", "none", "nan", "n/a"}:
        return None
    return value


def sql_escape(value):
    return str(value).replace("\\", "\\\\").replace("'", "\\'")


def sql_value(value):
    if value is None:
        return "NULL"
    if isinstance(value, int):
        return str(value)
    return f"'{sql_escape(value)}'"


def split_tuple_values(tuple_text):
    values = []
    current = []
    in_string = False
    i = 0
    while i < len(tuple_text):
        ch = tuple_text[i]
        if in_string:
            current.append(ch)
            if ch == "\\" and i + 1 < len(tuple_text):
                i += 1
                current.append(tuple_text[i])
            elif ch == "'":
                if i + 1 < len(tuple_text) and tuple_text[i + 1] == "'":
                    i += 1
                    current.append(tuple_text[i])
                else:
                    in_string = False
        else:
            if ch == "'":
                in_string = True
                current.append(ch)
            elif ch == ",":
                values.append("".join(current).strip())
                current = []
            else:
                current.append(ch)
        i += 1
    values.append("".join(current).strip())
    return values


def parse_scalar(token):
    if token.upper() == "NULL":
        return None
    if token.startswith("'") and token.endswith("'"):
        body = token[1:-1]
        body = body.replace("\\'", "'").replace("\\\\", "\\").replace("''", "'")
        return body
    try:
        return int(token)
    except ValueError:
        return token


def iter_insert_rows(sql_text):
    pattern = re.compile(
        r"INSERT INTO `Location_Master_India` \(`id`, `area_id`, `area_name`, `city_name`, `state_short_code`, `state_full_name`, `country_name`\) VALUES\s*(.*?);",
        re.S,
    )
    for match in pattern.finditer(sql_text):
        values_block = match.group(1)
        depth = 0
        in_string = False
        start = None
        i = 0
        while i < len(values_block):
            ch = values_block[i]
            if in_string:
                if ch == "\\":
                    i += 1
                elif ch == "'":
                    if i + 1 < len(values_block) and values_block[i + 1] == "'":
                        i += 1
                    else:
                        in_string = False
            else:
                if ch == "'":
                    in_string = True
                elif ch == "(":
                    if depth == 0:
                        start = i + 1
                    depth += 1
                elif ch == ")":
                    depth -= 1
                    if depth == 0 and start is not None:
                        tuple_text = values_block[start:i]
                        row = [parse_scalar(v) for v in split_tuple_values(tuple_text)]
                        if len(row) == len(COLUMNS):
                            yield dict(zip(COLUMNS, row))
            i += 1


def normalize_row(row):
    cleaned = dict(row)
    for key in ["area_name", "city_name", "state_short_code", "state_full_name", "country_name"]:
        cleaned[key] = clean_text(cleaned.get(key))

    if cleaned["city_name"]:
        cleaned["city_name"] = CITY_FIXES.get(cleaned["city_name"].lower(), cleaned["city_name"])

    if cleaned["state_full_name"]:
        state_key = cleaned["state_full_name"].lower()
        cleaned["state_full_name"] = STATE_FIXES.get(state_key, cleaned["state_full_name"])

    if cleaned["city_name"] and (not cleaned["state_full_name"] or cleaned["state_full_name"].lower() == "unknown"):
        inferred = UNKNOWN_CITY_STATE_FIXES.get(cleaned["city_name"].lower())
        if inferred:
            cleaned["state_short_code"], cleaned["state_full_name"] = inferred

    if cleaned["state_full_name"] and cleaned["state_full_name"].lower() in STATE_CODE_BY_NAME:
        cleaned["state_short_code"] = STATE_CODE_BY_NAME[cleaned["state_full_name"].lower()]
    elif cleaned["state_short_code"]:
        cleaned["state_short_code"] = cleaned["state_short_code"].upper()

    if not cleaned["country_name"]:
        cleaned["country_name"] = "India"

    return cleaned


def dedupe_key(row):
    return (
        (row["area_name"] or "").lower(),
        (row["city_name"] or "").lower(),
        (row["state_short_code"] or "").lower(),
        (row["state_full_name"] or "").lower(),
        (row["country_name"] or "").lower(),
    )


def render_inserts(rows, batch_size=1000):
    header = "INSERT INTO `Location_Master_India` (`id`, `area_id`, `area_name`, `city_name`, `state_short_code`, `state_full_name`, `country_name`) VALUES\n"
    blocks = []
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i + batch_size]
        lines = []
        for row in batch:
            rendered = ", ".join(sql_value(row[col]) for col in COLUMNS)
            lines.append(f"({rendered})")
        blocks.append(header + ",\n".join(lines) + ";")
    return "\n\n".join(blocks)


def clean_sql_file(source, output, report_path):
    sql_text = source.read_text(encoding="utf-8", errors="replace")
    first_insert = sql_text.find("INSERT INTO `Location_Master_India`")
    indexes_marker = sql_text.find("--\n-- Indexes for dumped tables")
    if first_insert == -1 or indexes_marker == -1:
        raise RuntimeError("Could not locate expected INSERT block or index footer.")

    prefix = sql_text[:first_insert]
    suffix = sql_text[indexes_marker:]

    rows = list(iter_insert_rows(sql_text))
    cleaned_rows = []
    seen = set()
    duplicate_count = 0
    changed_count = 0

    for row in rows:
        cleaned = normalize_row(row)
        if cleaned != row:
            changed_count += 1
        key = dedupe_key(cleaned)
        if key in seen:
            duplicate_count += 1
            continue
        seen.add(key)
        cleaned_rows.append(cleaned)

    auto_increment = max((row["id"] for row in cleaned_rows if isinstance(row["id"], int)), default=0) + 1
    suffix = re.sub(r"AUTO_INCREMENT=\d+", f"AUTO_INCREMENT={auto_increment}", suffix)

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(prefix + render_inserts(cleaned_rows) + "\n\n" + suffix, encoding="utf-8")

    report = {
        "source": str(source),
        "output": str(output),
        "input_rows": len(rows),
        "output_rows": len(cleaned_rows),
        "changed_rows": changed_count,
        "duplicates_removed": duplicate_count,
        "auto_increment": auto_increment,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description="Clean a Location_Master_India SQL dump without changing the source file.")
    parser.add_argument("source")
    parser.add_argument("--output", default="scratch/cleaned/Location_Master_India_cleaned.sql")
    parser.add_argument("--report", default="scratch/cleaned/Location_Master_India_cleaned_report.json")
    args = parser.parse_args()

    report = clean_sql_file(Path(args.source), Path(args.output), Path(args.report))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
