import json
from collections import Counter
from pathlib import Path

import numpy as np

import deep_sky_catalog


def test_messier_catalog_contains_expected_number_of_objects():
    assert len(deep_sky_catalog.MESSIER_CATALOG) == 110


def test_messier_catalog_contains_m31_with_coordinates():
    m31 = next(item for item in deep_sky_catalog.MESSIER_CATALOG if item["name"] == "M31")

    assert m31["display_name"] == "Andromeda Galaxy"
    assert abs(m31["ra"] - 10.6847) < 1e-4
    assert abs(m31["dec"] - 41.2690) < 1e-4
    assert m31["catalog"] == "Messier"


def test_simbad_catalog_file_contains_requested_catalog_families_offline():
    catalog_path = Path(deep_sky_catalog.__file__).with_name("deep_sky_catalog_simbad.json")
    payload = json.loads(catalog_path.read_text(encoding="utf-8"))
    objects = payload["objects"]
    counts = Counter(item["catalog"] for item in objects)

    assert payload["source"].startswith("SIMBAD TAP")
    assert counts["NGC"] > 7000
    assert counts["IC"] > 4000
    assert counts["LDN"] > 1700
    assert counts["Barnard"] > 300
    assert counts["Sharpless"] == 313
    assert counts["Caldwell"] == 109
    assert len({item["name"].casefold() for item in objects}) == len(objects)

    for item in objects:
        assert item["name"]
        assert item["catalog"] in counts
        assert isinstance(item["aliases"], list)
        assert item["ra"] is None or np.isfinite(item["ra"])
        assert item["dec"] is None or np.isfinite(item["dec"])


def test_loaded_local_catalog_exposes_large_ngc_ic_and_caldwell_sets():
    catalog_counts = Counter(item["catalog"] for item in deep_sky_catalog.DEEP_SKY_CATALOG)

    assert catalog_counts["NGC"] > 7000
    assert catalog_counts["IC"] > 4000
    assert catalog_counts["Caldwell"] == 109
    assert any(item["name"] == "C41" and "Hyades" in item["aliases"]
               for item in deep_sky_catalog.DEEP_SKY_CATALOG)
