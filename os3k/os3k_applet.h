#ifndef _OS3K_APPLET_H_
#define _OS3K_APPLET_H_

/** @file os3k_applet.h
 * @brief Applet messages, metadata, and entry points.
 */

#include <stdbool.h>
#include <stdint.h>

/** @brief Message codes delivered to the applet entry point.
 *
 * The entry point returns void. Use the status output for the reply requested
 * by the message. Write zero for ordinary events handled without a special
 * reply. The status word can contain a previous value on entry.
 * USB payloads are opaque unless their message entry specifies a contract.
 */
typedef enum _Message_e {
    MSG_IDLE            = 0x00, /**< Idle notification. Foreground param is normally zero; battery diagnostic callbacks use 0xFEDCBA98. Reply zero for ordinary handling. */
    MSG_PRINT_SETUP_FAILED = 0x0E, /**< Print-driver setup failed; param is zero. Native print path notifies the foreground applet. */
    MSG_INIT            = 0x18, /**< Initialize applet state. Native launch passed param zero. Reply zero for ordinary handling. */
    MSG_SETFOCUS        = 0x19, /**< Applet gains focus. param is an opaque launch value. Reply zero for ordinary handling. */
    MSG_KILLFOCUS       = 0x1A, /**< Applet loses focus. param is zero. Reply zero for ordinary handling. */
    MSG_REFRESH         = 0x1B, /**< Redraw/update notification, not exclusively a font event. param: MessageRefreshParam_e (Neo 3.21); ordinary redraw uses zero. */
    MSG_SETTINGS_READ   = 0x1C, /**< Read applet settings/resource record through a borrowed native request at param. Reply/request layout is workflow-specific; see message research. No synthetic flag is added. */
    MSG_SETTINGS_WRITE  = 0x1D, /**< Apply applet settings/resource record through a borrowed native request at param. No synthetic flag is added. */
    MSG_CHAR            = 0x20, /**< param is a translated character byte, zero-extended. Reply zero for ordinary handling. */
    MSG_KEY             = 0x21, /**< param is a zero-extended 16-bit keyboard event word. Reply zero for ordinary handling. */
    MSG_REFRESH_LEGACY  = 0x24, /**< Legacy refresh accepted by Inspiration; no producer identified in the three inventoried ROMs. Parameter meaning unresolved. */
    MSG_LOW_BATTERY      = 0x25, /**< Foreground notification after the native low-battery warning. No new payload is initialized; do not interpret param. */
    MSG_GET_ID           = 0x26, /**< Query applet identity: param is zero; write the 16-bit applet header ID, zero-extended, to status. Used for RAM-loaded applet registration. */
    /* AS3000 keyboard transports. param is a borrowed 20-byte native request
     * with five 32-bit fields (see dispatch audit); reply handling differs by transport.
     * Control events may go only to the ROM's selected protocol handler.
     */
    MSG_ADB_OPEN         = 0x10001, /**< ADB session open; no input. Replies 0x11/0x12 suppress attachment text. */
    MSG_ADB_RECEIVE      = 0x10002, /**< Host-command bytes; routed to the selected ADB protocol handler. */
    MSG_ADB_UNK_03       = 0x10003, /**< ADB pump event 03; producer known, detailed control semantics unresolved. */
    MSG_ADB_UNK_04       = 0x10004, /**< ADB pump event 04; selected protocol handler receives a native request. */
    MSG_ADB_SEND_POLL    = 0x10006, /**< Protocol output poll. Reply 4 supplies raw ADB output bytes. */
    MSG_ADB_TEXT_POLL    = 0x10007, /**< Keyboard text queue needs data; reply 6 converts supplied text to ADB key bytes. */
    MSG_ADB_TEXT_DRAINED = 0x10008, /**< Keyboard text queue drained; may supply more text. */
    MSG_ADB_CLOSE        = 0x1000C, /**< ADB session close notification. */
    MSG_ADB_UNK_16       = 0x10016, /**< ADB pump control event 16; semantics unresolved. */
    MSG_ADB_UNK_17       = 0x10017, /**< ADB pump control event 17; semantics unresolved. */
    MSG_ADB_KEY_DOWN     = 0x1001E, /**< Input points to a native 16-bit key word. Reply 3 supplies native keys; reply 6 supplies text. */
    MSG_ADB_KEY_UP       = 0x1001F, /**< Native key-up word. Same native-request layout as key-down. */
    MSG_ADB_KEY_DOWN_BUSY = 0x1011E, /**< Native key-down with queued ADB output; do not mask off the busy bits. */
    MSG_ADB_KEY_UP_BUSY  = 0x1011F, /**< Native key-up with queued ADB output. */
    MSG_PS2_OPEN         = 0x20001, /**< PS/2 session open; no input. Replies 0x11/0x12 suppress attachment text. */
    MSG_PS2_RECEIVE      = 0x20002, /**< Host-command byte(s); routed to the selected PS/2 protocol handler. */
    MSG_PS2_SEND_POLL    = 0x20006, /**< Selected PS/2 protocol handler output poll. */
    MSG_PS2_TEXT_POLL    = 0x20007, /**< Keyboard text queue needs more data; reply 6 supplies text for native conversion. */
    MSG_PS2_TEXT_DRAINED = 0x20008, /**< Keyboard text queue drained. */
    MSG_PS2_CLOSE        = 0x2000C, /**< PS/2 session close. */
    MSG_PS2_UNK_14       = 0x20014, /**< PS/2 control-state notification; exact host-command meaning unresolved. */
    MSG_PS2_UNK_15       = 0x20015, /**< PS/2 control-state notification; exact host-command meaning unresolved. */
    MSG_PS2_KEY_DOWN     = 0x2001E, /**< Input points to a native 16-bit key word. */
    MSG_PS2_KEY_UP       = 0x2001F, /**< Native key-up word. */
    MSG_PS2_KEY_DOWN_BUSY = 0x2011E, /**< Native key-down while PS/2 output is queued (AS3000 pump 4D277A–4D2788). */
    MSG_PS2_KEY_UP_BUSY  = 0x2011F, /**< Native key-up while PS/2 output is queued. */
    MSG_USB_PLUG        = 0x30001, /**< USB attach. param points to a ROM USB request block. The ROM checks the reply. */
    MSG_USB_UNK_07      = 0x30007, /**< USB event. param points to a USB request block. The request and reply are opaque. */
    MSG_USB_UNPLUG      = 0x3000C, /**< USB detach. param points to a USB request block. No reply is required by this notification. */
    MSG_USB_UNK_1E      = 0x3001E, /**< USB transfer event. Payload and reply are opaque. */
    MSG_USB_UNK_1F      = 0x3001F, /**< USB transfer event. Payload and reply are opaque. */
    MSG_HUB_OPEN         = 0x50001, /**< AlphaHub connection/session open. param is a native 20-byte transfer request. */
    MSG_HUB_RECEIVE      = 0x50002, /**< AlphaHub input bytes; reply 4 supplies output_length bytes. */
    MSG_HUB_RECEIVE_CONTINUATION = 0x50005, /**< AlphaHub additional input callback; not USB direct-send reply 5. */
    MSG_HUB_SEND_POLL    = 0x50006, /**< AlphaHub output queue empty; capacity 1020 in the traced Neo 3.21 path. Reply 4 supplies bytes. */
    MSG_HUB_UNK_09       = 0x50009, /**< AlphaHub pump control event 09, empty request; detailed cause unresolved. */
    MSG_HUB_UNK_0A       = 0x5000A, /**< AlphaHub pump control event 0A after packet-state processing, empty request. */
    MSG_HUB_CLOSE        = 0x5000C, /**< AlphaHub close notification; input/output capacity zero. */
    MSG_TRANSFER_OPEN   = 0x60001, /**< Native text-transfer open: request at param; copies a name capped at 39 characters, enters phase 6, replies 0x11. See text/USB research for scoped payload contract. */
    MSG_TRANSFER_CLOSE  = 0x6000C, /**< Native text-transfer close: editor transfer handler enters phase 10. Payload/replies remain workflow-specific. */
    MSG_TRANSFER_READ   = 0x6000D, /**< Printer requests another text chunk; native request at param, capacity up to 1024. Reply 4 supplies output_length bytes. */
    MSG_TRANSFER_WAIT   = 0x60010, /**< Printer write has stalled/lasted long enough for progress UI. param is zero; reply 8 cancels in the traced path. */
    MSG_TRANSFER_CONTINUE = 0x60011, /**< Printer wait ended; param is zero. Distinct from TRANSFER_READ. */
    MSG_TRANSFER_CHAR   = 0x60020, /**< Native text-transfer character request; input points to a native 16-bit key. Escape enters phase 8 and replies 8. */
    MSG_IRDA_OPEN        = 0x70001, /**< IrDA application-transfer session open. param is a native transfer request; selected handler may reply with data. */
    MSG_IRDA_RECEIVE     = 0x70002, /**< IrDA application payload; native transfer request, not a raw IrLAP frame. */
    MSG_IRDA_SEND_POLL   = 0x70006, /**< IrDA output poll; reply 4 supplies output_length bytes. */
    MSG_IRDA_CLOSE       = 0x7000C, /**< IrDA application-transfer close; param may be NULL. */
    MSG_IRDA_KEY         = 0x70020, /**< Input points to a native 16-bit key word; reply 0x10 cancels in the default Escape handler. */
    /* Scoped to Neo font-provider applets: other providers reuse these codes.
     * param is writable pointer storage for queries 1–5, uint32_t for query 6.
     * AppletSendMessage also accepts the corresponding low codes 1 through 6.
     */
    MSG_FONT_GET_NAME   = 0x1000001, /**< Write a borrowed const char* display name through param. */
    MSG_FONT_GET_NORMAL = 0x1000002, /**< Write a borrowed FontHeader_t* for font slot 0 through param. */
    MSG_FONT_GET_BOLD   = 0x1000003, /**< Write font slot 1, or NULL to use the normal face. */
    MSG_FONT_GET_ITALIC = 0x1000004, /**< Write font slot 2, or NULL to use the normal face. */
    MSG_FONT_GET_BOLD_ITALIC = 0x1000005, /**< Write font slot 3, or NULL to use the bold face. */
    MSG_FONT_GET_HEIGHT = 0x1000006, /**< Write the pixel height as a uint32_t through param, not a FontHeader_t*. Stock Neo providers also initialize their descriptor and zero-extend its height byte; BetaWiseTerminal initializes via MSG_INIT. */
    MSG_FONT_INITIALIZE = MSG_FONT_GET_HEIGHT, /**< Compatibility name; the output is a scalar height. */
    /* Other providers intentionally reuse font-query numbers. These aliases
     * are scoped protocol selectors, not universal meanings of low codes.
     */
    MSG_COWRITER_REQUEST_0 = 0x1000000, /**< CoWriter session/setup request; status points to a packed result record, not just a uint32_t. */
    MSG_COWRITER_REQUEST_1 = 0x1000001, /**< CoWriter request 1; see scoped payload/result mapping in message research. */
    MSG_COWRITER_REQUEST_2 = 0x1000002, /**< CoWriter request 2; scoped packed result record. */
    MSG_COWRITER_KEY       = 0x1000003, /**< CoWriter native-key request; param is a key word, status is its packed result record. */
    MSG_COWRITER_REQUEST_4 = 0x1000004, /**< CoWriter request 4; scoped packed result record. */
    MSG_COWRITER_REQUEST_5 = 0x1000005, /**< CoWriter request 5; scoped packed result record. */
    MSG_DICTIONARY_GET_DATA = 0x1000001, /**< CW_Topics/CW_MainDictionary: param points to output data pointer; status requires 8 writable bytes (zero uint32_t followed by data pointer). */
    /* Thesaurus payload layouts: research/dictionaries/README.md. */
    MSG_THESAURUS_FIND_GROUPS = 0x1000000,
    MSG_THESAURUS_GET_GROUP = 0x1000001,
    MSG_THESAURUS_GET_GROUP_COUNT = 0x1000002,
    MSG_THESAURUS_GET_HEADWORD = 0x1000003,
    MSG_THESAURUS_GET_WORD_CLASS = 0x1000004,
    MSG_THESAURUS_GET_RELATED_WORDS = 0x1000005,
    MSG_THESAURUS_GET_ANTONYM_GROUP = 0x1000006,
    /* SpellCheck uses a distinct five-field request; selector 0 is unsupported.
     * Operations 2 and 4 remain unresolved and are intentionally unnamed.
     */
    MSG_SPELLCHECK_CHECK = 0x1000001,
    MSG_SPELLCHECK_INTERACTIVE = 0x1000003,
    MSG_SPELLCHECK_ENABLE = 0x1000005,
    MSG_SPELLCHECK_DISABLE = 0x1000006,
    MSG_SPELLCHECK_GET_ENABLED = 0x1000007,
    MSG_STYLEWRITER_QUERY = 0x1A01000, /**< SWFont: low byte of param indexes 256 relative offsets; status receives the selected borrowed ROM address. */
    /* Source-compatible names retained for existing callers. */
    MSG_MOD_SYNTHETIC   = 0x1000000 /**< Dispatch flag applied by AppletSendMessage() to most messages. */
} Message_e;

