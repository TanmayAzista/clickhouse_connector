# clickhouse-connector

It connects Clickhouse with QGIS, enabling seamless integration and visualization of spatial data. It retrieves records from ClickHouse — either a native `Point` column or separate latitude/longitude columns — and displays them as a live, continuously-refreshing layer in QGIS as you pan and zoom. This plugin allows users to easily manage and visualize large geospatial datasets stored in Clickhouse directly within the QGIS environment.

# Clickhouse Plugin for QGIS

Query and Visualize [Clickhouse](https://clickhouse.com/) geospatial data in QGIS.

**Requirements**

************
QGIS 3.34 LTR (tested; earlier 3.x versions not verified)
- Tested successfully in 3.44.13

**Important Note**

---
 - The code uses "—break-system-packages" to install the dependencies (try it at your own risk).
 - **Location Data Type**: choose how your table stores position data before clicking Display AIS —
   - **Single Point Column**: a native ClickHouse `Point` column.
   - **Separate Lat/Lon Columns**: two separate numeric (`Float32`/`Float64`) columns; pick which is latitude and which is longitude.
 - **Viewport-driven rendering**: Display AIS doesn't load the whole result set at once. It splits the current map view into a grid and fetches up to a capped number of points per grid cell, so the total number of rendered points stays bounded no matter how large the table is. As you pan or zoom, the grid and query automatically refresh to match the new view. Grid rows, columns, and points-per-cell are adjustable from the **Grid Settings** row (defaults: 10 rows, 10 columns, 100 points per cell). Recommended to use <200k capped points overall. 
 - By default, before the per-cell cap is applied:
   - If a timestamp field is selected, only the last 8 hours of data is queried — use the Basic Query Tool to write your own filter for a different time range (it still composes with the viewport grid/cap).
   - If no timestamp field is selected, the whole table is queried — the per-cell cap is what keeps this fast regardless of table size.
   - A very zoomed-out view (e.g. the whole world) still has to check every candidate row against the current viewport, so it can be noticeably slower than a zoomed-in view. May be able to resolve with a spatial index in the DB.
## Install

#### Install from ZIP file

The plugin can be installed using **Install from ZIP** option on the **QGIS plugin manager**.

* Download zip file from the required plugin released version.
* From the **Install from ZIP** page, select the zip file and click the **Install** button to install plugin
* It might take a few minutes to get all the required dependencies for plugin to work

#### Install from QGIS plugin repository in experimental plugins

* Open QGIS application and open plugin manager.
* Search for `clickhouse_connector` in the All page of the plugin manager.
* From the found results, click on the `clickhouse_connector` result item and a page with plugin information will show up.
* Click the `Install Plugin` button at the bottom of the dialog to install the plugin.
