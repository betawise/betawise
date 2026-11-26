"""Skip closing formatting records until the requested numbered verse."""
from linear_boundaries import generate as generate_linear


def generate(here):
    text = generate_linear(here).read_text()
    text = text.replace('            verse = number;', '            verse = number;\n            if(!by_position) in_heading = false;')
    text = text.replace('            while(cursor < limit && *cursor != VERSE_FONT_BEGIN && *cursor != VERSE_FONT_END) ++cursor;', '''            if(!by_position && verse < target) {
                while(cursor < limit && *cursor != VERSE_FONT_BEGIN) ++cursor;
            } else {
                while(cursor < limit && *cursor != VERSE_FONT_BEGIN && *cursor != VERSE_FONT_END) ++cursor;
            }''')
    output = here / 'build/lean-boundaries.h'
    output.write_text(text)
    return output