/** @brief Parameters of MSG_REFRESH, traced on Neo 3.21.
 *
 * These are scalar reason codes, not message IDs, pointers, or font indices.
 * Unknown values must not be assumed to mean a font change. Font selection
 * can notify even when no different face was committed. See
 * research/syscalls/applet/messages.md for producers and handler behavior.
 */
typedef enum _MessageRefreshParam_e {
    MSG_REFRESH_REDRAW = 0x00, /**< Ordinary redraw after firmware UI/activity. */
    MSG_REFRESH_FONTS = 0xFC, /**< Reload the four current font pointers and reconcile layout. */
    MSG_REFRESH_CURSOR_STYLE = 0xFE /**< Refresh the applet's saved native cursor-style setting and redraw. */
} MessageRefreshParam_e;

/** @brief Applet-provided message handler.
 * @param message Message code, possibly including a dispatch flag.
 * @param param Message-specific value or target address.
 * @param status Message-specific reply storage supplied by the caller. Most
 * protocols use a uint32_t; CoWriter/dictionary services require larger packed
 * result records despite this historical signature. See message research.
 */
void ProcessMessage(Message_e message, uint32_t param, uint32_t* status);

/** @brief Select the applet identity reported by AppletGetContextId().
 *
 * Updates a separate ROM identity
 * context only when the indexed applet's dispatch/status word is zero.
 * A nonzero status word rejects the request and preserves the previous
 * identity. Selection does not launch the applet, switch its A5 data base,
 * change the foreground applet, or select its file folder.
 *
 * The ROM performs no index bounds or descriptor-presence checks here.
 * AppletGetContextId() subsequently dereferences the selected descriptor.
 * @param index Installed applet's table index, from 0 through 31. Index zero
 * selects the system applet. The caller must ensure the descriptor exists.
 * @return The supplied index on success, or zero when the status word is
 * nonzero. Successful selection of index zero also returns zero.
 */
