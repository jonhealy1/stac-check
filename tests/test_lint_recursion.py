import json

import pytest

from stac_check import display_messages
from stac_check.lint import Linter


def test_linter_collection_recursive():
    file = "sample_files/1.0.0/catalog-with-bad-item.json"
    linter = Linter(file, assets=False, links=False, recursive=True)
    assert linter.version == "1.0.0"
    assert linter.recursive == True
    assert linter.validate_all[0]["valid_stac"] is True  # root catalog
    msg = next(m for m in linter.validate_all if not m["valid_stac"])
    assert msg["error_type"] == "JSONSchemaValidationError"
    # Accept either 'message' or 'error_message' as the error string
    error_msg = msg.get("error_message") or msg.get("message", "")
    assert "'id' is a required property" in error_msg
    # Optionally check path, version, schema if present
    if "path" in msg:
        assert msg["path"].endswith("bad-item.json")


def test_linter_recursive_keeps_all_results_on_failure():
    """validate_all retains every validated object when the run fails, and
    the walk continues past an invalid item link (stac-valid >= 4.6.4)."""
    file = "sample_files/1.0.0/catalog-with-bad-item.json"
    linter = Linter(file, recursive=True)
    assert len(linter.validate_all) == 3  # catalog + both items
    assert sum(1 for m in linter.validate_all if not m["valid_stac"]) == 1
    assert any(
        m["path"].endswith("collectionless-item.json") and m["valid_stac"]
        for m in linter.validate_all
    )


def test_linter_recursive_trace_suppressed(capsys):
    """trace_recursion's per-object JSON dump does not leak to stdout."""
    Linter("sample_files/1.0.0/catalog-with-bad-item.json", recursive=True)
    out = capsys.readouterr().out
    assert '"valid_stac"' not in out


def test_linter_recursive_trace_verbose(capsys):
    """--verbose surfaces the upstream per-object trace output."""
    Linter(
        "sample_files/1.0.0/catalog-with-bad-item.json",
        recursive=True,
        verbose=True,
    )
    out = capsys.readouterr().out
    assert '"valid_stac"' in out


def test_linter_recursive_fast():
    """--recursive --fast uses FastValidator to validate the whole catalog."""
    file = "sample_files/1.0.0/catalog-with-bad-item.json"
    linter = Linter(file, recursive=True, fast=True)
    assert linter.recursive == True
    assert len(linter.validate_all) == 3  # catalog + 2 items
    assert all(
        msg["validation_method"] == "FastJSONSchema" for msg in linter.validate_all
    )
    invalid = next(msg for msg in linter.validate_all if not msg["valid_stac"])
    assert invalid["path"].endswith("bad-item.json")
    assert invalid["error_type"] == "FastValidationError"
    valid = [msg for msg in linter.validate_all if msg["valid_stac"]]
    assert len(valid) == 2


def test_linter_recursive_fast_missing_child():
    """Children that fail to load are reported as failed results."""
    file = "sample_files/1.0.0/catalog-with-missing-item.json"
    linter = Linter(file, recursive=True, fast=True)
    failed = [msg for msg in linter.validate_all if not msg["valid_stac"]]
    assert len(failed) == 1
    assert failed[0]["path"].endswith("does-not-exist.json")
    assert "Failed to load" in failed[0]["error_message"]
    assert failed[0]["asset_type"] == ""


def test_linter_recursive_fast_root_load_failure(monkeypatch):
    """A root document that fails to load inside FastValidator surfaces as a
    failed result instead of an empty summary."""
    from stac_validator import fast_validator as fv

    def _raise(self_v, resource_path):
        raise OSError("boom")

    monkeypatch.setattr(fv.FastValidator, "_load_json_resource", _raise)
    file = "sample_files/1.0.0/catalog-with-bad-item.json"
    linter = Linter(file, recursive=True, fast=True)
    assert len(linter.validate_all) == 1
    msg = linter.validate_all[0]
    assert msg["valid_stac"] is False
    assert msg["path"] == file
    assert "Failed to load" in msg["error_message"]


def test_linter_recursive_fast_max_depth_warns():
    file = "sample_files/1.0.0/catalog-with-bad-item.json"
    with pytest.warns(UserWarning, match="--max-depth is not supported"):
        linter = Linter(file, recursive=True, fast=True, max_depth=1)
    assert len(linter.validate_all) == 3


def test_linter_recursive_fast_dict_warns():
    """--fast is not supported for in-memory dicts; falls back with a warning."""
    file = "sample_files/1.0.0/catalog-with-bad-item.json"
    with open(file) as f:
        data = json.load(f)
    with pytest.warns(UserWarning, match="not supported for in-memory dict"):
        linter = Linter(data, recursive=True, fast=True)
    assert isinstance(linter.validate_all, list)


