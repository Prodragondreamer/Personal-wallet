from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput

from screens.dashboard import app_data


class AssetScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        layout = BoxLayout(orientation='vertical', spacing=10, padding=10)

        layout.add_widget(Label(text="Asset Entry", font_size=22))

        # Bank input
        layout.add_widget(Label(text="Bank Balance"))
        self.bank_input = TextInput(hint_text="Enter bank amount", multiline=False)
        layout.add_widget(self.bank_input)

        # Stock input
        layout.add_widget(Label(text="Stocks Value"))
        self.stock_input = TextInput(hint_text="Enter stock value", multiline=False)
        layout.add_widget(self.stock_input)

        # Crypto input
        layout.add_widget(Label(text="Crypto Value"))
        self.crypto_input = TextInput(hint_text="Enter crypto value", multiline=False)
        layout.add_widget(self.crypto_input)

        # Save button
        btn_save = Button(text="Save All")
        btn_save.bind(on_press=self.save_data)
        layout.add_widget(btn_save)

        # Back button
        btn_back = Button(text="Back to Dashboard")
        btn_back.bind(on_press=self.go_back)
        layout.add_widget(btn_back)

        self.add_widget(layout)

    def save_data(self, instance):
        try:
            if self.bank_input.text:
                app_data["bank"] = float(self.bank_input.text)

            if self.stock_input.text:
                app_data["stocks"] = float(self.stock_input.text)

            if self.crypto_input.text:
                app_data["crypto"] = float(self.crypto_input.text)

            print("Saved all assets:", app_data)

        except:
            print("Invalid input")

    def go_back(self, instance):
        self.manager.current = "dashboard"