uint32_t AppletSelectContext(uint32_t index);

/** @brief Clear the ROM's applet identity context.
 *
 * Marks the identity context as unset
 * using the ROM's internal -1 sentinel. AppletGetContextId() then returns
 * zero. This clears the identity without closing or unloading an applet.
 */
void AppletClearContext(void);

/** @brief Read the header ID of the applet selected as the identity context.
 *
 * Reads the 16-bit id member at offset
 * 0x14 of the selected applet's header. This is an ID, not a table index,
 * and is independent of the foreground/executing applet. The ROM itself
 * also sets and clears this identity during applet lifecycle transitions.
 * A selected descriptor must remain valid until the context is changed or
 * cleared; the getter does not check for a missing descriptor.
 * @return The selected applet's 16-bit header ID, or zero when the context
 * is unset. A selected applet whose header ID is zero also returns zero.
 */
uint16_t AppletGetContextId(void);

/** @brief Find an installed applet by a case-sensitive name prefix.
 * @param name NUL-terminated prefix to compare.
 * @param start_index Search begins at the index after this value.
 * @return The matching index, or zero if no applet matches.
 */
uint32_t AppletFindByName(const char* name, uint32_t start_index);

/** @brief Find an installed applet by its header ID.
 * Search stops at the first empty descriptor in the installed applet table.
 * @param id 16-bit applet identifier.
 * @return The matching index, or zero for no match or the system applet.
 */