def test_linter_recursive_fast_remote(monkeypatch):
    """Relative child hrefs on remote catalogs resolve to valid https://
    URLs, and documents without a 'type' field are detected."""
    import requests_mock
    from stac_validator import fast_validator as fv

    # STAC Catalogs have no 'type' member at any version; the catalog
    # carries 'license' but must not be misclassified as a Collection,
    # which is identified by 'extent'.
    catalog = {
        "id": "root",
        "stac_version": "1.0.0",
        "description": "root catalog",
        "license": "proprietary",
        "links": [{"rel": "child", "href": "./collection.json"}],
    }
    collection = {
        "id": "col",
        "stac_version": "1.0.0",
        "description": "collection",
        "license": "proprietary",
        "extent": {"spatial": {"bbox": [[-180, -90, 180, 90]]}},
        "links": [{"rel": "item", "href": "./item.json"}],
    }
    item = {
        "type": "Feature",
        "stac_version": "1.0.0",
        "id": "i1",
        "geometry": None,
        "properties": {"datetime": "2020-01-01T00:00:00Z"},
        "links": [],
        "assets": {},
    }

    # Skip schema fetching/validation entirely; this test covers child URL
    # resolution and loading, not schema results.
    monkeypatch.setattr(fv, "get_validator", lambda *a, **k: (lambda data: None, None))
    with requests_mock.Mocker() as m:
        m.get("https://example.com/stac/catalog.json", json=catalog)
        m.get("https://example.com/stac/collection.json", json=collection)
        m.get("https://example.com/stac/item.json", json=item)
        linter = Linter(
            "https://example.com/stac/catalog.json", recursive=True, fast=True
        )

    assert len(linter.validate_all) == 3
    for msg in linter.validate_all:
        assert msg["path"].startswith("https://example.com/")
        assert msg["valid_stac"] is True
    assert {m["asset_type"] for m in linter.validate_all} == {
        "CATALOG",
        "COLLECTION",
        "ITEM",
    }


def test_linter_recursive_fast_headers(monkeypatch):
    """Custom headers are applied to FastValidator's HTTP session and
    restored afterwards."""
    from stac_validator import fast_validator as fv

    seen_headers = {}

    def spy_load(self_v, resource_path):
        seen_headers.update(fv.HTTP_SESSION.headers)
        return {
            "type": "Catalog",
            "id": "c",
            "stac_version": "1.0.0",
            "description": "d",
            "links": [],
        }

    monkeypatch.setattr(fv.FastValidator, "_load_json_resource", spy_load)
    file = "sample_files/1.0.0/catalog-with-bad-item.json"
    Linter(
        file,
        recursive=True,
        fast=True,
        headers={"Authorization": "Bearer token"},
    )
    assert seen_headers["Authorization"] == "Bearer token"
    assert "Authorization" not in fv.HTTP_SESSION.headers


def test_validate_collection_fast_forwards_headers():
    """Custom headers are forwarded to the linter instances used by
    --collections/--item-collection --fast."""
    from stac_check.fast_validator_wrapper import validate_collection_fast

    seen = []

    class FakeLinter:
        def __init__(self, item, **kwargs):
            seen.append(kwargs.get("headers"))
            self.message = [{"valid_stac": True, "schemas_checked": [], "errors": []}]
            self.best_practices_msg = []
            self.geometry_errors_msg = []

    results, _, _ = validate_collection_fast(
        "sample_files/1.0.0/feature_collection.json",
        FakeLinter,
        fast_linting=True,
        headers={"Authorization": "Bearer token"},
    )
    assert results
    assert seen
    assert all(h == {"Authorization": "Bearer token"} for h in seen)


def test_linter_recursive_fast_linting():
    """--recursive --fast-linting attaches best practices and geometry
    errors to each result without re-validating."""
    file = "sample_files/1.0.0/catalog-with-bad-item.json"
    linter = Linter(file, recursive=True, fast=True, fast_linting=True)
    assert len(linter.validate_all) == 3
    bad = next(m for m in linter.validate_all if not m["valid_stac"])
    assert any("datetime" in msg for msg in bad["best_practices"])
    assert any("bbox" in msg for msg in bad["geometry_errors"])
    catalog = linter.validate_all[0]
    assert any("title" in msg for msg in catalog["best_practices"])


def test_linter_recursive_fast_validates_root_once(monkeypatch):
    """The root document is validated by run_recursive() only; validate_file
    is not invoked separately, and the linter message reflects the root."""
    calls = []
    original = Linter.validate_file

    def spy(self, file):
        calls.append(file)
        return original(self, file)

    monkeypatch.setattr(Linter, "validate_file", spy)
    file = "sample_files/1.0.0/catalog-with-bad-item.json"
    linter = Linter(file, recursive=True, fast=True)
    assert calls == []
    assert linter.valid_stac is True
    assert linter.version == "1.0.0"
    assert linter.asset_type == "CATALOG"


