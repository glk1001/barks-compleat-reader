from kivy.app import App
from kivy.uix.label import Label
from kivy.lang import Builder
import pyphen

# Initialize Pyphen
dic = pyphen.Pyphen(lang='en_US')

def cross_platform_wrap(text):
    words = text.split(' ')
    processed_words = []

    # The Magic Trick:
    # 1. A space allows Kivy to wrap the line.
    # 2. [size=0] makes the space invisible and 0 width.
    # 3. [color=00000000] is a backup to ensure it's fully transparent.
    invisible_break = "[size=0][color=00000000] [/color][/size]"

    for word in words:
        # Pyphen finds the syllable breaks
        # We replace the potential break point with our invisible markup space
        split_word = dic.inserted(word, hyphen=invisible_break)
        processed_words.append(split_word)

    return ' '.join(processed_words)

kv = """
BoxLayout:
    orientation: 'vertical'
    padding: 80
    spacing: 20
    canvas.before:
        Color:
            rgba: 0.2, 0.2, 0.2, 1
        Rectangle:
            pos: self.pos
            size: self.size

    Label:
        text: "Standard Justify (Ugly Gaps):"
        size_hint_y: None
        height: 40
        font_size: '16sp'
        color: 1, 0.5, 0.5, 1

    Label:
        text_size: self.width, None
        halign: 'justify'
        valign: 'top'
        font_size: '20sp'
        text: 
            "Electroencephalography is a monitoring method to record " + \
            "electrical activity of the brain. " + \
            "Otorhinolaryngologist is a surgical subspecialty within " + \
            "medicine that deals with conditions of the ear, nose, and throat."

    Label:
        text: "Cross-Platform Split (Clean):"
        size_hint_y: None
        height: 40
        font_size: '16sp'
        color: 0.5, 1, 0.5, 1

    Label:
        id: smart_label
        text_size: self.width, None
        halign: 'justify'
        valign: 'top'
        font_size: '20sp'
        markup: True  # <--- CRITICAL for this to work
"""

class MainApp(App):
    def build(self):
        app = Builder.load_string(kv)

        raw_text = (
                "Electroencephalography is a monitoring method to record "
                "electrical activity of the brain. "
                "Otorhinolaryngologist is a surgical subspecialty within "
                "medicine that deals with conditions of the ear, nose, and throat."
        )

        # Apply the wrapper
        app.ids.smart_label.text = cross_platform_wrap(raw_text)

        return app

if __name__ == '__main__':
    MainApp().run()
