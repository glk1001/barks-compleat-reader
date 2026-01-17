from kivy.app import App
from kivy.uix.label import Label
from kivy.lang import Builder
import pyphen

# Initialize Pyphen
dic = pyphen.Pyphen(lang='en_US')

def smart_wrap_text(text):
    words = text.split(' ')
    processed_words = []

    # The Zero Width Space character
    zwsp = u'\u200b'

    for word in words:
        # Pyphen normally inserts a soft hyphen (\xad).
        # We tell it to use the Zero Width Space instead.
        # This tells Kivy "You are allowed to break the line here"
        # without rendering a visible symbol or a "missing box".
        split_word = dic.inserted(word, hyphen=zwsp)
        processed_words.append(split_word)

    return ' '.join(processed_words)

kv = """
BoxLayout:
    orientation: 'vertical'
    padding: 50
    spacing: 20

    Label:
        text: "Without Hyphenation (Big Gaps):"
        size_hint_y: None
        height: 30
        color: 1, 0.5, 0.5, 1

    Label:
        text_size: self.width, None
        halign: 'justify'
        valign: 'top'
        font_size: '18sp'
        text: 
            "Electroencephalography is a monitoring method to record " + \
            "electrical activity of the brain. " + \
            "Otorhinolaryngologist is a surgical subspecialty within " + \
            "medicine that deals with conditions of the ear, nose, and throat."

    Label:
        text: "With Zero-Width Space Injection (Clean):"
        size_hint_y: None
        height: 30
        color: 0.5, 1, 0.5, 1

    Label:
        id: improved_label
        text_size: self.width, None
        halign: 'justify'
        valign: 'top'
        font_size: '18sp'
"""

class HyphenApp(App):
    def build(self):
        app = Builder.load_string(kv)

        raw_text = (
                "Electroencephalography is a monitoring method to record "
                "electrical activity of the brain. "
                "Otorhinolaryngologist is a surgical subspecialty within "
                "medicine that deals with conditions of the ear, nose, and throat."
        )

        # Apply the processing
        processed_text = smart_wrap_text(raw_text)

        app.ids.improved_label.text = processed_text
        return app

if __name__ == '__main__':
    HyphenApp().run()
