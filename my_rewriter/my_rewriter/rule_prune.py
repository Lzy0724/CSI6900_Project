import re
import typing as t


def analyze_query_shape(query: str) -> t.Dict[str, bool]:
    q = query.lower()
    return {
        "has_agg": bool(re.search(r"\b(group\s+by|having|count\s*\(|sum\s*\(|avg\s*\(|min\s*\(|max\s*\()", q)),
        "has_join": bool(re.search(r"\bjoin\b", q)),
        "has_filter": bool(re.search(r"\bwhere\b", q)),
        "has_sort": bool(re.search(r"\border\s+by\b|\blimit\b|\bfetch\b", q)),
        "has_set_op": bool(re.search(r"\bunion\b|\bintersect\b|\bminus\b", q)),
        "has_window": bool(re.search(r"\bover\s*\(", q)),
        "has_subquery": bool(re.search(r"\(\s*select\b", q)),
        "has_values": bool(re.search(r"\bvalues\b", q)),
    }


def _need_agg(rule_name: str) -> bool:
    return "AGGREGATE" in rule_name


def _need_join(rule_name: str) -> bool:
    return "JOIN" in rule_name or "SEMI_JOIN" in rule_name


def _need_filter(rule_name: str) -> bool:
    return "FILTER" in rule_name


def _need_sort(rule_name: str) -> bool:
    return "SORT" in rule_name


def _need_set_op(rule_name: str) -> bool:
    return any(x in rule_name for x in ("UNION", "INTERSECT", "MINUS", "SET_OP"))


def _need_window(rule_name: str) -> bool:
    return "WINDOW" in rule_name


def _need_subquery(rule_name: str) -> bool:
    return "SUB_QUERY" in rule_name or "CORRELATE" in rule_name


def _need_values(rule_name: str) -> bool:
    return "VALUES" in rule_name


def should_keep_rule(rule_name: str, shape: t.Dict[str, bool]) -> bool:
    if _need_agg(rule_name) and not shape["has_agg"]:
        return False
    if _need_join(rule_name) and not (shape["has_join"] or shape["has_subquery"]):
        return False
    if _need_filter(rule_name) and not (shape["has_filter"] or shape["has_join"] or shape["has_subquery"]):
        return False
    if _need_sort(rule_name) and not shape["has_sort"]:
        return False
    if _need_set_op(rule_name) and not shape["has_set_op"]:
        return False
    if _need_window(rule_name) and not shape["has_window"]:
        return False
    if _need_subquery(rule_name) and not shape["has_subquery"]:
        return False
    if _need_values(rule_name) and not shape["has_values"]:
        return False
    return True


def prune_rules_for_query(query: str, rules: t.List[t.Dict[str, str]]) -> t.List[t.Dict[str, str]]:
    shape = analyze_query_shape(query)
    kept = [r for r in rules if should_keep_rule(r["name"], shape)]
    # Keep original behavior as fallback.
    return kept if kept else rules
