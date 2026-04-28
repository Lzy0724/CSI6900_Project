import hashlib
import json
import os
import re
import sqlite3
import threading
import time
import typing as t


def _normalize_sql(sql: str) -> str:
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.S)
    sql = re.sub(r"--.*?$", " ", sql, flags=re.M)
    sql = re.sub(r"\s+", " ", sql).strip().lower()
    return sql


def _extract_tables(sql: str) -> t.List[str]:
    table_pattern = re.compile(r"\b(?:from|join)\s+([a-z_][a-z0-9_\.]*)", re.I)
    tables = sorted(set(m.group(1).split(".")[-1].lower() for m in table_pattern.finditer(sql)))
    return tables


def _extract_join_types(sql: str) -> t.List[str]:
    join_types = []
    join_patterns = [
        (r"\bleft\s+join\b", "left"),
        (r"\bright\s+join\b", "right"),
        (r"\bfull\s+join\b", "full"),
        (r"\bcross\s+join\b", "cross"),
        (r"\binner\s+join\b", "inner"),
    ]
    for pattern, tag in join_patterns:
        if re.search(pattern, sql, flags=re.I):
            join_types.append(tag)
    if re.search(r"\bjoin\b", sql, flags=re.I) and not join_types:
        join_types.append("generic")
    return sorted(join_types)


def _extract_filter_template(sql: str) -> str:
    where_match = re.search(
        r"\bwhere\b(.*?)(\bgroup\s+by\b|\border\s+by\b|\bhaving\b|\blimit\b|;|$)",
        sql,
        flags=re.I | re.S,
    )
    if not where_match:
        return ""

    where_clause = where_match.group(1)
    where_clause = re.sub(r"'[^']*'", "?", where_clause)
    where_clause = re.sub(r"\b\d+(\.\d+)?\b", "?", where_clause)
    where_clause = re.sub(r"\s+", " ", where_clause).strip().lower()
    return where_clause


def extract_sql_features(sql: str) -> t.Dict[str, t.Any]:
    normalized = _normalize_sql(sql)
    features = {
        "tables": _extract_tables(normalized),
        "join_types": _extract_join_types(normalized),
        "filter_template": _extract_filter_template(normalized),
        "has_group_by": bool(re.search(r"\bgroup\s+by\b", normalized)),
        "has_having": bool(re.search(r"\bhaving\b", normalized)),
        "has_order_by": bool(re.search(r"\border\s+by\b", normalized)),
        "has_subquery": bool(re.search(r"\(\s*select\b", normalized)),
    }
    return features


def feature_fingerprint(features: t.Dict[str, t.Any]) -> str:
    canonical = json.dumps(features, ensure_ascii=True, sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class LearnedRewriteCache:
    def __init__(self, db_path: str):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._lock = threading.Lock()
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS learned_rule_cache (
                    fingerprint TEXT PRIMARY KEY,
                    features_json TEXT NOT NULL,
                    rule_sequence_json TEXT NOT NULL,
                    hits INTEGER NOT NULL DEFAULT 0,
                    created_at_ms INTEGER NOT NULL,
                    updated_at_ms INTEGER NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_learned_rule_cache_updated_at ON learned_rule_cache(updated_at_ms)"
            )
            conn.commit()

    def get(self, features: t.Dict[str, t.Any]) -> t.Optional[t.List[str]]:
        fp = feature_fingerprint(features)
        now_ms = int(time.time() * 1000)

        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT rule_sequence_json, hits FROM learned_rule_cache WHERE fingerprint = ?",
                (fp,),
            ).fetchone()
            if row is None:
                return None

            conn.execute(
                "UPDATE learned_rule_cache SET hits = ?, updated_at_ms = ? WHERE fingerprint = ?",
                (int(row["hits"]) + 1, now_ms, fp),
            )
            conn.commit()
            return json.loads(row["rule_sequence_json"])

    def put(self, features: t.Dict[str, t.Any], rule_sequence: t.List[str]) -> None:
        if not rule_sequence:
            return

        fp = feature_fingerprint(features)
        now_ms = int(time.time() * 1000)
        features_json = json.dumps(features, ensure_ascii=True, sort_keys=True)
        rule_sequence_json = json.dumps(rule_sequence, ensure_ascii=True)

        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO learned_rule_cache (
                    fingerprint, features_json, rule_sequence_json, hits, created_at_ms, updated_at_ms
                ) VALUES (?, ?, ?, 0, ?, ?)
                ON CONFLICT(fingerprint) DO UPDATE SET
                    features_json = excluded.features_json,
                    rule_sequence_json = excluded.rule_sequence_json,
                    updated_at_ms = excluded.updated_at_ms
                """,
                (fp, features_json, rule_sequence_json, now_ms, now_ms),
            )
            conn.commit()
