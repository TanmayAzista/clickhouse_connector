# -*- coding: utf-8 -*-
"""Geo/SQL construction for viewport-driven, per-grid-cell-capped ClickHouse queries.

Pure functions only (aside from the QGIS CRS transform) — no threading, no Qt signals.
"""

from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsProject,
)

GRID_ROWS = 10
GRID_COLS = 10
POINTS_PER_CELL = 100

_WGS84 = QgsCoordinateReferenceSystem("EPSG:4326")


def canvas_bbox_wgs84(iface):
    """Current map canvas extent, transformed to EPSG:4326 (WGS84 lat/lon degrees)."""
    canvas = iface.mapCanvas()
    transform = QgsCoordinateTransform(canvas.mapSettings().destinationCrs(), _WGS84, QgsProject.instance())
    return transform.transformBoundingBox(canvas.extent())


def grid_cell_size(bbox, rows=GRID_ROWS, cols=GRID_COLS):
    """(cell_height_degrees, cell_width_degrees) for the given bbox and grid shape."""
    cell_h = (bbox.yMaximum() - bbox.yMinimum()) / rows
    cell_w = (bbox.xMaximum() - bbox.xMinimum()) / cols
    return cell_h, cell_w


def build_query(base_query, location_column, bbox, cell_h, cell_w, grid_rows, grid_cols,
                 points_per_cell=POINTS_PER_CELL):
    """Wrap base_query in a bbox filter capped to points_per_cell per grid cell.

    location_column: either a str (single ClickHouse Point-typed column) or a
    (lat_col, lon_col) tuple of separate numeric columns -- same convention
    Clickhouse.py already uses elsewhere.

    grid_rows/grid_cols must be the same values used to compute cell_h/cell_w (via
    grid_cell_size) -- passed explicitly rather than re-read from a module constant so
    the degenerate-extent fallback below can never silently disagree with the caller's
    actual grid shape.

    Returns (sql, params) for client.query(sql, parameters=params) /
    client.query_row_block_stream(sql, parameters=params). params use ClickHouse's
    server-side {name:Type} query-parameter binding (confirmed against the installed
    clickhouse_connect driver) so float formatting/locale never leaks into the SQL text.
    """
    base = base_query.strip().rstrip(';')

    if isinstance(location_column, tuple):
        lat_col, lon_col = location_column
        lat_expr = f'base.{lat_col}'
        lon_expr = f'base.{lon_col}'
    else:
        # ClickHouse's Point type is Tuple(Float64, Float64) in (x, y) = (lon, lat)
        # order per its documented convention. Verify against a real Point column
        # before trusting this in production -- must stay consistent with the
        # row-unpack in viewport_query_thread.py's _process_block().
        lon_expr = f'tupleElement(base.{location_column}, 1)'
        lat_expr = f'tupleElement(base.{location_column}, 2)'

    params = {
        'min_lat': bbox.yMinimum(),
        'max_lat': bbox.yMaximum(),
        'min_lon': bbox.xMinimum(),
        'max_lon': bbox.xMaximum(),
    }
    where = (
        f"WHERE {lat_expr} BETWEEN {{min_lat:Float64}} AND {{max_lat:Float64}}\n"
        f"  AND {lon_expr} BETWEEN {{min_lon:Float64}} AND {{max_lon:Float64}}"
    )

    if cell_h > 0 and cell_w > 0:
        params['cell_h'] = cell_h
        params['cell_w'] = cell_w
        params['points_per_cell'] = points_per_cell
        # floor(), not intDiv(): intDiv's Float64 support is version-dependent in
        # ClickHouse; floor() is documented-safe on floats and works fine as a
        # LIMIT BY grouping key (only needs to be hashable/comparable, not an int).
        sql = (
            f"SELECT * FROM ({base}) AS base\n"
            f"{where}\n"
            f"LIMIT {{points_per_cell:UInt32}} BY\n"
            f"    floor(({lat_expr} - {{min_lat:Float64}}) / {{cell_h:Float64}}),\n"
            f"    floor(({lon_expr} - {{min_lon:Float64}}) / {{cell_w:Float64}})"
        )
    else:
        # Degenerate/zero-size extent (e.g. canvas hasn't painted yet) -- skip
        # per-cell bucketing, fall back to a flat cap on the whole viewport.
        sql = (
            f"SELECT * FROM ({base}) AS base\n"
            f"{where}\n"
            f"LIMIT {grid_rows * grid_cols * points_per_cell}"
        )

    return sql, params