uint32_t AppletFindById(uint16_t id);

/** @brief Copy an installed applet's display name.
 * @param index Nonzero applet index.
 * @param name Writable buffer of at least 37 bytes.
 * @return True on success. On failure the destination is left untouched.
 */
bool AppletGetName(uint32_t index, char* name);

/** @brief Dispatch a message synchronously to another installed applet.
 *
 * The ROM installs the target's A5 context and
 * restores the caller's context afterward. It sets MSG_MOD_SYNTHETIC on
 * the low 24-bit message code except for codes 0x1C and 0x1D.
 * @param index Nonzero target applet index.
 * @param message Message code to dispatch.
 * @param param Value forwarded to the applet.
 * @param status Reply address forwarded to the applet. It must satisfy the message contract.
 * @return True if the callback ran.
 */
bool AppletSendMessage(uint32_t index, Message_e message, uint32_t param, uint32_t* status);

/** @brief Betawise ROM entry point. Initializes applet RAM on MSG_INIT.
 * @param message ROM message code.
 * @param param Message-specific input.
 * @param status Message-specific reply word.
 */
void Os3kEntry(Message_e message, uint32_t param, uint32_t* status);

/** @brief Apply Betawise lifecycle handling and forward the message to ProcessMessage().
 * @param message ROM message code.
 * @param param Message-specific input.
 * @param status Message-specific reply word.
 */
