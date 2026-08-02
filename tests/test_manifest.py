import json
from pathlib import Path

MANIFEST = (
    Path(__file__).resolve().parent.parent
    / "custom_components" / "wing_delivery" / "manifest.json"
)
HACS = Path(__file__).resolve().parent.parent / "hacs.json"

REQUIRED = {
    "domain", "name", "version", "documentation",
    "issue_tracker", "codeowners",
}


def test_manifest_has_required_keys():
    data = json.loads(MANIFEST.read_text())
    assert REQUIRED.issubset(data.keys())
    assert data["domain"] == "wing_delivery"
    assert data["codeowners"] == ["@ajachierno"]
    assert data["config_flow"] is True
    assert data["iot_class"] == "cloud_polling"
    assert data["requirements"] == []


def test_hacs_json_has_name():
    data = json.loads(HACS.read_text())
    assert data["name"] == "Wing Delivery"
