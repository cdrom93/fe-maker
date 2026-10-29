import json
from pathlib import Path

LOCALES = Path(__file__).resolve().parents[2] / "ui" / "src" / "locales"


# Spanish and Italian are set aside (frozen files) until a more complete version.
ACTIVE = ("fr", "en")


def test_every_language_has_every_key():
    reference = set(json.loads((LOCALES / "fr.json").read_text(encoding="utf-8")))
    for path in (LOCALES / f"{lang}.json" for lang in ACTIVE):
        keys = set(json.loads(path.read_text(encoding="utf-8")))
        assert keys == reference, f"{path.name}: missing {sorted(reference - keys)}, extra {sorted(keys - reference)}"
