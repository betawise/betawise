/* Read-only AS3000 System 3.01 native filesystem adapter. These addresses are
 * ROM-specific: the runner must verify its ROM hash before entering this code.
 * 0xF42 is the native folder table; it is NOT a copied export directory.
 */
#include "native_fs.h"
#define RAM_END 0x40000u
#define APP_TABLE 0x0d82u
#define FOLDERS 0x0f42u
#define CLIPBOARD 0x344au
#define STRIDE 0x48u
#ifndef ASFS_HOST
uint8_t asfs_memory_byte(uint32_t address) { return *(const volatile uint8_t *)address; }
#endif
static uint16_t be16(uint32_t a) {return (uint16_t)asfs_memory_byte(a)<<8|asfs_memory_byte(a+1);}
static uint32_t be32(uint32_t a) {return (uint32_t)be16(a)<<16|be16(a+2);}
static int ram_range(uint32_t a,uint32_t n) {return a>=0x400u&&a<RAM_END&&n<=RAM_END-a;}
static int file_range(uint32_t a,uint32_t n) {
 if(!n)return !a||a<RAM_END;
 if(!ram_range(a,n))return 0;
#ifndef ASFS_HOST
 /* The disposable RAM-loader reserves these addresses. Real installation must
  * obtain its own applet RAM; never overwrite native live allocations. */
 extern char end;
 if((a<(uint32_t)&end&&a+n>0x30000u)||(a<0x3e200u&&a+n>0x3c000u))return 0;
#endif
 return 1;
}
static uint8_t bounded_length(uint32_t a,uint8_t limit) {uint8_t n=0;while(n<limit&&asfs_memory_byte(a+n))n++;return n;}
static int raw_folder(uint16_t app,uint32_t *table,uint16_t *count) {
 if(app>=ASFS_APPS)return -1;
 *table=be32(FOLDERS+(uint32_t)app*8);*count=asfs_memory_byte(FOLDERS+(uint32_t)app*8+4);
 if(*count&&(!file_range(*table,(uint32_t)*count*STRIDE)||(*table&1)))return -1;
 return 0;
}
/* Clipboard is working state, not an exported document. Exclude both its
 * actual global record and its reserved ID, even inside an applet table. */
static int document_record(uint32_t record) {
 return record!=be32(CLIPBOARD)&&be16(record+0x44)!=0x00cb;
}
int asfs_folder(uint16_t app,struct asfs_folder *out) {
 uint32_t table;uint16_t count;if(raw_folder(app,&table,&count))return -1;
 out->table=table;out->count=0;out->app_id=0;out->present=0;
 for(uint16_t i=0;i<count;i++)if(document_record(table+(uint32_t)i*STRIDE))out->count++;
 out->name.address=0;out->name.length=3;out->name.literal=3; /* APP fallback */
 uint32_t header=be32(APP_TABLE+(uint32_t)app*4);
 if(header&&header!=0xffffffffu){
  if(header<0x400000u||header>0x4fff6cu||(header&1)||be32(header)!=0xc0ffeeadu)return -1;
  out->app_id=be16(header+0x14);out->name.address=header+0x18;
  out->name.length=bounded_length(header+0x18,36);out->name.literal=0;out->present=1;
 }
 if(count)out->present=1; /* Do not silently omit files with a missing applet. */
 if(app==0){out->present=1;out->name.length=6;out->name.literal=1;}
 return 0;
}
int asfs_file(uint16_t app,uint16_t index,struct asfs_file *out) {
 uint32_t table;uint16_t count;if(raw_folder(app,&table,&count))return -1;
 uint32_t record=0;uint16_t ordinal=0;
 for(uint16_t i=0;i<count;i++){uint32_t candidate=table+(uint32_t)i*STRIDE;if(!document_record(candidate))continue;if(ordinal++==index){record=candidate;break;}}
 if(!record)return -1;
 out->address=be32(record);out->length=be32(record+4);out->capacity=be32(record+12);
 out->flags=be32(record+0x20);out->id=be16(record+0x44);out->tag=be16(record+0x46);
 if(out->length>out->capacity||(out->capacity&&!ram_range(out->address,out->capacity))||!file_range(out->address,out->length))return -1;
 out->name.address=record+0x34;out->name.length=bounded_length(record+0x34,16);out->name.literal=0;
 return 0;
}
uint8_t asfs_name_byte(const struct asfs_name *name,uint16_t index) {
 if(index>=name->length)return 0;
 if(name->literal==1)return (uint8_t)"System"[index];
 if(name->literal==3)return (uint8_t)"APP"[index];
 return asfs_memory_byte(name->address+index);
}
int asfs_bytes(uint32_t address,uint8_t *destination,uint16_t count) {
 if(!file_range(address,count))return -1;
 while(count--)*destination++=asfs_memory_byte(address++);return 0;
}
static uint32_t mix(uint32_t h,uint32_t v) {return ((h<<5)|(h>>27))^v;}
uint32_t asfs_metadata_hash(void) {
 uint32_t h=0x41534653u;
 for(uint16_t a=0;a<ASFS_APPS;a++){
  struct asfs_folder folder;if(asfs_folder(a,&folder))return 0;
  h=mix(h,folder.table);h=mix(h,folder.count);h=mix(h,folder.app_id);h=mix(h,folder.present);
  for(uint16_t n=0;n<folder.name.length;n++)h=mix(h,asfs_name_byte(&folder.name,n));
  if(!folder.present)continue;
  for(uint16_t i=0;i<folder.count;i++){
   struct asfs_file file;if(asfs_file(a,i,&file))return 0;
   h=mix(h,file.address);h=mix(h,file.length);h=mix(h,file.capacity);h=mix(h,file.flags);
   h=mix(h,file.id);h=mix(h,file.tag);
   for(uint16_t n=0;n<file.name.length;n++)h=mix(h,asfs_name_byte(&file.name,n));
  }
 }
 return h?h:1;
}