def test_recursive_message_fast(capsys):
    """Fast recursive display shows fallback per-asset output plus the
    compact fast summary with timing information."""
    file = "sample_files/1.0.0/catalog-with-bad-item.json"
    linter = Linter(file, recursive=True, fast=True)
    display_messages.recursive_message(linter)
    out = capsys.readouterr().out
    assert "Passed: 2/3" in out
    assert "Failed: 1/3" in out
    assert "Total Validation Time" in out


def test_recursive_message_fast_silences_output(monkeypatch, capsys):
    """--fast recursive output silences per-asset display for large catalogs
    without re-instantiating a Linter for every result."""
    file = "sample_files/1.0.0/catalog-with-bad-item.json"
    linter = Linter(file, recursive=True, fast=True)
    linter.validate_all = [
        {
            "version": "1.0.0",
            "path": f"/tmp/item-{i}.json",
            "schema": [],
            "asset_type": "ITEM",
            "validation_method": "FastJSONSchema",
            "valid_stac": True,
            "error_type": "",
            "error_message": "",
        }
        for i in range(25)
    ]

    def _no_linter(*args, **kwargs):
        raise AssertionError("Linter must not be re-created in fast mode")

    monkeypatch.setattr(display_messages, "Linter", _no_linter)
    display_messages.recursive_message(linter)
    out = capsys.readouterr().out
    assert "silencing output" in out
    assert "Passed: 25/25" in out


def test_linter_recursive_max_depth_1():
    file = "https://radarstac.s3.amazonaws.com/stac/catalog.json"
    stac = Linter(file, assets=False, links=False, recursive=True, max_depth=1)
    assert stac.validate_all == [
        {
            "version": "0.7.0",
            "path": "https://radarstac.s3.amazonaws.com/stac/catalog.json",
            "schema": ["https://cdn.staclint.com/v0.7.0/catalog.json"],
            "asset_type": "CATALOG",
            "validation_method": "recursive",
            "validator_engine": "jsonschema",
            "valid_stac": True,
        }
    ]


def test_linter_recursive_max_depth_4():
    file = "https://radarstac.s3.amazonaws.com/stac/catalog.json"
    stac = Linter(file, assets=False, links=False, recursive=True, max_depth=4)
    assert stac.validate_all == [
        {
            "version": "0.7.0",
            "path": "https://radarstac.s3.amazonaws.com/stac/catalog.json",
            "schema": ["https://cdn.staclint.com/v0.7.0/catalog.json"],
            "asset_type": "CATALOG",
            "validation_method": "recursive",
            "validator_engine": "jsonschema",
            "valid_stac": True,
        },
        {
            "version": "0.7.0",
            "path": "https://radarstac.s3.amazonaws.com/stac/radarsat-1/collection.json",
            "schema": ["https://cdn.staclint.com/v0.7.0/collection.json"],
            "asset_type": "COLLECTION",
            "validation_method": "recursive",
            "validator_engine": "jsonschema",
            "valid_stac": True,
        },
        {
            "version": "0.7.0",
            "path": "https://radarstac.s3.amazonaws.com/stac/radarsat-1/slc/catalog.json",
            "schema": ["https://cdn.staclint.com/v0.7.0/catalog.json"],
            "asset_type": "CATALOG",
            "validation_method": "recursive",
            "validator_engine": "jsonschema",
            "valid_stac": True,
        },
        {
            "version": "0.7.0",
            "path": "https://radarstac.s3.amazonaws.com/stac/radarsat-1/slc/2012-05-13/RS1_M0630938_F2N_20120513_225708_HH_SLC.json",
            "schema": ["https://cdn.staclint.com/v0.7.0/item.json"],
            "asset_type": "ITEM",
            "validation_method": "recursive",
            "validator_engine": "jsonschema",
            "valid_stac": True,
        },
        {
            "version": "0.7.0",
            "path": "https://radarstac.s3.amazonaws.com/stac/radarsat-1/slc/2012-06-14/RS1_M0634796_F3F_20120614_110317_HH_SLC.json",
            "schema": ["https://cdn.staclint.com/v0.7.0/item.json"],
            "asset_type": "ITEM",
            "validation_method": "recursive",
            "validator_engine": "jsonschema",
            "valid_stac": True,
        },
        {
            "version": "0.7.0",
            "path": "https://radarstac.s3.amazonaws.com/stac/radarsat-1/slc/2012-06-14/RS1_M0634795_F3F_20120614_110311_HH_SLC.json",
            "schema": ["https://cdn.staclint.com/v0.7.0/item.json"],
            "asset_type": "ITEM",
            "validation_method": "recursive",
            "validator_engine": "jsonschema",
            "valid_stac": True,
        },
        {
            "version": "0.7.0",
            "path": "https://radarstac.s3.amazonaws.com/stac/radarsat-1/slc/2012-10-12/RS1_M0634798_F3F_20121012_110325_HH_SLC.json",
            "schema": ["https://cdn.staclint.com/v0.7.0/item.json"],
            "asset_type": "ITEM",
            "validation_method": "recursive",
            "validator_engine": "jsonschema",
            "valid_stac": True,
        },
        {
            "version": "0.7.0",
            "path": "https://radarstac.s3.amazonaws.com/stac/radarsat-1/slc/2012-10-12/RS1_M0634799_F3F_20121012_110331_HH_SLC.json",
            "schema": ["https://cdn.staclint.com/v0.7.0/item.json"],
            "asset_type": "ITEM",
            "validation_method": "recursive",
            "validator_engine": "jsonschema",
            "valid_stac": True,
        },
        {
            "version": "0.7.0",
            "path": "https://radarstac.s3.amazonaws.com/stac/radarsat-1/raw/catalog.json",
            "schema": ["https://cdn.staclint.com/v0.7.0/catalog.json"],
            "asset_type": "CATALOG",
            "validation_method": "recursive",
            "validator_engine": "jsonschema",
            "valid_stac": True,
        },
        {
            "version": "0.7.0",
            "path": "https://radarstac.s3.amazonaws.com/stac/radarsat-1/raw/2012-05-13/RS1_M0000676_F2N_20120513_225701_HH_RAW.json",
            "schema": ["https://cdn.staclint.com/v0.7.0/item.json"],
            "asset_type": "ITEM",
            "validation_method": "recursive",
            "validator_engine": "jsonschema",
            "valid_stac": True,
        },
    ]


