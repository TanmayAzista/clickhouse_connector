# -*- coding: utf-8 -*-
"""Background thread that streams one already-built ClickHouse query per viewport
refresh and emits results block by block.

Must never construct or touch QgsFeature/QgsVectorLayer/QMessageBox itself -- those
only ever happen on the GUI thread (constructing a Qt widget from a non-GUI QThread is
undefined behavior and previously crashed this plugin outright).
"""

from datetime import datetime

from qgis.PyQt.QtCore import QThread, pyqtSignal


class ViewportQueryThread(QThread):
    result_block = pyqtSignal(int, list)   # generation, list[(x, y, attrs_dict)]
    finished_ok = pyqtSignal(int)          # generation -- query completed, no error
    error = pyqtSignal(int, str)           # generation, message

    def __init__(self, client, sql, params, generation, column_names, location_column):
        super().__init__()
        self.client = client
        self.sql = sql
        self.params = params
        self.generation = generation
        self.column_names = column_names
        self.location_column = location_column
        self._cancel_requested = False

    def request_cancel(self):
        # Polled between blocks in run(); a plain bool is a single writer (GUI
        # thread) / single reader (this thread) flag, safe enough under the GIL
        # without extra locking.
        self._cancel_requested = True

    def run(self):
        try:
            with self.client.query_row_block_stream(self.sql, parameters=self.params) as stream:
                for block in stream:
                    if self._cancel_requested:
                        return
                    rows_out = self._process_block(block)
                    if rows_out:
                        self.result_block.emit(self.generation, rows_out)
            if not self._cancel_requested:
                self.finished_ok.emit(self.generation)
        except Exception as e:
            if not self._cancel_requested:
                self.error.emit(self.generation, str(e))

    def _process_block(self, block):
        out = []
        for row in block:
            if isinstance(self.location_column, tuple):
                lat_col, lon_col = self.location_column
                y = row[self.column_names.index(lat_col)]
                x = row[self.column_names.index(lon_col)]
                if y is None or x is None:
                    continue
            else:
                location_index = self.column_names.index(self.location_column)
                location = row[location_index]
                if not isinstance(location, tuple) or len(location) != 2:
                    continue
                # Must match the tupleElement(col, 1/2) order used to build the bbox
                # filter in viewport_query.build_query() -- (lon, lat).
                x, y = location

            # Skip points where latitude and longitude are both 0, and obviously
            # invalid coordinates.
            if x == 0 and y == 0:
                continue
            if x < -180 or x > 180 or y < -90 or y > 90:
                continue

            row = list(row)
            for i, value in enumerate(row):
                if isinstance(value, datetime):
                    row[i] = value.strftime('%Y-%m-%d %H:%M:%S')
            attrs = {col: val for col, val in zip(self.column_names, row)}
            out.append((x, y, attrs))
        return out
