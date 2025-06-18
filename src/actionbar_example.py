import logging

from kivy.core.window import Window
from kivy.lang import Builder

if __name__ == "__main__":
    from kivy.base import runTouchApp
    from kivy.uix.floatlayout import FloatLayout
    from kivy.factory import Factory

    # XXX clean the first registration done from '__main__' here.
    # otherwise kivy.uix.actionbar.ActionPrevious != __main__.ActionPrevious
    Factory.unregister('ActionPrevious')

    Builder.load_string('''
<MainScreen>:
    ActionBar:
        id: action_bar
        pos_hint: {'top':1}
        background_color: 0.6, 3.0, 0.2, 1
        ActionView:
            use_separator: True
            ActionPrevious:
                title: 'Action Bar'
                with_previous: False
            ActionOverflow:
            ActionButton:
                text: 'Btn0'
                #icon: 'atlas://data/images/defaulttheme/audio-volume-high'
                background_normal: ""
                background_color: 0.6, 4.0, 0.2, 1
                draggable: False

            ActionSeparator:
                background_normal: ""
                background_color: 0.0, 0.0, 0.2, 1

            ActionButton:
                text: 'Btn1'
                background_normal: ""
                background_color: 0.6, 4.0, 0.2, 1
                draggable: False
            ActionButton:
                text: 'Btn2'
                background_normal: ""
                background_color: 0.6, 4.0, 0.2, 1
                draggable: False
            ActionGroup:
                text: 'Group 1'
                background_normal: ""
                background_color: 0.6, 4.0, 0.2, 1
                draggable: False
                ActionButton:
                    text: 'Btn3'
                ActionButton:
                    text: 'Btn4'
            ActionGroup:
                draggable: False
                dropdown_width: 200
                text: 'Group 2'
                ActionButton:
                    text: 'Btn5'
                ActionButton:
                    text: 'Btn6'
                ActionButton:
                    text: 'Btn7'
''')

    class MainScreen(FloatLayout):
        pass

    float_layout = MainScreen()

    Window.custom_titlebar = True
    title_bar = float_layout.ids.action_bar
    if Window.set_custom_titlebar(title_bar):
        logging.info("Window: setting custom titlebar successful")
    else:
        logging.info("Window: setting custom titlebar " "Not allowed on this system ")

    runTouchApp(float_layout)
