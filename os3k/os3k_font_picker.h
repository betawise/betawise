#ifndef OS3K_FONT_PICKER_H
#define OS3K_FONT_PICKER_H
#include <stdbool.h>
#include <stdint.h>

/** @file os3k_font_picker.h
 * Neo proportional font picker. One active picker per applet.
 * Begin supplies an installed-font name/filter callback, then Open draws it.
 * Route navigation to Move/Edge, redraw requests to Redraw, and call Close on
 * acceptance, cancellation or loss of focus. Choice returns a transient handle.
 * Drawing does not change the global font preference or apply editor fonts.
 */
/* Modal handles only. Zero and 32 are built-in selections; all other valid
 * handles are installed indices 1–31. Persist a selection kind/provider ID. */
#define FONT_PICKER_SYSTEM_SMALL 32
typedef struct {
    uint16_t choice, top;
    uint8_t target_lines, row;
} FontPickerState;
typedef bool (*FontPickerReadName)(unsigned index, char name[37]);
extern FontPickerState g_font_picker;
void FontPickerBegin(FontPickerReadName read_name, uint16_t current);
void FontPickerMove(int family_direction, int size_direction);
void FontPickerEdge(bool last);
bool FontPickerCanResize(int direction);
uint16_t FontPickerChoice(void);
bool FontPickerOpen(void);
void FontPickerDraw(void);
void FontPickerRedraw(void);
void FontPickerClose(void);
#endif
