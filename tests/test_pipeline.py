"""
Tests for the area statistics pipeline.

These run entirely offline - the geometry is built by hand and the Output Area
centroids are passed in directly, so nothing here touches the ONS or Nomis
APIs. That keeps them fast and means they still pass without a network.

Run them with:
    pytest
"""

import json
import os
import sys
import warnings

import pandas as pd
import pytest
from shapely.geometry import Polygon

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import census_api
import data_aggregates as agg
import points_in_polygon as pip


############################################################
# Fixtures - small synthetic stand-ins for the real data
############################################################

@pytest.fixture
def square_geojson(tmp_path):
    """A 1km square in EPSG:27700, with a declared CRS and a height on each point."""
    path = tmp_path / "square.geojson"
    ring = [[0, 0, 50.0], [1000, 0, 50.0], [1000, 1000, 50.0],
            [0, 1000, 50.0], [0, 0, 50.0]]
    path.write_text(json.dumps({
        "type": "FeatureCollection",
        "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:EPSG::27700"}},
        "features": [{
            "type": "Feature",
            "properties": {"id": "T001", "name": "Test Parish",
                           "loc": "Testville", "dean": "T"},
            "geometry": {"type": "Polygon", "coordinates": [ring]},
        }],
    }))
    return path


@pytest.fixture
def lookup_frame():
    """Two parishes in one deanery, three OAs each."""
    return pd.DataFrame({
        "OA": ["A1", "A2", "A3", "B1", "B2", "B3"],
        "ParishID": ["P1", "P1", "P1", "P2", "P2", "P2"],
        "Name": ["One"] * 3 + ["Two"] * 3,
        "Deanery": ["D"] * 6,
    })


@pytest.fixture
def census_frame():
    """A Census-shaped table: a Total plus two categories that sum to it."""
    return pd.DataFrame(
        {"Total": [10, 20, 30, 40, 50, 60],
         "Female": [4, 8, 12, 16, 20, 24],
         "Male": [6, 12, 18, 24, 30, 36]},
        index=pd.Index(["A1", "A2", "A3", "B1", "B2", "B3"], name="OA"),
    )


############################################################
# Step 1: reading the boundary
############################################################

def test_detect_crs_reads_declared_crs():
    data = {"crs": {"type": "name",
                    "properties": {"name": "urn:ogc:def:crs:EPSG::3857"}},
            "features": [{"geometry": {"coordinates": [[[0, 0]]]}}]}
    assert pip.detect_crs(data) == "EPSG:3857"


@pytest.mark.parametrize("coord, expected", [
    ([-2.3, 53.4], "EPSG:4326"),        # degrees
    ([380000, 398000], "EPSG:27700"),   # British National Grid
    ([-254124.0, 7072273.0], "EPSG:3857"),  # Web Mercator
])
def test_detect_crs_guesses_from_magnitude(coord, expected):
    data = {"features": [{"geometry": {"coordinates": [[coord]]}}]}
    assert pip.detect_crs(data) == expected


def test_load_boundary_strips_height_and_keeps_properties(square_geojson):
    geometry, properties = pip.load_boundary(str(square_geojson))
    assert not geometry.has_z, "height should be dropped before matching"
    assert geometry.is_valid
    assert properties["id"] == "T001"
    assert geometry.area == pytest.approx(1_000_000)


def test_load_boundary_handles_holes(tmp_path):
    """A boundary with a hole should have the hole's area excluded."""
    path = tmp_path / "donut.geojson"
    outer = [[0, 0], [1000, 0], [1000, 1000], [0, 1000], [0, 0]]
    hole = [[400, 400], [600, 400], [600, 600], [400, 600], [400, 400]]
    path.write_text(json.dumps({
        "type": "FeatureCollection",
        "crs": {"type": "name", "properties": {"name": "EPSG:27700"}},
        "features": [{"type": "Feature", "properties": {},
                      "geometry": {"type": "Polygon", "coordinates": [outer, hole]}}],
    }))
    geometry, _ = pip.load_boundary(str(path))
    # 1,000,000 minus the 200x200 hole
    assert geometry.area == pytest.approx(1_000_000 - 40_000)