void BwProcessMessage(Message_e message, uint32_t param, uint32_t* status);

/** @brief On-flash applet header.
 *
 * The m68k layout is 0x94 bytes and uses big-endian integers. The applet
 * image is addressed relative to this header. Betawise's linker places it
 * before the RAM initialization and code images, and places the footer
 * magic at the end of the flash image.
 */
typedef struct _AppletHeader_t {
    uint32_t signature; /**< 0x00, image marker 0xC0FFEEAD. */
    uint32_t romUsage; /**< 0x04, total image size including the header and footer. */
    uint32_t ramUsage; /**< 0x08, applet RAM request in bytes, including zero-initialized storage. */
    uint32_t settingsOffset; /**< 0x0C, applet-relative resource-stream offset, consumed by AppletGetResources(). Betawise defaults to zero. */
    uint32_t flags; /**< 0x10, applet flags word. Betawise supplies 0xFF in the high byte. */
    uint16_t id; /**< 0x14, applet identifier used by AppletFindById() and AppletGetContextId(). */
    uint8_t headerVersion; /**< 0x16, header format version. Betawise emits version 1. */
    uint8_t fileCount; /**< 0x17, number of files requested in the applet folder. */
    char name[36]; /**< 0x18, fixed-width display name. A full-width name can omit the terminator. */
    /** @brief Three-byte applet version. */
    struct _Version_t {
        uint8_t versionMajor; /**< 0x3C, applet major version. */
        uint8_t versionMinor; /**< 0x3D, applet minor version. */
        char versionRevision[1]; /**< 0x3E, single revision character. */
    } version; /**< 0x3C, applet version fields. */
    uint8_t languageId; /**< 0x3F, applet language identifier. */
    char info[60]; /**< 0x40, fixed-width applet information text. */
    uint32_t minAsmVersion; /**< 0x7C, minimum AlphaSmart Manager version field. Betawise defaults to zero. */
    uint32_t fileUsage; /**< 0x80, applet file storage request field. Betawise defaults to zero. */
    void* entryPoint; /**< 0x84, ROM-relative callback offset. The ROM adds the header address before dispatch. */
    uint32_t magic[3]; /**< 0x88, reserved trailing words; preserve the Betawise initializer. */
} AppletHeader_t;

