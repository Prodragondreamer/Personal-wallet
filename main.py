from kivy.app import App
from kivy.uix.screenmanager import ScreenManager
from kivy.core.window import Window

from screens.dashboard import DashboardScreen
from screens.asset import AssetScreen
from screens.transaction import TransactionScreen

Window.size = (360, 640)

class MyApp(App):
    def build(self):
        sm = ScreenManager()

        sm.add_widget(DashboardScreen(name='dashboard'))
        sm.add_widget(AssetScreen(name='asset'))
        sm.add_widget(TransactionScreen(name='transaction'))

        return sm

if __name__ == "__main__":
    MyApp().run()