def test_load_boundary_handles_multipolygon_and_several_features(tmp_path):
    """Two separate squares, whether as a MultiPolygon or as two features."""
    def square(x0):
        return [[[x0, 0], [x0 + 100, 0], [x0 + 100, 100], [x0, 100], [x0, 0]]]

    multi = tmp_path / "multi.geojson"
    multi.write_text(json.dumps({
        "type": "FeatureCollection",
        "crs": {"type": "name", "properties": {"name": "EPSG:27700"}},
        "features": [{"type": "Feature", "properties": {},
                      "geometry": {"type": "MultiPolygon",
                                   "coordinates": [square(0), square(500)]}}],
    }))

    split = tmp_path / "split.geojson"
    split.write_text(json.dumps({
        "type": "FeatureCollection",
        "crs": {"type": "name", "properties": {"name": "EPSG:27700"}},
        "features": [
            {"type": "Feature", "properties": {},
             "geometry": {"type": "Polygon", "coordinates": square(0)}},
            {"type": "Feature", "properties": {},
             "geometry": {"type": "Polygon", "coordinates": square(500)}},
        ],
    }))

    for path in (multi, split):
        geometry, _ = pip.load_boundary(str(path))
        assert geometry.area == pytest.approx(20_000), path.name


############################################################
# Step 1: the buffer
############################################################

def test_buffered_bounds_grows_the_box_in_every_direction():
    """
    Regression test. The buffer used to be added to all four bounds, which
    slid the search box diagonally instead of widening it, and could drop
    Output Areas near the south-western edge.
    """
    square = Polygon([(1000, 1000), (2000, 1000), (2000, 2000), (1000, 2000)])
    minx, miny, maxx, maxy = pip.buffered_bounds(square, buffer_m=300)

    assert (minx, miny, maxx, maxy) == (700, 700, 2300, 2300)
    assert minx < square.bounds[0] and miny < square.bounds[1]
    assert maxx > square.bounds[2] and maxy > square.bounds[3]


def test_buffer_keeps_a_centroid_near_the_south_west_corner():
    """The bug this guards against: a real OA just inside the SW edge."""
    square = Polygon([(1000, 1000), (2000, 1000), (2000, 2000), (1000, 2000)])
    corner = [["SW", 1050.0, 1050.0]]

    inside, _ = pip.find_oas_in_area(square, centroids=corner)
    assert [c[0] for c in inside] == ["SW"]

    # And it would have been missed by the old, shifted box.
    old_box = tuple(v + 300 for v in square.bounds)
    assert not (old_box[0] <= 1050 <= old_box[2] and old_box[1] <= 1050 <= old_box[3])


############################################################
# Step 1: matching and output
############################################################

def test_find_oas_splits_inside_from_outside():
    square = Polygon([(0, 0), (1000, 0), (1000, 1000), (0, 1000)])
    centroids = [["IN1", 500.0, 500.0], ["IN2", 100.0, 900.0],
                 ["OUT1", 1200.0, 500.0], ["OUT2", -50.0, 500.0]]

    inside, outside = pip.find_oas_in_area(square, centroids=centroids)

    assert [c[0] for c in inside] == ["IN1", "IN2"]
    assert [c[0] for c in outside] == ["OUT1", "OUT2"]


def test_write_outputs_builds_the_lookup_step_two_needs(tmp_path, square_geojson):
    _, properties = pip.load_boundary(str(square_geojson))
    inside = [["A1", 1.0, 2.0], ["A2", 3.0, 4.0]]

    csv_path = tmp_path / "out" / "lookup.csv"
    json_path = tmp_path / "out" / "oas.json"
    pip.write_outputs(inside, properties, str(json_path), str(csv_path))

    frame = pd.read_csv(csv_path)
    assert list(frame.columns) == ["OA", "ParishID", "Name", "Location", "Deanery"]
    assert frame["OA"].tolist() == ["A1", "A2"]
    assert set(frame["ParishID"]) == {"T001"}

    written = json.loads(json_path.read_text())
    assert written["count"] == 2
    assert written["parish"]["Name"] == "Test Parish"


############################################################
# Step 2: proportions
############################################################

def test_calculate_proportions_divides_by_total():
    row = pd.Series({"Total": 100, "Female": 40, "Male": 60})
    result = agg.calculate_proportions(row, ["Female", "Male"])
    assert result["Female_prop"] == pytest.approx(0.4)
    assert result["Male_prop"] == pytest.approx(0.6)


