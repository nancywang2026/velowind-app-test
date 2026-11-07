"""Redact credentials before any payload enters a journal or Allure attachment."""
import re

MASK = "[REDACTED]"


def sensitive(key):
    normalized = re.sub(r"[^a-z0-9]", "", str(key).lower())
    return any(part in normalized for part in ("password", "passwd", "token", "secret", "authorization", "cookie", "apikey")) or normalized in {"phone", "mobile", "telephone"}


class Redactor:
    def __init__(self):
        self.secrets = set()

    def remember(self, value):
        if isinstance(value, dict):
            for key, item in value.items():
                if sensitive(key) and isinstance(item, (str, int)) and str(item):
                    self.secrets.add(str(item))
                self.remember(item)
        elif isinstance(value, list):
            for item in value:
                self.remember(item)

    def text(self, value):
        for secret in sorted(self.secrets, key=len, reverse=True):
            value = value.replace(secret, MASK)
        value = re.sub(r'(?i)(bearer\s+)[^\s"<>]+', r'\1[REDACTED]', value)
        value = re.sub(r'eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+', MASK, value)
        return re.sub(r'''(?ix)((?:password|passwd|access[_-]?token|refresh[_-]?token|secret|api[_-]?key|phone)\s*["']?\s*[:=]\s*["']?)[^\s,"'<>;&]+''', r'\1[REDACTED]', value)

    def clean(self, value):
        self.remember(value)
        return self._clean(value)

    def _clean(self, value):
        if isinstance(value, dict):
            return {k: MASK if sensitive(k) else self._clean(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self._clean(v) for v in value]
        if isinstance(value, str):
            return self.text(value)
        return value
