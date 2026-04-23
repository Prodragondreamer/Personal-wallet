from __future__ import annotations

from kivy.core.text import Label as CoreLabel
from kivy.graphics import Color, Line, Mesh, RoundedRectangle, Rectangle
from kivy.metrics import dp
from kivy.properties import BooleanProperty, ListProperty, NumericProperty, StringProperty
from kivy.uix.widget import Widget
import re


class LineChart(Widget):
    """
    Lightweight line chart with filled area (no external deps).

    Set `points_y` to a list of floats (y-values). X is spaced evenly.
    Set `rgba` to line color (r,g,b,a).
    """

    points_y = ListProperty([])  # list[float]
    labels_x = ListProperty([])  # list[str] aligned with points_y
    rgba = ListProperty([0.95, 0.80, 0.20, 1.0])
    hover_value = NumericProperty(0.0)
    hover_label = StringProperty("")
    hover_index = NumericProperty(-1)
    is_scrubbing = BooleanProperty(False)

    def on_points_y(self, *_args) -> None:
        self._redraw()

    def on_rgba(self, *_args) -> None:
        self._redraw()

    def on_labels_x(self, *_args) -> None:
        self._redraw()

    def on_size(self, *_args) -> None:
        self._redraw()

    def on_pos(self, *_args) -> None:
        self._redraw()

    def on_hover_value(self, *_args) -> None:
        # Property changes should update the overlay.
        self._redraw()

    def on_is_scrubbing(self, *_args) -> None:
        self._redraw()

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self.is_scrubbing = True
            self._update_hover_from_touch(touch)
            return True
        return super().on_touch_down(touch)

    def on_touch_move(self, touch):
        if self.is_scrubbing:
            self._update_hover_from_touch(touch)
            return True
        return super().on_touch_move(touch)

    def on_touch_up(self, touch):
        if self.is_scrubbing:
            self._update_hover_from_touch(touch)
            self.is_scrubbing = False
            return True
        return super().on_touch_up(touch)

    def _update_hover_from_touch(self, touch) -> None:
        pts = [float(v) for v in (self.points_y or [])]
        if len(pts) < 2:
            self.hover_value = 0.0
            self.hover_label = ""
            self.hover_index = -1
            return

        pad_x = self.width * 0.04
        left = self.x + pad_x
        right = self.right - pad_x
        if right <= left:
            self.hover_value = pts[-1]
            return

        n = len(pts)
        t = (touch.x - left) / (right - left)
        i = int(round(max(0.0, min(1.0, t)) * float(n - 1)))
        i = max(0, min(n - 1, i))
        self.hover_index = i
        self.hover_value = float(pts[i])
        labels = list(self.labels_x or [])
        self.hover_label = labels[i] if i < len(labels) else ""

    def _redraw(self) -> None:
        self.canvas.clear()
        pts = [float(v) for v in (self.points_y or [])]
        if len(pts) < 2:
            return

        min_v = min(pts)
        max_v = max(pts)
        if max_v - min_v < 1e-9:
            max_v = min_v + 1.0

        pad_x = self.width * 0.04
        pad_y = self.height * 0.08
        left = self.x + pad_x
        right = self.right - pad_x
        bottom = self.y + pad_y
        top = self.top - pad_y

        n = len(pts)
        dx = (right - left) / float(n - 1)

        xy: list[float] = []
        for i, v in enumerate(pts):
            x = left + dx * i
            y = bottom + ((v - min_v) / (max_v - min_v)) * (top - bottom)
            xy.extend([x, y])

        # Build a triangle strip mesh to fill the area under the line.
        vertices: list[float] = []
        indices: list[int] = []
        for i in range(n):
            x = xy[i * 2]
            y = xy[i * 2 + 1]
            # top vertex
            vertices.extend([x, y, 0, 0])
            # bottom vertex
            vertices.extend([x, bottom, 0, 0])
            if i < n - 1:
                base = i * 2
                indices.extend([base, base + 1, base + 2, base + 1, base + 3, base + 2])

        r, g, b, a = (list(self.rgba) + [1.0, 1.0, 1.0, 1.0])[:4]
        with self.canvas:
            # Subtle fill
            Color(r, g, b, 0.18 * a)
            Mesh(vertices=vertices, indices=indices, mode="triangles")

            # Line on top
            Color(r, g, b, a)
            Line(points=xy, width=1.6)

            # X-axis labels (start / mid / end). Show at least start/end.
            labels = [str(s) for s in (self.labels_x or [])]
            if len(labels) >= 2:
                wdays = {"Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"}
                sample = next((s for s in labels if (s or "").strip()), "")
                first_token = (sample.split(" ")[0] if sample else "").strip()

                looks_week = first_token in wdays
                looks_day = bool(re.search(r"\\d{1,2}:\\d{2}\\s?(AM|PM)", sample))
                looks_month = bool(re.match(r"^[A-Za-z]{3}\\s+\\d{1,2}$", sample.strip()))
                looks_year = bool(re.match(r"^[A-Za-z]{3}$", sample.strip()))

                if looks_week and len(labels) >= 7:
                    # 7 ticks Mon..Sun
                    idxs = [int(round((k / 6.0) * (len(labels) - 1))) for k in range(7)]
                elif looks_year and len(labels) >= 12:
                    # 12 ticks Jan..Dec across the series
                    idxs = [int(round((k / 11.0) * (len(labels) - 1))) for k in range(12)]
                elif looks_day:
                    # 5 ticks across the day
                    idxs = [int(round((k / 4.0) * (len(labels) - 1))) for k in range(5)]
                elif looks_month:
                    # 5 ticks across the month
                    idxs = [int(round((k / 4.0) * (len(labels) - 1))) for k in range(5)]
                else:
                    idxs = [0, len(labels) - 1] if len(labels) == 2 else [0, len(labels) // 2, len(labels) - 1]
                for j, idx in enumerate(idxs):
                    raw_txt = (labels[idx] or "").strip()
                    if looks_week:
                        # For week-like labels, only show day.
                        txt = raw_txt.split(" ")[0]
                    else:
                        txt = raw_txt
                    if not txt:
                        continue
                    lab = CoreLabel(text=txt, font_size=dp(10), color=(0.72, 0.74, 0.80, 1))
                    lab.refresh()
                    tw, th = lab.texture.size
                    if j == 0:
                        lx = left
                    elif j == 1 and len(idxs) == 3:
                        lx = (left + right) / 2 - (tw / 2)
                    elif len(idxs) > 3:
                        # distribute ticks evenly
                        t = j / float(max(1, len(idxs) - 1))
                        lx = left + t * (right - left) - (tw / 2)
                    else:
                        lx = right - tw
                    ly = self.y + dp(2)
                    Color(1, 1, 1, 1)
                    Rectangle(texture=lab.texture, pos=(lx, ly), size=(tw, th))

            if self.is_scrubbing:
                hi = int(self.hover_index) if int(self.hover_index) >= 0 else n - 1
                hi = max(0, min(n - 1, hi))

                hx = left + dx * hi
                hy = xy[hi * 2 + 1]

                # Vertical marker
                Color(1, 1, 1, 0.18)
                Line(points=[hx, bottom, hx, top], width=1.0)

                # Dot
                Color(r, g, b, 1.0)
                Line(circle=(hx, hy, dp(3.5)), width=1.6)

                # Price + time bubble
                when = (self.hover_label or "").strip()
                text = f"{when}\n${float(self.hover_value):,.2f}" if when else f"${float(self.hover_value):,.2f}"
                label = CoreLabel(text=text, font_size=dp(12), color=(1, 1, 1, 1))
                label.refresh()
                tw, th = label.texture.size

                pad = dp(8)
                bw = tw + pad * 2
                bh = th + pad * 1.4

                bx = hx - (bw / 2)
                by = hy + dp(14)

                # keep bubble inside chart bounds
                bx = max(self.x + dp(6), min(self.right - bw - dp(6), bx))
                by = min(self.top - bh - dp(6), max(self.y + dp(6), by))

                Color(0, 0, 0, 0.35)
                RoundedRectangle(pos=(bx, by - dp(2)), size=(bw, bh), radius=[dp(12), dp(12), dp(12), dp(12)])
                Color(0.14, 0.15, 0.19, 0.95)
                RoundedRectangle(pos=(bx, by), size=(bw, bh), radius=[dp(12), dp(12), dp(12), dp(12)])

                Color(1, 1, 1, 1)
                Rectangle(texture=label.texture, pos=(bx + pad, by + (bh - th) / 2), size=(tw, th))

