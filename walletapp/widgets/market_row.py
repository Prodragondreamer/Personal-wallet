from __future__ import annotations

from kivy.properties import ListProperty, StringProperty
from kivy.uix.boxlayout import BoxLayout


class MarketRow(BoxLayout):
    symbol = StringProperty("")
    price = StringProperty("")
    change = StringProperty("")
    change_color = ListProperty([0.72, 0.74, 0.80, 1.0])

