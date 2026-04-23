from __future__ import annotations

from kivy.animation import Animation
from kivy.properties import BooleanProperty, NumericProperty
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.widget import Widget


class ModernSwitch(ButtonBehavior, Widget):
    """
    Custom switch to avoid default Kivy Switch visuals.

    - `active`: boolean state
    - `thumb_t`: 0..1 animation position
    """

    active = BooleanProperty(False)
    thumb_t = NumericProperty(0.0)

    def on_active(self, _instance, value: bool) -> None:
        Animation.cancel_all(self, "thumb_t")
        Animation(thumb_t=1.0 if value else 0.0, d=0.14, t="out_quad").start(self)

    def on_press(self) -> None:
        self.active = not bool(self.active)

