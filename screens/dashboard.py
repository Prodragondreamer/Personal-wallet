from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button

# Shared data (temporary simple solution)
app_data = {
    "bank": 0,
    "stocks": 0,
    "crypto": 0
}

class DashboardScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.layout = BoxLayout(orientation='vertical', spacing=10, padding=10)

        self.balance_label = Label(font_size=24)
        self.bank_label = Label()
        self.stock_label = Label()
        self.crypto_label = Label()

        self.layout.add_widget(self.balance_label)
        self.layout.add_widget(self.bank_label)
        self.layout.add_widget(self.stock_label)
        self.layout.add_widget(self.crypto_label)

        btn_asset = Button(text="Add Asset")
        btn_asset.bind(on_press=self.go_to_asset)
        self.layout.add_widget(btn_asset)

        btn_tx = Button(text="Preview Transaction")
        btn_tx.bind(on_press=self.go_to_transaction)
        self.layout.add_widget(btn_tx)

        btn_kill = Button(text="KILL SWITCH", background_color=(1, 0, 0, 1))
        btn_kill.bind(on_press=self.kill_switch)
        self.layout.add_widget(btn_kill)

        self.add_widget(self.layout)

        self.update_labels()

    def update_labels(self):
        total = app_data["bank"] + app_data["stocks"] + app_data["crypto"]

        self.balance_label.text = f"Total Net Worth: ${total}"
        self.bank_label.text = f"Bank: ${app_data['bank']}"
        self.stock_label.text = f"Stocks: ${app_data['stocks']}"
        self.crypto_label.text = f"Crypto: ${app_data['crypto']}"

    def on_enter(self):
        self.update_labels()

    def go_to_asset(self, instance):
        self.manager.current = "asset"

    def go_to_transaction(self, instance):
        self.manager.current = "transaction"

    def kill_switch(self, instance):
        print("Kill switch activated!")

    