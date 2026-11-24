/* GCC may lower structure assignments to memcpy even with -fno-builtin. */
#include <stddef.h>
void *memcpy(void *destination,const void *source,size_t count) {
 unsigned char *d=destination;const unsigned char *s=source;
 while(count--)*d++=*s++;return destination;
}
