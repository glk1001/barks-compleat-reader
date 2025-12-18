import re
import sys

from pathlib import Path

from pandas.core.computation.ops import isnumeric
from spellchecker import SpellChecker


def is_number(s):
    try:
        float(s)
        return True
    except ValueError:
        return False


spell = SpellChecker()

WRITE = True

in_dir = Path(sys.argv[1])

for ocr_dir in in_dir.iterdir():
    for file in ocr_dir.glob('*.json'):
        with file.open('r') as f:
            lines = f.readlines()

        changed = False
        changed_lines = []
        for line in lines:
            ln = line
            show = False
            # match = re.findall(r'\w+-\\n\w+', line)
            # if match:
            #     for m in match:
            #         joined_word = m.replace(r'-\n', '')
            #         if not spell.unknown([joined_word]) and not is_number(joined_word):
            #             show = True
            #             print("replace")
            #             word = m.replace('-', '\\u00AD')
            #             ln = line.replace(m, word, 1)
            #         else:
            #             word = m
            if r'\u2014  ' in ln:
                show = True
                #ln = re.sub(r'\w+(?:-\w+)+', '', line)
#                ln = line.replace(r'--\n', ' \\u2014\\n')
#                ln = line.replace(r'--"', ' \\u2014"')
#                ln = line.replace(r'\u2014-', '\\u2014')
#                ln = line.replace(r'--', ' \\u2014 ')
#                ln = line.replace(r' -\n', ' \\u2014\\n')
#                ln = line.replace(r' - ', ' \\u2014 ')
#                ln = line.replace(r'\u2013', '\\u2014 ')
#                ln = line.replace(r'O.R. ST. B', 'O.R.ST.B')
                ln = line.replace(r'\u2014  ', '\\u2014 ')
                changed = True
            if show:
                print(file)
                # print("match: ", match)
                # print("word: ", word)
                print(line.removesuffix('\n'))
                print(ln.removesuffix('\n'))
            changed_lines.append(ln)

        if WRITE and changed:
            with file.open('w') as f:
                for line in changed_lines:
                    f.write(line)
