"""Small strict runner for business/UI sequences, checks and compensating actions.

Bindings are data (API requests/native actions), not code or expected responses.
All required bindings/locators are checked before the first business mutation.
"""
from __future__ import annotations
from copy import deepcopy
import re

from .core import Blocked, require, wait

_VARIABLE = re.compile(r"\$\{([A-Za-z0-9_.]+)\}")


def lookup(context, path):
    value = context
    for key in path.split("."):
        if isinstance(value, list) and key.isdigit(): value = value[int(key)]
        elif isinstance(value, dict) and key in value: value = value[key]
        else: raise Blocked(f"Missing runtime value: {path}")
    return value


def resolve(value, context):
    if isinstance(value, dict): return {k: resolve(v, context) for k,v in value.items()}
    if isinstance(value, list): return [resolve(v, context) for v in value]
    if not isinstance(value, str): return value
    match = _VARIABLE.fullmatch(value)
    if match: return deepcopy(lookup(context, match[1]))
    result = _VARIABLE.sub(lambda m: str(lookup(context, m[1])), value)
    if "${" in result or "{{" in result: raise Blocked("Unresolved runtime template")
    return result


def check(actual, expected, operator="eq"):
    if operator == "eq": require(type(actual) is type(expected) and actual == expected, "Value/type mismatch")
    elif operator == "contains": require(expected in actual, "Expected member missing")
    elif operator == "not_contains": require(expected not in actual, "Unexpected member present")
    elif operator == "same_set":
        require(len(actual) == len(set(actual)) and len(expected) == len(set(expected)), "Duplicate IDs in set assertion")
        require(set(actual) == set(expected), "Object ID sets differ")
    elif operator == "delta":
        require(type(actual) is int and type(expected[0]) is int and actual - expected[0] == expected[1], "Wrong count delta")
    else: raise Blocked(f"Unknown assertion operator: {operator}")


class Program:
    def __init__(self, api, actors, uis, bindings, context, report):
        self.api, self.actors, self.uis = api, actors, uis
        self.bindings, self.context, self.report = bindings, context, report

    def preflight(self, names):
        missing = []
        for name in names:
            binding = self.bindings.get(name)
            if not binding or not binding.get("source") or not binding.get("steps"):
                missing.append(name); continue
            for step in binding["steps"]:
                kind = step.get("kind")
                if kind not in {"api", "ui", "assert"}:
                    missing.append(f"{name}:invalid-step-kind"); continue
                if kind == "api" and (step.get("actor") not in {"a","b","c","leader","admin"}
                        or step.get("method") not in {"GET","POST","PUT","PATCH","DELETE"}
                        or not step.get("path", "").startswith("/api/v1/")):
                    missing.append(f"{name}:invalid-api-step")
                if kind == "api" and self.actors and step.get("actor") not in self.actors:
                    missing.append(f"{name}:missing-api-actor:{step.get('actor')}")
                if step.get("kind") == "ui":
                    role = step.get("actor")
                    if role not in self.uis: missing.append(f"{name}:UI:{role}"); continue
                    key = step.get("key")
                    if key and not self.uis[role].bindings.get(key, {}).get("evidence"):
                        missing.append(f"{name}:locator:{key}")
                    if step.get("action") not in {"back","restart","click","input","visible","value","enabled","rect","hold","scroll"}:
                        missing.append(f"{name}:invalid-ui-action")
        if missing: raise Blocked("Missing verified execution bindings: " + ", ".join(missing))

    def run(self, name, **arguments):
        self.preflight([name])
        local = {**self.context, "args": arguments}
        for step in self.bindings[name]["steps"]:
            spec = resolve(step, local)
            kind = spec["kind"]
            if kind == "api":
                result = self.api.request(self.actors[spec["actor"]], spec["method"], spec["path"],
                                          body=spec.get("body"), params=spec.get("params"))
            elif kind == "ui":
                result = self.uis[spec["actor"]].action(spec["action"], spec.get("key"),
                          value=spec.get("value"), **spec.get("parameters", {}))
            elif kind == "assert":
                check(spec["actual"], spec["expected"], spec.get("operator", "eq")); result = True
            else: raise Blocked(f"Unknown execution step kind: {kind}")
            if "save" in spec: local[spec["save"]] = result
        output = resolve(self.bindings[name].get("output", {}), local)
        require(isinstance(output, dict), "Binding output must be a facts object")
        self.report.append({"operation": name, "status": "passed"})
        return output