/** @brief Display name suffix in a Neo font applet header. */
#define APPLET_FONT_NAME_PTR (&__header.name[11])

/** @brief Absolute linker symbol whose address encodes the flash image size. */
extern char __os3k_rom_size;
/** @brief Absolute linker symbol whose address encodes the applet RAM size. */
extern char __os3k_ram_size;

/** @brief Begin the applet header initializer with Betawise defaults. */
#define APPLET_HEADER_BEGIN \
    const AppletHeader_t __header __attribute__ ((section("os3k_header"))) = { \
        .signature = 0xC0FFEEAD, \
        .romUsage = (uint32_t)&__os3k_rom_size, \
        .ramUsage = (uint32_t)&__os3k_ram_size, \
        .settingsOffset = 0, \
        .flags = 0xFF000000, \
        .headerVersion = 1, \
        .fileCount = 0, \
        .name = "Test", \
        .minAsmVersion = 0, \
        .fileUsage = 0, \
        .entryPoint = &Os3kEntry, \
        .magic = {0, 1, 2},
/** @brief Supply applet capabilities in the header flags word. */
#define APPLET_FLAGS(param) .flags = 0xFF000000 | (param),
/** @brief Supply the 16-bit applet identifier. */
#define APPLET_ID(param) .id = param,
/** @brief Supply the applet display name. */
#define APPLET_NAME(param) .name = param,
/** @brief Supply a Neo font name with the firmware prefix. */
#define APPLET_FONT_NAME(param) .name = "Neo Font - " param,
/** @brief Supply applet information text. */
#define APPLET_INFO(param) .info = param,
/** @brief Supply the major, minor, and revision fields. */
#define APPLET_VERSION(major, minor, revision) .version = {major, minor, revision},
/** @brief Set the applet language to English (United States). */
#define APPLET_LANGUAGE_EN_US .languageId = 1,
/** @brief Set the applet language to English (United Kingdom). */
#define APPLET_LANGUAGE_EN_UK .languageId = 2,
/** @brief Set the applet language to French. */
#define APPLET_LANGUAGE_FR .languageId = 3,
/** @brief Set the applet language to French (Canada). */
#define APPLET_LANGUAGE_FR_CR .languageId = 4,
/** @brief Set the applet language to Italian. */
#define APPLET_LANGUAGE_IT .languageId = 5,
/** @brief Set the applet language to German. */
#define APPLET_LANGUAGE_DE .languageId = 6,
/** @brief Set the applet language to Spanish. */
#define APPLET_LANGUAGE_ES .languageId = 7,
/** @brief Set the applet language to Dutch. */
#define APPLET_LANGUAGE_NL .languageId = 8,
/** @brief Set the applet language to Swedish. */
#define APPLET_LANGUAGE_SV .languageId = 9,
/** @brief End the header initializer and emit the flash image footer. */
#define APPLET_HEADER_END \
    }; \
    const uint32_t __footer __attribute__ ((section("os3k_footer"))) = { 0xCAFEFEED }; \

/** @brief Hide the applet from the regular applet list. */
#define APPLET_FLAG_HIDDEN 0x001
/** @brief Identify an applet as a font provider. */
#define APPLET_FLAG_FONT (0x010 | 0x020)
/** @brief Advertise support for the font selection dialog. */
#define APPLET_FLAG_ALLOW_FONT_DIALOG 0x080
/** @brief Mark the applet as requiring wireless support. */
#define APPLET_FLAG_WIRELESS_REQUIRED 0x100

/** @brief Read an applet's disable/context-lock mask.
 *
 * Bit zero is the system disable flag. Other bits identify applet contexts
 * that have registered a context lock. A nonzero mask blocks AppletSelectContext().
 * @param index Existing installed applet table index 0–31; unchecked by the ROM.
 * @return Complete 32-bit mask.
 */
