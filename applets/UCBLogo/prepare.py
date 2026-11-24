"""Stage pristine UCBLogo 6.2.5 sources with the OS3K build adaptations.

Source edits select supported primitives, compact nodes, bound evaluation,
and connect text and graphics to the applet runtime. The upstream checkout
stays untouched. Unused platform and tool sources retain their original bytes.

Usage: python3 prepare.py UPSTREAM DESTINATION
Run from this directory so port_config.h resolves beside the Makefile.
"""

import argparse
from pathlib import Path
import re
import subprocess

REVISION = "a0215433f07384e4c42fe247525867f11e6f32f7"
SOURCE_ENCODING = "latin1"
STDIO_SOURCES = {"coms.c", "globals.h", "wrksp.c"}
COMMANDS = set(
    """
    fd forward bk back rt right lt left repeat repcount cs clearscreen
    pu penup pd pendown home print st showturtle ht hideturtle to ct cleartext
    er erase erall erps gc nodes make local if ifelse stop output op thing
    + - * / < = > sum difference product quotient equalp lessp greaterp
    procedures po text setxy setheading
    """.split()
)
PRIMITIVE_ENTRY = re.compile(r'^([ \t]+)\{"([^"]+)".*?\},[^\n]*$', re.M)

TURTLE_OVERLAY = """
/* Toggle the LCD cursor without changing Logo's pen or drawing history. */
extern void neo_cursor_edge(int, int, int, int);

void neo_toggle_turtle(void)
{
    if (!user_turtle_shown)
        return;
    /* Use the release's built-in triangle geometry at LCD scale. */
    FLONUM angle = (90.0 - turtle_heading) * degrad;
    FLONUM dx = sin(angle) * turtle_half_bottom * 0.55;
    FLONUM dy = cos(angle) * turtle_half_bottom * 0.55;
    FLONUM nose = turtle_side * 0.55;
    int left = screen_x_center + g_round(turtle_x - dx);
    int left_y = screen_y_center - g_round(turtle_y + dy);
    int right = screen_x_center + g_round(turtle_x + dx);
    int right_y = screen_y_center - g_round(turtle_y - dy);
    int tip = screen_x_center + g_round(turtle_x + cos(angle) * nose);
    int tip_y = screen_y_center - g_round(turtle_y + sin(angle) * nose);
    neo_cursor_edge(right, right_y, left, left_y);
    neo_cursor_edge(left, left_y, tip, tip_y);
    neo_cursor_edge(tip, tip_y, right, right_y);
}
"""


def replace_once(source, old, new):
    """Fail during staging if a pinned-source edit no longer matches."""
    if source.count(old) != 1:
        raise ValueError(f"Expected one occurrence of {old!r}")
    return source.replace(old, new, 1)


def adapt_header(source):
    """Use smaller pools, buffers, and GC fields; retain full-width type flags."""
    replacements = {
        "#define SEG_SIZE        16000": "#define SEG_SIZE        128",
        "#define MAX_PHYS_LINE   5000": "#define MAX_PHYS_LINE   1024",
        "    int my_gen;": "    short my_gen;",
        "    int gen_age;": "    short gen_age;",
    }
    for old, new in replacements.items():
        source = replace_once(source, old, new)
    return source


def adapt_initialization(source):
    """Register supported primitives and borrow the embedded message strings."""
    source = PRIMITIVE_ENTRY.sub(
        lambda match: match[0] if match[2] in COMMANDS else "", source
    )
    start = source.index('    snprintf(linebuf, 256, "%s%sMessages"')
    end = source.index("\n#define wd_copy", start)
    source = source[:start] + """    char *message = (char *)neo_messages;
    for (i = 0; i < MAX_MESSAGE + NUM_WORDS; ++i) {
        message_texts[i] = message;
        message += strlen(message) + 1;
    }
""" + source[end:]
    return '#include "messages.h"\n' + source


def adapt_math(source):
    """Use port character classification and reject unavailable libm selectors."""
    source = re.sub(r"^#define isdigit\([^\n]+\n", "", source, flags=re.M)
    # These selectors share binary() with supported arithmetic, even though
    # their primitives are disabled. Keeping calls would require desktop libm.
    for expression in (
        "sqrt(fval)",
        "exp(fval)",
        "log10(fval)",
        "log(fval)",
        "atan2(farg,fval)/degrad",
        "atan2(farg,fval)",
        "pow(fval,farg)",
    ):
        source = replace_once(
            source,
            "errchk(fval = " + expression + ");",
            "err_logo(BAD_DATA_UNREC,arg);",
        )
    return source


