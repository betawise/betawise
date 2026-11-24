#ifndef STREAM_FAT12_H
#define STREAM_FAT12_H
#include <stdint.h>
#define FAT12_SECTORS 4096u
#define FAT12_SECTOR_BYTES 512u
/* Guest state is O(1): scalar geometry/guards and one native extent cache.
 * No disk image, FAT table, directory table, or sector buffer is allocated. */
int fat12_mount(void);
void fat12_unmount(void);
int fat12_stable(void);
int fat12_read(uint32_t byte_offset,uint8_t *destination,uint16_t count);
uint16_t fat12_used_clusters(void);
uint16_t fat12_file_count(void);
#endif