@pytest.mark.parametrize("total", [0, None])
def test_calculate_proportions_handles_an_empty_area(total):
    """
    Regression test. Dividing by a zero total used to give infinity, which
    looks like a real number in the output CSV. An empty cell is honest.
    """
    row = pd.Series({"Total": total, "Female": 0, "Male": 0})
    result = agg.calculate_proportions(row, ["Female", "Male"])
    assert pd.isna(result["Female_prop"])
    assert pd.isna(result["Male_prop"])


def test_calculate_proportions_defaults_to_every_column():
    row = pd.Series({"Total": 10, "Female": 4, "Male": 6})
    result = agg.calculate_proportions(row)
    assert "Female_prop" in result and "Male_prop" in result


############################################################
# Step 2: aggregation
############################################################

def test_transform_dataset_aggregates_and_totals(lookup_frame, census_frame):
    deanery, parish = agg.transform_dataset(census_frame, lookup_frame)

    assert parish.loc["P1", "Total"] == 60      # 10 + 20 + 30
    assert parish.loc["P2", "Total"] == 150     # 40 + 50 + 60
    assert deanery.loc["D", "Total"] == 210
    assert deanery.loc["Diocese", "Total"] == 210
    assert parish.loc["P1", "Female_prop"] == pytest.approx(24 / 60)


def test_transform_dataset_warns_about_output_areas_with_no_data(
        lookup_frame, census_frame):
    """An unmatched OA sums as zero, which would quietly understate the area."""
    trimmed = census_frame.drop(index=["A3"])

    with pytest.warns(UserWarning, match="no data"):
        _, parish = agg.transform_dataset(trimmed, lookup_frame)

    assert parish.loc["P1", "Total"] == 30      # A3's 30 is missing


def test_extract_relevant_rows_orders_and_renames(lookup_frame, census_frame):
    deanery, parish = agg.transform_dataset(census_frame, lookup_frame)
    report = agg.extract_relevant_rows(deanery, parish, ["P1"], ["D"], "My Parish")

    assert report.index.tolist() == ["My Parish", "Deanery D", "Diocese"]


def test_extract_relevant_rows_supports_several_parishes(lookup_frame, census_frame):
    deanery, parish = agg.transform_dataset(census_frame, lookup_frame)
    report = agg.extract_relevant_rows(
        deanery, parish, ["P1", "P2"], ["D"], {"P1": "One", "P2": "Two"}
    )
    assert report.index.tolist() == ["One", "Two", "Deanery D", "Diocese"]


############################################################
# Step 2: file naming
############################################################

def test_process_year_data_names_each_output_separately(
        tmp_path, lookup_frame, census_frame):
    """
    Regression test. The report path used to be reassigned inside the loop, so
    the second dataset was written to 'first.csvsecond.csv'.
    """
    lookup = tmp_path / "lookup.csv"
    lookup_frame.to_csv(lookup, index=False)

    full = tmp_path / "full"; full.mkdir()
    report = tmp_path / "report"; report.mkdir()

    datasets = []
    for name in ("first", "second"):
        path = tmp_path / f"{name}.csv"
        census_frame.to_csv(path)
        datasets.append({"path": str(path), "dataset": name,
                         "description": f"{name} table"})

    agg.process_year_data(
        "2021", datasets,
        [{"year": "2021", "path": f"{full}/"}],
        [{"year": "2021", "path": f"{report}/"}],
        str(lookup), ["P1"], ["D"],
    )

    assert sorted(os.listdir(report)) == ["first.csv", "second.csv"]
    assert sorted(os.listdir(full)) == [
        "deaneries_first.csv", "deaneries_second.csv",
        "parishes_first.csv", "parishes_second.csv",
    ]


############################################################
# The API client's reshaping, without touching the network
############################################################

def test_is_count_column_spots_derived_statistics():
    assert census_api.is_count_column("Age 0 to 4")
    assert census_api.is_count_column("Total")
    assert not census_api.is_count_column("Mean Age")
    assert not census_api.is_count_column("Median Age")
    assert not census_api.is_count_column("2001 Density(number of people per hectare)")


def test_nomis_dimensions_finds_the_category_columns():
    header = ["DATE", "DATE_NAME", "GEOGRAPHY", "GEOGRAPHY_NAME", "GEOGRAPHY_CODE",
              "C_SEX", "C_SEX_NAME", "MEASURES", "MEASURES_NAME", "OBS_VALUE"]
    assert census_api._nomis_dimensions(header) == ["C_SEX"]
