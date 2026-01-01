from PIL import Image, ImageDraw, ImageFont

def save_char_image(font_path, text: str, output_name):
    img = Image.new('RGB', (1000, 1000), color='white')
    draw = ImageDraw.Draw(img)

    # Load the font at a specific size
    font = ImageFont.truetype(font_path, 60)

    draw.text((20, 10), text, font=font, fill='black')
    img.save(output_name)


font_file = "/home/greg/Prj/github/barks-compleat-digital/barks-compleat-reader/src/barks-fantagraphics/data/fonts/Carl Barks Script-1.ttf"
save_char_image(font_file, "Currency test: $98.00", "/tmp/carl-barks-font-test.png")

