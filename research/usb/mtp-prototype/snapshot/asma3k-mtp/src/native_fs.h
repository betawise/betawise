#ifndef AS_NATIVE_FS_H
#define AS_NATIVE_FS_H
#include <stdint.h>
#define ASFS_APPS 32u
struct asfs_name { uint32_t address; uint8_t length, literal; };
struct asfs_folder { struct asfs_name name; uint32_t table; uint16_t count, app_id; uint8_t present; };
struct asfs_file { struct asfs_name name; uint32_t address, length, capacity, flags; uint16_t id, tag; };
/* Returns 0 on success, negative on malformed native metadata. No OS calls,
 * writes, allocation, opening files, or changes to folder/current position. */
int asfs_folder(uint16_t app, struct asfs_folder *out);
int asfs_file(uint16_t app, uint16_t index, struct asfs_file *out);
uint8_t asfs_name_byte(const struct asfs_name *name, uint16_t index);
int asfs_bytes(uint32_t address, uint8_t *destination, uint16_t count);
uint32_t asfs_metadata_hash(void);
/* The memory reader has a separate host-fixture implementation. */
uint8_t asfs_memory_byte(uint32_t address);
#endif
