/* Byte-generated FAT12/VFAT view of native files. No writable FAT storage.
 * Layout: boot, two 12-sector FATs, 512 root entries, 4039 data clusters.
 * Each app owns one contiguous directory chain followed by its native files.
 * Allocation is recomputed from immutable native metadata, not kept in RAM.
 */
#include "fat12.h"
#include "native_fs.h"
#define FAT_SECTORS 12u
#define ROOT_ENTRIES 512u
#define ROOT_SECTORS 32u
#define ROOT_LBA (1u+2u*FAT_SECTORS)
#define DATA_LBA (ROOT_LBA+ROOT_SECTORS)
#define CLUSTERS (FAT12_SECTORS-DATA_LBA)
#define NONE 0xffffu
#define FILE_SLOTS 6u
#define APP_SLOTS 10u
struct object {uint16_t app,index;}; /* index NONE denotes an applet directory */
struct extent {uint32_t address,length;uint16_t start,count,app,index;uint8_t valid;};
static struct {uint32_t fingerprint;uint16_t used,files;uint8_t mounted;struct extent cache;} volume;
/* Two constant-size cursors; neither contains a FAT entry/table, directory
 * entry, sector, filename string, or per-file index. */
static struct {struct object key;uint16_t plain,length,insert;uint8_t collides,valid;} naming;
static struct {struct object object;uint32_t entry,size;uint16_t app,slot,start;uint8_t kind,valid;} directory_cursor;
static uint8_t upper(uint8_t c){return c>='a'&&c<='z'?c-32:c;}
static uint8_t hex(uint16_t n){return (uint8_t)"0123456789ABCDEF"[n&15];}
static uint8_t safe(uint8_t c){return c>=32&&c<127&&c!='"'&&c!='*'&&c!='/'&&c!=':'&&c!='<'&&c!='>'&&c!='?'&&c!='\\'&&c!='|'&&c!='_'&&c!='~';}
static uint16_t clusters(uint32_t length){return (uint16_t)((length+511u)>>9);}
static int info(struct object o,struct asfs_name *name,uint32_t *flags){
 if(o.index==NONE){struct asfs_folder f;if(asfs_folder(o.app,&f)||!f.present)return -1;*name=f.name;*flags=0;}
 else {struct asfs_file f;if(asfs_file(o.app,o.index,&f))return -1;*name=f.name;*flags=f.flags;}
 return 0;
}
static uint16_t escaped_length(const struct asfs_name *n){
 if(!n->length)return 4;uint16_t len=0;
 for(uint16_t i=0;i<n->length;i++){uint8_t c=asfs_name_byte(n,i);len+=(safe(c)&&!(i+1==n->length&&(c==' '||c=='.')))?1:3;}
 return len;
}
static uint8_t escaped_byte(const struct asfs_name *n,uint16_t at){
 if(!n->length)return at<4?(uint8_t)"FILE"[at]:0;
 for(uint16_t i=0;i<n->length;i++){
  uint8_t c=asfs_name_byte(n,i);uint8_t width=(safe(c)&&!(i+1==n->length&&(c==' '||c=='.')))?1:3;
  if(at<width)return width==1?c:at==0?'_':at==1?hex(c>>4):hex(c);
  at-=width;
 }return 0;
}
static uint16_t extension(const struct asfs_name *n){
 for(uint16_t i=n->length;i>1;i--)if(asfs_name_byte(n,i-1)=='.'&&i<n->length)return i-1;
 return NONE;
}
static uint8_t reserved(const struct asfs_name *n){
 uint16_t len=escaped_length(n),stem=0;while(stem<len&&escaped_byte(n,stem)!='.')stem++;
 if(stem==3){uint8_t a=upper(escaped_byte(n,0)),b=upper(escaped_byte(n,1)),c=upper(escaped_byte(n,2));
  return (a=='C'&&b=='O'&&c=='N')||(a=='P'&&b=='R'&&c=='N')||(a=='A'&&b=='U'&&c=='X')||(a=='N'&&b=='U'&&c=='L');}
 if(stem==4){uint8_t d=escaped_byte(n,3);return d>='1'&&d<='9'&&((upper(escaped_byte(n,0))=='C'&&upper(escaped_byte(n,1))=='O'&&upper(escaped_byte(n,2))=='M')||(upper(escaped_byte(n,0))=='L'&&upper(escaped_byte(n,1))=='P'&&upper(escaped_byte(n,2))=='T'));}
 return 0;
}
static uint16_t base_length(struct object o){struct asfs_name n;uint32_t f;if(info(o,&n,&f))return 0;return escaped_length(&n)+reserved(&n)+(o.index!=NONE&&extension(&n)==NONE?4:0);}
static uint8_t base_byte(struct object o,uint16_t at){
 struct asfs_name n;uint32_t flags;if(info(o,&n,&flags))return 0;
 if(reserved(&n)){if(!at)return '_';at--;}
 uint16_t len=escaped_length(&n);if(at<len)return escaped_byte(&n,at);at-=len;
 if(o.index!=NONE&&extension(&n)==NONE&&at<4)return (uint8_t)(flags&4?".RAW":".BIN")[at];
 return 0;
}
static uint8_t same_name(struct object a,struct object b){
 uint16_t n=base_length(a);if(n!=base_length(b))return 0;
 for(uint16_t i=0;i<n;i++)if(upper(base_byte(a,i))!=upper(base_byte(b,i)))return 0;return 1;
}
static uint8_t collision(struct object o){
 if(o.index==NONE){for(uint16_t a=0;a<ASFS_APPS;a++){struct asfs_folder f;if(a==o.app)continue;if(asfs_folder(a,&f))return 1;if(f.present&&same_name(o,(struct object){a,NONE}))return 1;}}
 else {struct asfs_folder f;if(asfs_folder(o.app,&f))return 1;for(uint16_t i=0;i<f.count;i++)if(i!=o.index&&same_name(o,(struct object){o.app,i}))return 1;}
 return 0;
}
static void select_name(struct object o){
 if(naming.valid&&naming.key.app==o.app&&naming.key.index==o.index)return;
 naming.key=o;naming.plain=base_length(o);naming.collides=collision(o);naming.length=naming.plain+(naming.collides?5:0);naming.insert=naming.plain;
 if(naming.collides&&o.index!=NONE)for(uint16_t i=naming.plain;i>0;i--)if(base_byte(o,i-1)=='.'){naming.insert=i-1;break;}
 naming.valid=1;
}
static uint16_t name_length(struct object o){select_name(o);return naming.length;}
static uint8_t name_byte(struct object o,uint16_t at){
 select_name(o);if(!naming.collides)return base_byte(o,at);
 uint16_t insert=naming.insert;
 if(at<insert)return base_byte(o,at);
 if(at<insert+5){uint16_t v=o.index==NONE?o.app:o.index;at-=insert;return !at?'~':hex(v>>(4*(4-at)));}
 return base_byte(o,at-5);
}
static uint16_t quotient16(uint16_t n,uint16_t divisor){
#ifdef __m68k__
 uint32_t wide=n;__asm__("divu.w %1,%0":"+d"(wide):"d"(divisor):"cc");return (uint16_t)wide;
#else
 return n/divisor;
#endif
}
static uint16_t remainder16(uint16_t n,uint16_t divisor){
#ifdef __m68k__
 uint32_t wide=n;__asm__("divu.w %1,%0":"+d"(wide):"d"(divisor):"cc");return (uint16_t)(wide>>16);
#else
 return n%divisor;
#endif
}
static uint16_t slots(struct object o){
 uint16_t n=(uint16_t)(name_length(o)+13);
#ifdef __m68k__
 uint32_t q=n;__asm__("divu.w #13,%0":"+d"(q)::"cc");return (uint16_t)q+1;
#else
 return n/13+1;
#endif
}
static uint8_t alias_byte(struct object o,uint8_t at){
 /* Fixed ordinal aliases cannot collide with another native record, even when
  * names/IDs are duplicated. Long names retain human-readable names. */
 uint16_t ordinal=(o.index==NONE?o.app:o.index)+1;
 if(!at)return o.index==NONE?'A':'F';if(at<8)return hex((uint32_t)ordinal>>(4*(7-at)));
 if(o.index==NONE)return ' ';
 struct asfs_name n;uint32_t flags;if(info(o,&n,&flags))return ' ';
 uint16_t dot=extension(&n);if(dot!=NONE&&n.length-dot-1<=3){uint16_t i=dot+at-7;if(i>=n.length)return ' ';uint8_t c=upper(asfs_name_byte(&n,i));if((c>='A'&&c<='Z')||(c>='0'&&c<='9'))return c;}
 return (uint8_t)(flags&4?"RAW":"BIN")[at-8];
}
static uint8_t checksum(struct object o){uint8_t s=0;for(uint8_t i=0;i<11;i++)s=(uint8_t)(((s&1)?128:0)+(s>>1)+alias_byte(o,i));return s;}
static uint16_t directory_clusters(uint16_t app){
 struct asfs_folder folder;if(asfs_folder(app,&folder)||!folder.present)return 0;
 /* Fixed virtual entry slots avoid name/collision scans in cluster allocation.
  * Unused leading slots are generated as deleted entries, not an early EOF. */
 return (uint16_t)((3u+folder.count*FILE_SLOTS+15u)>>4);
}
static uint16_t app_start(uint16_t app){
 uint16_t at=2;for(uint16_t a=0;a<app;a++){
  struct asfs_folder folder;if(asfs_folder(a,&folder))return 0;if(!folder.present)continue;
  at+=directory_clusters(a);for(uint16_t i=0;i<folder.count;i++){struct asfs_file file;if(asfs_file(a,i,&file))return 0;at+=clusters(file.length);}
 }return at;
}
static uint16_t file_start(uint16_t app,uint16_t index){
 struct asfs_file f;if(asfs_file(app,index,&f)||!f.length)return 0;
 uint16_t at=app_start(app)+directory_clusters(app);
 for(uint16_t i=0;i<index;i++){if(asfs_file(app,i,&f))return 0;at+=clusters(f.length);}return at;
}
static int locate(uint16_t cluster,struct extent *out){
 if(volume.cache.valid&&cluster>=volume.cache.start&&cluster<volume.cache.start+volume.cache.count){*out=volume.cache;return 0;}
 uint16_t at=2;
 for(uint16_t a=0;a<ASFS_APPS;a++){
  struct asfs_folder folder;if(asfs_folder(a,&folder))return -1;if(!folder.present)continue;
  uint16_t n=directory_clusters(a);
  if(cluster>=at&&cluster<at+n){out->address=0;out->length=(uint32_t)n*512;out->start=at;out->count=n;out->app=a;out->index=NONE;out->valid=1;volume.cache=*out;return 0;}at+=n;
  for(uint16_t i=0;i<folder.count;i++){
   struct asfs_file f;if(asfs_file(a,i,&f))return -1;n=clusters(f.length);
   if(cluster>=at&&cluster<at+n){out->address=f.address;out->length=f.length;out->start=at;out->count=n;out->app=a;out->index=i;out->valid=1;volume.cache=*out;return 0;}at+=n;
  }
 }return -1;
}
static uint16_t fat_entry(uint16_t c){
 if(!c)return 0xff8;if(c==1)return 0xfff;if(c>=volume.used+2)return 0;
 struct extent e;if(locate(c,&e))return 0xff7;return c+1==e.start+e.count?0xfff:c+1;
}
static uint8_t fat_byte(uint16_t pos){
 uint16_t c=(uint16_t)(pos/3u)*2u;uint8_t part=pos%3u;
 if(!part)return (uint8_t)fat_entry(c);
 if(part==1)return (uint8_t)((fat_entry(c)>>8)|((fat_entry(c+1)&15)<<4));
 return (uint8_t)(fat_entry(c+1)>>4);
}
static uint8_t word_byte(uint32_t value,uint8_t index){return (uint8_t)(value>>(index*8));}
static uint8_t boot_byte(uint16_t p){
 if(p==0)return 0xeb;if(p==1)return 0x3c;if(p==2)return 0x90;
 if(p<11)return (uint8_t)"AS3KFS  "[p-3];
 if(p==12)return 2;if(p==13||p==14)return 1;if(p==16)return 2;
 if(p==18)return 2; /* 512 root entries */
 if(p==19||p==20)return word_byte(FAT12_SECTORS,p-19);
 if(p==21)return 0xf8;if(p==22)return FAT_SECTORS;if(p==24||p==26)return 1;
 if(p==36)return 0x80;if(p==38)return 0x29;
 if(p>=39&&p<43)return (uint8_t)"ASFS"[p-39];
 if(p>=43&&p<54)return (uint8_t)"ALPHASMART "[p-43];
 if(p>=54&&p<62)return (uint8_t)"FAT12   "[p-54];
 if(p==510)return 0x55;if(p==511)return 0xaa;return 0;
}
static uint8_t short_entry(struct object o,uint8_t p,uint16_t start,uint32_t size){
 if(p<11)return alias_byte(o,p);if(p==11)return o.index==NONE?0x10:1;
 if(p==16||p==18||p==24)return 0x21; /* 1980-01-01 */
 if(p==26||p==27)return word_byte(start,p-26);
 if(p>=28)return o.index==NONE?0:word_byte(size,p-28);return 0;
}
static uint8_t object_entry(struct object o,uint16_t slot,uint8_t p){
 uint16_t long_slots=slots(o)-1;
 if(slot==long_slots){
  return short_entry(o,p,directory_cursor.start,directory_cursor.size);
 }
 uint8_t ordinal=(uint8_t)(long_slots-slot);
 if(!p)return ordinal|(slot==0?0x40:0);if(p==11)return 0x0f;if(p==13)return checksum(o);
 if(p==12||p==26||p==27)return 0;
 uint8_t unit,high;
 if(p<11){unit=(p-1)/2;high=(p-1)&1;}
 else if(p<26){unit=5+(p-14)/2;high=(p-14)&1;}
 else {unit=11+(p-28)/2;high=(p-28)&1;}
 uint16_t at=(uint16_t)(ordinal-1)*13+unit,len=name_length(o);
 if(at>len)return 0xff;if(high||at==len)return 0;return name_byte(o,at);
}
static uint8_t dot_entry(uint8_t parent,uint8_t p,uint16_t start){
 if(p<11)return p==0||(p==1&&parent)?'.':' ';if(p==11)return 0x10;
 if(p==16||p==18||p==24)return 0x21;if(p==26||p==27)return word_byte(start,p-26);return 0;
}
static uint8_t directory_byte(uint16_t app,uint32_t pos){
 uint16_t entry=(uint16_t)(pos>>5);uint8_t p=pos&31;
 if(!directory_cursor.valid||directory_cursor.app!=app||directory_cursor.entry!=entry){
  directory_cursor.valid=1;directory_cursor.app=app;directory_cursor.entry=entry;directory_cursor.kind=0;
  uint16_t offset=0,width=0;
  if(app==NONE){
   if(!entry)directory_cursor.kind=1;
   else if(entry<=ASFS_APPS*APP_SLOTS){
    uint16_t a=quotient16(entry-1,APP_SLOTS);struct asfs_folder f;
    if(!asfs_folder(a,&f)&&f.present){directory_cursor.kind=2;directory_cursor.object=(struct object){a,NONE};offset=remainder16(entry-1,APP_SLOTS);width=APP_SLOTS;}
    else directory_cursor.kind=5;
   }
  }else if(entry<2){directory_cursor.kind=entry==0?3:4;directory_cursor.start=entry==0?app_start(app):0;}
  else{struct asfs_folder f;uint16_t i=quotient16(entry-2,FILE_SLOTS);
   if(!asfs_folder(app,&f)&&i<f.count){directory_cursor.kind=2;directory_cursor.object=(struct object){app,i};offset=remainder16(entry-2,FILE_SLOTS);width=FILE_SLOTS;}}
  if(directory_cursor.kind==2){
   struct object o=directory_cursor.object;uint16_t n=slots(o);
   if(n>width)return 0; /* mount/name bounds make this unreachable */
   if(offset<width-n)directory_cursor.kind=5;
   else{directory_cursor.slot=offset-(width-n);
    if(directory_cursor.slot==n-1){
     if(o.index==NONE){directory_cursor.start=app_start(o.app);directory_cursor.size=0;}
     else{struct asfs_file f;if(asfs_file(o.app,o.index,&f))return 0;directory_cursor.start=file_start(o.app,o.index);directory_cursor.size=f.length;}
    }
   }
  }
 }
 if(directory_cursor.kind==1){if(p<11)return (uint8_t)"ALPHASMART "[p];return p==11?8:0;}
 if(directory_cursor.kind==2)return object_entry(directory_cursor.object,directory_cursor.slot,p);
 if(directory_cursor.kind==3||directory_cursor.kind==4)return dot_entry(directory_cursor.kind==4,p,directory_cursor.start);
 if(directory_cursor.kind==5)return p==0?0xe5:0;
 return 0;
}
int fat12_mount(void){
 volume.mounted=0;volume.cache.valid=0;naming.valid=directory_cursor.valid=0;volume.used=volume.files=0;
 uint32_t hash=asfs_metadata_hash();if(!hash)return -1;
 uint16_t root_used=2+ASFS_APPS*APP_SLOTS; /* label, all app slots, EOF */
 for(uint16_t a=0;a<ASFS_APPS;a++){
  struct asfs_folder folder;if(asfs_folder(a,&folder))return -1;if(!folder.present)continue;
  volume.used+=directory_clusters(a);if(volume.used>CLUSTERS)return -1;
  for(uint16_t i=0;i<folder.count;i++){struct asfs_file f;if(asfs_file(a,i,&f))return -1;volume.files++;uint16_t n=clusters(f.length);if(n>CLUSTERS-volume.used)return -1;volume.used+=n;}
  if(volume.used>CLUSTERS)return -1;
 }
 if(root_used>ROOT_ENTRIES||hash!=asfs_metadata_hash())return -1;
 volume.fingerprint=hash;volume.mounted=1;return 0;
}
void fat12_unmount(void){volume.mounted=0;volume.cache.valid=0;naming.valid=directory_cursor.valid=0;}
int fat12_stable(void){
 if(!volume.mounted)return 0;
 if(asfs_metadata_hash()!=volume.fingerprint){fat12_unmount();return 0;}return 1;
}
uint16_t fat12_used_clusters(void){return volume.used;}
uint16_t fat12_file_count(void){return volume.files;}
int fat12_read(uint32_t pos,uint8_t *out,uint16_t count){
 if(!volume.mounted||pos>FAT12_SECTORS*512u||count>FAT12_SECTORS*512u-pos)return -1;
 while(count){
  uint32_t lba=pos>>9;uint16_t within=pos&511;
  if(lba>=DATA_LBA){
   uint16_t c=(uint16_t)(lba-DATA_LBA+2);struct extent e;
   if(c<volume.used+2){
    if(locate(c,&e))return -1;uint32_t offset=(uint32_t)(c-e.start)*512u+within;
    if(e.index!=NONE&&offset<e.length){uint16_t n=count;uint32_t left=e.length-offset;if(n>left)n=(uint16_t)left;if(n>512u-within)n=512u-within;
     if(asfs_bytes(e.address+offset,out,n))return -1;out+=n;pos+=n;count-=n;continue;}
    *out++=e.index==NONE?directory_byte(e.app,offset):0;
   }else *out++=0;
  }else if(!lba)*out++=boot_byte(within);
  else if(lba<ROOT_LBA)*out++=fat_byte((uint16_t)((uint16_t)(lba-1)%FAT_SECTORS)*512u+within);
  else *out++=directory_byte(NONE,(lba-ROOT_LBA)*512u+within);
  pos++;count--;
 }return 0;
}
