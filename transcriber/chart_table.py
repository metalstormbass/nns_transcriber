from typing import Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QAbstractItemView, QTableWidget, QTableWidgetItem

from .models import NnsEvent


class ChartTable(QTableWidget):
    changed = Signal()

    COLUMNS = [
        "Section",
        "Bar",
        "Beat",
        "Number",
        "Quality",
        "Rhythm / Hits",
        "Repeat",
        "Time Sig",
        "Audio Start",
        "Audio End",
    ]

    def __init__(self):
        super().__init__(0, len(self.COLUMNS))
        self.setHorizontalHeaderLabels(self.COLUMNS)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.horizontalHeader().setStretchLastSection(True)
        self._suppress_changed = False
        self.cellChanged.connect(self._on_cell_changed)

    def _on_cell_changed(self, *_):
        if not self._suppress_changed:
            self.changed.emit()

    def add_event(self, event: Optional[NnsEvent] = None):
        if event is None:
            event = NnsEvent("VERSE", 1, 1.0, "1", "", "", "", "4/4", None, None)

        self._suppress_changed = True
        row = self.rowCount()
        self.insertRow(row)
        values = [
            event.section,
            event.bar,
            event.beat,
            event.number,
            event.quality,
            event.rhythm,
            event.repeat,
            event.time_signature,
            "" if event.audio_start is None else f"{event.audio_start:.3f}",
            "" if event.audio_end is None else f"{event.audio_end:.3f}",
        ]
        for col, value in enumerate(values):
            self.setItem(row, col, QTableWidgetItem(str(value)))
        self._suppress_changed = False
        self.changed.emit()

    def set_selected_time(self, column, value):
        rows = sorted({index.row() for index in self.selectedIndexes()})
        if not rows:
            return False

        self._suppress_changed = True
        for row in rows:
            self.setItem(row, column, QTableWidgetItem(f"{value:.3f}"))
        self._suppress_changed = False
        self.changed.emit()
        return True

    def selected_rows(self):
        return sorted({index.row() for index in self.selectedIndexes()})

    def events(self):
        output = []
        for row in range(self.rowCount()):
            raw = {
                "section": self.item(row, 0).text() if self.item(row, 0) else "VERSE",
                "bar": self.item(row, 1).text() if self.item(row, 1) else "1",
                "beat": self.item(row, 2).text() if self.item(row, 2) else "1",
                "number": self.item(row, 3).text() if self.item(row, 3) else "1",
                "quality": self.item(row, 4).text() if self.item(row, 4) else "",
                "rhythm": self.item(row, 5).text() if self.item(row, 5) else "",
                "repeat": self.item(row, 6).text() if self.item(row, 6) else "",
                "time_signature": self.item(row, 7).text() if self.item(row, 7) else "4/4",
                "audio_start": self.item(row, 8).text() if self.item(row, 8) else "",
                "audio_end": self.item(row, 9).text() if self.item(row, 9) else "",
            }
            output.append(NnsEvent.from_dict(raw))
        return output