def test_linter_recursive_100():
    file = "https://digital-atlas.s3.amazonaws.com/stac/public_stac/population/worldpop_2020/collection.json"
    stac = Linter(file, assets=False, links=False, recursive=True, max_depth=4)
    assert stac.validate_all == [
        {
            "asset_type": "COLLECTION",
            "path": "https://digital-atlas.s3.amazonaws.com/stac/public_stac/population/worldpop_2020/collection.json",
            "schema": [
                "https://stac-extensions.github.io/scientific/v1.0.0/schema.json",
                "https://schemas.stacspec.org/v1.0.0/collection-spec/json-schema/collection.json",
            ],
            "valid_stac": True,
            "validation_method": "recursive",
            "validator_engine": "jsonschema",
            "version": "1.0.0",
        },
        {
            "asset_type": "ITEM",
            "path": "https://digital-atlas.s3.amazonaws.com/stac/public_stac/population/worldpop_2020/./pop_2020/pop_2020.json",
            "schema": [
                "https://stac-extensions.github.io/projection/v1.1.0/schema.json",
                "https://stac-extensions.github.io/file/v2.1.0/schema.json",
                "https://stac-extensions.github.io/raster/v1.1.0/schema.json",
                "https://schemas.stacspec.org/v1.0.0/item-spec/json-schema/item.json",
            ],
            "valid_stac": True,
            "validation_method": "recursive",
            "validator_engine": "jsonschema",
            "version": "1.0.0",
        },
        {
            "asset_type": "ITEM",
            "path": "https://digital-atlas.s3.amazonaws.com/stac/public_stac/population/worldpop_2020/./popDens_2020/popDens_2020.json",
            "schema": [
                "https://stac-extensions.github.io/projection/v1.1.0/schema.json",
                "https://stac-extensions.github.io/file/v2.1.0/schema.json",
                "https://stac-extensions.github.io/raster/v1.1.0/schema.json",
                "https://schemas.stacspec.org/v1.0.0/item-spec/json-schema/item.json",
            ],
            "valid_stac": True,
            "validation_method": "recursive",
            "validator_engine": "jsonschema",
            "version": "1.0.0",
        },
        {
            "asset_type": "ITEM",
            "path": "https://digital-atlas.s3.amazonaws.com/stac/public_stac/population/worldpop_2020/./pop_2020_parquet/pop_2020_parquet.json",
            "schema": [
                "https://stac-extensions.github.io/table/v1.2.0/schema.json",
                "https://stac-extensions.github.io/file/v2.1.0/schema.json",
                "https://schemas.stacspec.org/v1.0.0/item-spec/json-schema/item.json",
            ],
            "valid_stac": True,
            "validation_method": "recursive",
            "validator_engine": "jsonschema",
            "version": "1.0.0",
        },
    ]