uint32_t AppletGetDisableMask(uint32_t index);

/** @brief Set the system disable bit without clearing context locks.
 * @param index Existing applet table index 0–31; unchecked.
 */
void AppletDisable(uint32_t index);

/** @brief Clear all disable and context-lock bits.
 * @param index Existing applet table index 0–31; unchecked.
 */
void AppletClearDisableMask(uint32_t index);

/** @brief Add the current identity-context bit to an applet mask.
 *
 * Uses AppletSelectContext()'s identity, not a caller-supplied source index.
 * The current identity must be valid and from 0–31. Context zero sets bit zero.
 * @param index Target applet index 1–31. Other values are ignored.
 */
void AppletAddContextLock(uint32_t index);

/** @brief Remove the current identity-context bit from an applet mask.
 * @param index Target applet index 1–31; other values are ignored. Requires a
 * valid current identity in 0–31, as for AppletAddContextLock().
 */
void AppletRemoveContextLock(uint32_t index);

/** @brief Header of an applet resource record in firmware byte order.
 *
 * Six-byte header followed by length payload bytes and, for odd lengths, one
 * unused padding byte. Type zero terminates a search. These functions do not
 * validate bounds or supply allocations; streams must be word-aligned.
 */
typedef struct _AppletResource_t {
    uint16_t type; /**< Resource category; zero is the search terminator. */
    uint16_t id; /**< Identifier within the category. */
    uint16_t length; /**< Payload byte count, excluding header and padding. */
    uint8_t data[]; /**< Inline payload, beginning six bytes after the header. */
} AppletResource_t;

/** @brief Get the resource stream for the current identity context.
 *
 * The descriptor must exist. Context zero resolves offsets from the system ROM
 * base; other contexts resolve them from their applet headers. The returned
 * storage remains owned by the firmware/applet. The Betawise entry bridges the
 * ROM's D0 pointer result to GCC's A0 result convention.
 * @return Stream pointer, or NULL for an unset/out-of-range context or zero resource offset.
 */
const AppletResource_t* AppletGetResources(void);

/** @brief Read one resource header and move the stream cursor.
 *
 * All pointers are required. A zero-length record leaves the cursor unchanged.
 * Nonzero lengths advance by six plus the length rounded up to an even number;
 * lengths must be at most 65534 to avoid the ROM's 16-bit rounding overflow.
 * @param cursor Address of the current record pointer; updated in place.
 * @param type Output category word.
 * @param id Output identifier word.
 * @param length Output unpadded payload byte count.
 * @param data Output borrowed payload pointer, including for zero-length records.
 */
void AppletReadResource(const AppletResource_t** cursor, uint16_t* type,
                        uint16_t* id, uint16_t* length, const void** data);

/** @brief Append a resource to caller-owned storage.
 *
 * Does not allocate, check capacity, write a terminator, or initialize padding.
 * Always advances, including by six bytes for an empty record.
 * @param cursor Writable record pointer, updated past the new record and padding.
 * @param type Category word; zero may be written as a terminator.
 * @param id Identifier word.
 * @param length Payload length, at most 65534.
 * @param data Source payload; may be NULL only when length is zero.
 */
void AppletWriteResource(AppletResource_t** cursor, uint16_t type, uint16_t id,
                         uint16_t length, const void* data);

/** @brief Search a zero-type-terminated resource stream.
 *
 * Starts at *cursor. A match advances the cursor past that record. Failure
 * leaves it at the zero-type terminator and preserves both optional outputs.
 * Zero-length records advance by six; lengths must not exceed 65534.
 * @param cursor Required stream cursor, updated in place.
 * @param type Nonzero category to match.
 * @param id Identifier to match.
 * @param length Optional payload byte count output.
 * @param data Optional borrowed payload pointer output.
 * @return Zero on a match, -1 at the terminator without a match.
 */
int32_t AppletFindResource(const AppletResource_t** cursor, uint16_t type,
                           uint16_t id, uint16_t* length, const void** data);

#endif