def adapt_evaluator(source):
    """Check the execution budget for primitive calls and REPEAT iterations."""
    source = replace_once(
        source,
        "val = (*getprimfun(proc))(argl);",
        "val = neo_tick() ? (*getprimfun(proc))(argl) : UNBOUND;",
    )
    source = replace_once(
        source, "if (repcount == 0) {", "if (repcount == 0 || !neo_tick()) {"
    )
    return "extern int neo_tick(void);\n" + source


def adapt_graphics(source):
    """Use LCD drawing history and a separately toggled turtle outline."""
    source = replace_once(
        source, "wraploop:\n", "wraploop:\n    if (!neo_tick()) return;\n"
    )
    source = replace_once(
        source, "BOOLEAN refresh_p = TRUE;", "BOOLEAN refresh_p = FALSE;"
    )
    # The desktop cursor changes pen state and records drawing operations.
    # The applet instead toggles an outline directly on the LCD.
    start = source.index("void draw_turtle(void) {")
    end = source.index("\n}", start) + 2
    source = source[:start] + "void draw_turtle(void) {}" + source[end:]
    return "extern int neo_tick(void);\n" + source + TURTLE_OVERLAY


def adapt_graphics_header(source):
    """Connect the no-window backend to the right-hand 132x64 LCD pane."""
    for old in (
        "#define prepare_to_draw_turtle nop();",
        "#define done_drawing_turtle nop();",
    ):
        source = replace_once(source, old, "")
    replacements = {
        "#define GR_SIZE 1": "#define GR_SIZE 8",
        "#define screen_right 100": "#define screen_right 131",
        "#define screen_top 1": "#define screen_top 0",
        "#define screen_bottom 100": "#define screen_bottom 63",
        "#define clear_screen nop()": "#define clear_screen neo_clear()",
        "#define line_to(x,y) nop()": (
            "#define line_to(x,y) neo_line(x,y,pen_vis,drawing_turtle)"
        ),
        "#define move_to(x,y) nop()": "#define move_to(x,y) neo_move(x,y)",
    }
    for old, new in replacements.items():
        source = replace_once(source, old, new)
    return """void neo_move(int, int);
void neo_line(int, int, int, int);
void neo_clear(void);
""" + source


def adapt_source(name, source):
    """Apply only the edits used by the OS3K build."""
    adapters = {
        "logo.h": adapt_header,
        "init.c": adapt_initialization,
        "math.c": adapt_math,
        "eval.c": adapt_evaluator,
        "graphics.c": adapt_graphics,
        "nographics.h": adapt_graphics_header,
    }
    if name in adapters:
        source = adapters[name](source)
    elif name == "mem.c":
        # Generations range from zero to three; promotion age starts at four.
        # Oldest-generation nodes cannot be promoted, so do not decrement
        # their age indefinitely and overflow the narrowed 16-bit field.
        source = replace_once(
            source,
            "if (--(nd->gen_age) == 0 && loop < NUM_GENS-1)",
            "if (loop < NUM_GENS-1 && --(nd->gen_age) == 0)",
        )
    if name in STDIO_SOURCES:
        source = re.sub(r"\b(fgets|fputc|fputs|putc)\b", r"neo_\1", source)
    return source


def write_messages(upstream, destination):
    """Store the English Messages file as NUL-separated flash strings."""
    lines = (upstream / "logolib/Messages").read_bytes().splitlines()
    data = b"\0".join(line for line in lines if not line.startswith(b";"))
    rows = [
        ", ".join(str(value) for value in data[index:index + 16]) + ","
        for index in range(0, len(data), 16)
    ]
    (destination / "messages.h").write_text(
        "static const unsigned char neo_messages[] = {\n"
        + "\n".join(rows) + "\n0 };\n"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("upstream", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()

    try:
        head = subprocess.check_output(
            ["git", "-C", str(args.upstream), "rev-parse", "HEAD"], text=True
        ).strip()
    except subprocess.CalledProcessError:
        raise SystemExit(
            "Initialize the pinned UCBLogo submodule first. See README.md."
        ) from None
    if head != REVISION:
        raise SystemExit(f"UCBLogo checkout must be at {REVISION}, found {head}")

    args.destination.mkdir(exist_ok=True)
    for path in sorted(args.upstream.iterdir()):
        if path.suffix not in (".c", ".h"):
            continue
        source = path.read_text(encoding=SOURCE_ENCODING)
        adapted = adapt_source(path.name, source)
        target = args.destination / path.name
        if adapted == source:
            target.write_bytes(path.read_bytes())
        else:
            target.write_text(adapted, encoding=SOURCE_ENCODING)

    (args.destination / "config.h").write_bytes(Path("port_config.h").read_bytes())
    write_messages(args.upstream, args.destination)


if __name__ == "__main__":
    main()
