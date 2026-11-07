from __future__ import annotations
import json
import os
from pathlib import Path
from .core import Blocked


def read_configuration(path=None):
    path = path or os.getenv("VW_MESSAGE_REGRESSION_CONFIG")
    if not path: raise Blocked("Set VW_MESSAGE_REGRESSION_CONFIG to the private execution config")
    config_path = Path(path)
    try: data = json.loads(config_path.read_text())
    except (OSError, ValueError): raise Blocked("Cannot read message execution config") from None
    if data.get("api_origin") != "https://dev-api.velowind.com":
        raise Blocked("Only confirmed dev-api is supported")
    if data.get("observed_app_origin") != data["api_origin"] or not data.get("environment_evidence"):
        raise Blocked("Actual App API origin and environment evidence required")
    variables = {}
    grouped_accounts = {}
    if data.get("accounts_file"):
        account_path = Path(data["accounts_file"])
        if not account_path.is_absolute(): account_path = config_path.parent / account_path
        try:
            source = json.loads(account_path.read_text())
            grouped_accounts = source["accounts"]
            if not isinstance(grouped_accounts, dict) or not all(
                    isinstance(role, str) and isinstance(account, dict)
                    for role, account in grouped_accounts.items()):
                raise ValueError("Invalid grouped account structure")
        except (OSError, ValueError, KeyError, TypeError):
            raise Blocked("Cannot read grouped accounts file") from None
    if data.get("postman_environment"):
        try:
            source = json.loads(Path(data["postman_environment"]).read_text())
            variables = {x["key"]: x.get("value", "") for x in source["values"] if x.get("enabled", True)}
        except (OSError, ValueError, KeyError): raise Blocked("Cannot read Postman environment export") from None
    # Process environment overrides file values. Never write credentials back.
    variables.update(os.environ)
    accounts = {}
    for role in dict.fromkeys(("a", "b", "c", *data.get("accounts", {}).keys(), *grouped_accounts.keys())):
        spec = data.get("accounts", {}).get(role, {})
        account = {}
        for field in ("phone", "password", "user_id", "name"):
            key = spec.get(field + "_variable", field + "_" + role)
            grouped = grouped_accounts.get(role, {})
            grouped_field = "username" if field == "phone" else field
            value = os.environ.get(key, grouped.get(grouped_field, variables.get(key)))
            if not isinstance(value, str) or not value.strip() or "{{" in value:
                if data.get("accounts_file"):
                    raise Blocked(f"Missing grouped account field: {role}.{grouped_field}")
                raise Blocked(f"Missing Postman/environment variable: {key}")
            account[field] = value
        accounts[role] = account
    if len({accounts[r]["user_id"] for r in ("a","b","c")}) != 3 or len({accounts[r]["phone"] for r in ("a","b","c")}) != 3:
        raise Blocked("A/B/C must be distinct test accounts")
    return data, accounts


def audit_bindings(data, cases):
    bindings = data.get("operations", {})
    rows = []
    for case in cases:
        names = ("prepare." + case.id, *case.operations, "cleanup." + case.id)
        missing = [x for x in names if not bindings.get(x, {}).get("steps") or not bindings[x].get("source")]
        rows.append({"case_id": case.id, "title": case.title, "variants": list(case.variants),
                     "status": "blocked" if missing else "bindings-present-unverified",
                     "missing_operations": missing, "prerequisite": case.conditional or None})
    return rows
