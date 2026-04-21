from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button

class TransactionScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        layout = BoxLayout(orientation='vertical', spacing=10, padding=10)

        layout.add_widget(Label(text="Transaction Preview", font_size=22))

        # Placeholder info (UI first, logic later)
        self.asset_label = Label(text="Asset: ETH")
        self.price_label = Label(text="Price: $0")
        self.amount_label = Label(text="Amount: 0")
        self.gas_label = Label(text="Gas Fee: $0")
        self.total_label = Label(text="Total Cost: $0")

        layout.add_widget(self.asset_label)
        layout.add_widget(self.price_label)
        layout.add_widget(self.amount_label)
        layout.add_widget(self.gas_label)
        layout.add_widget(self.total_label)

        # Warning label (important UI feature)
        self.warning_label = Label(
            text="",
            color=(1, 0, 0, 1)  # red text
        )
        layout.add_widget(self.warning_label)

        # Buttons
        btn_confirm = Button(text="Confirm Transaction")
        layout.add_widget(btn_confirm)

        btn_back = Button(text="Back to Dashboard")
        btn_back.bind(on_press=self.go_back)
        layout.add_widget(btn_back)

        self.add_widget(layout)

    def go_back(self, instance):
        self.manager.current = "dashboard"