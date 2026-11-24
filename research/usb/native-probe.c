/* Test applet callback, not a substitute for any firmware USB routine. */
#include <stddef.h>
#include "os3k_applet.h"
_Static_assert(sizeof(UsbRequest_t) == 20, "USB request ABI");
_Static_assert(offsetof(UsbRequest_t, input) == 4, "input ABI");
_Static_assert(offsetof(UsbRequest_t, output_capacity) == 8, "capacity ABI");
_Static_assert(offsetof(UsbRequest_t, output_length) == 12, "length ABI");
_Static_assert(offsetof(UsbRequest_t, output) == 16, "output ABI");
_Static_assert(MSG_USB_UNK_07 == MSG_USB_SEND_POLL, "legacy alias");
_Static_assert(MSG_USB_UNK_1E == MSG_USB_KEY_DOWN, "legacy alias");
_Static_assert(MSG_USB_UNK_1F == MSG_USB_KEY_UP, "legacy alias");

void usb_probe_callback(uint32_t message, UsbRequest_t* request, uint32_t* reply)
{
    volatile uint32_t* observed = (volatile uint32_t*)0x74000;
    volatile uint8_t* input_copy = (volatile uint8_t*)0x74020;
    const uint8_t* input = request->input;
    uint8_t* output = request->output;
    observed[0] = message;
    observed[1] = request->input_length;
    observed[2] = (uint32_t)request->input;
    observed[3] = request->output_capacity;
    observed[4] = request->output_length;
    observed[5] = (uint32_t)output;
    for (uint32_t i = 0; i < request->input_length && i < 16; ++i)
        input_copy[i] = input[i];
    /* Includes NUL and non-text bytes; the ROM must not convert this output. */
    for (uint32_t i = 0; i < 16; ++i)
        output[i] = (uint8_t)(i * 17);
    request->output_length = 16;
    *reply = observed[16];
}
