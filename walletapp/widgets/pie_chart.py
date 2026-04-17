from __future__ import annotations

from dataclasses import dataclass

from kivy.graphics import Color, Ellipse
from kivy.properties import ListProperty
from kivy.uix.widget import Widget


@dataclass(frozen=True)
class PieSlice:
    value: float
    rgba: tuple[float, float, float, float]


class PieChart(Widget):
    """
    Lightweight pie chart (no external deps).

    Set `values` to a list of (value, r, g, b, a).
    """

    values = ListProperty([])  # list[tuple[value, r, g, b, a]]

    def on_values(self, *_args) -> None:
        self._redraw()

    def on_size(self, *_args) -> None:
        self._redraw()

    def on_pos(self, *_args) -> None:
        self._redraw()

    def _redraw(self) -> None:
        self.canvas.clear()

        raw = list(self.values or [])
        total = sum(max(0.0, float(v[0])) for v in raw) if raw else 0.0
        if total <= 0:
            return

        size = min(self.width, self.height)
        pad = size * 0.05
        d = size - (2 * pad)
        x = self.center_x - d / 2
        y = self.center_y - d / 2

        start = 0.0
        with self.canvas:
            for v, r, g, b, a in raw:
                value = max(0.0, float(v))
                if value <= 0:
                    continue
                angle = 360.0 * (value / total)
                Color(r, g, b, a)
                Ellipse(pos=(x, y), size=(d, d), angle_start=start, angle_end=start + angle)
                start += angle

