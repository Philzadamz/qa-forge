"""Small helpers for copying openpyxl cell styles (used by xlsx_writer)."""

from copy import copy
from dataclasses import dataclass
from typing import cast

from openpyxl.cell.cell import Cell, MergedCell
from openpyxl.styles import Alignment, Border, Fill, Font


@dataclass
class CellStyle:
    font: Font
    fill: Fill
    border: Border
    alignment: Alignment
    number_format: str

    @classmethod
    def capture(cls, cell: Cell) -> "CellStyle":
        # openpyxl's cell.font/.fill/... are typed as StyleProxy in the stubs, but copy()
        # of one yields a real Font/Fill/Border/Alignment instance at runtime.
        return cls(
            font=cast(Font, copy(cell.font)),
            fill=cast(Fill, copy(cell.fill)),
            border=cast(Border, copy(cell.border)),
            alignment=cast(Alignment, copy(cell.alignment)),
            number_format=cell.number_format,
        )

    def apply(self, cell: Cell | MergedCell) -> None:
        cell.font = copy(self.font)
        cell.fill = copy(self.fill)
        cell.border = copy(self.border)
        cell.alignment = copy(self.alignment)
        cell.number_format = self.number_format
