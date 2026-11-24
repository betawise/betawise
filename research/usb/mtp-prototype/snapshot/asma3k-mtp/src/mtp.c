/* Minimal native-object MTP responder. AS3000 3.01; foreground polling only.
 * No disk image or whole-file upload buffer. No other native writers may run.
 * Object properties/extensions are deliberately not advertised: ObjectInfo is
 * the metadata API, as in jacobly0/transfer. All multibyte wire values are LE. */
#include "mtp.h"
#include "native_fs.h"
typedef uint8_t u8;typedef uint16_t u16;typedef uint32_t u32;
#ifndef PLAIN_PTP
#define PLAIN_PTP 0
#endif
#ifndef WRITABLE
#define WRITABLE 0
#endif
#define STORAGE 0x10001u
#define FOLDER(a) (0x10000u+(a))
#define MAX_HANDLES 256u
#define OK 0x2001
static u8 header[32],dataset[384],response[24];
static u16 used,built,opcode;
static u32 transaction,session,params[5],remaining,txoff,txsize,file_address;
static u8 phase,source,need_zlp,response_zlp;
enum {COMMAND,OUTPUT,INPUT};enum {BUFFER,FILE_BYTES,HANDLES};
static u32 filter_parent,filter_format;
static u16 response_len,response_off;
#if WRITABLE
static u16 result;static u8 rxkind;
/* Monotonic session handles; tombstones are never reused within a session.
 * Ordinals are updated after native table compaction/ID renumbering. */
static struct {u16 app,index;} handles[MAX_HANDLES];
static u16 handle_count;
static struct {u32 size,handle;u16 app,id,index;u8 valid,created;char name[16];} upload;
static u8 write_buffer[128];static u16 write_used;
static u8 event_bytes[16],event_used,event_left,event_zlp;
extern int32_t FileSetFolder(u32,u32*);extern void FileClose(void);
extern int32_t FileCreate(u8,const char*,u32,u32);extern int32_t FileDelete(u16);
extern int32_t FileWriteBuffer(u16,const void*,u32,u32);
extern u32 FileGetFreeSpace(void);
static void select_folder(u16 a){FileClose();FileSetFolder(a,0);}
#else
#define handle_count 0u
#endif
static u16 get16(const volatile u8*p){return p[0]|(u16)p[1]<<8;}
static u32 get32(const volatile u8*p){return p[0]|(u32)p[1]<<8|(u32)p[2]<<16|(u32)p[3]<<24;}
static void put16(volatile u8*p,u16 v){p[0]=v;p[1]=v>>8;}
static void put32(volatile u8*p,u32 v){put16(p,v);put16(p+2,v>>16);}
static void b8(u8 v){if(built<sizeof dataset)dataset[built++]=v;}
static void b16(u16 v){b8(v);b8(v>>8);}
static void b32(u32 v){b16(v);b16(v>>16);}
static void b64(u32 v){b32(v);b32(0);}
static void str(const char*s){u16 n=0;while(s[n])n++;b8(n+1);for(u16 i=0;i<n;i++)b16((u8)s[i]);b16(0);}
static void name(const struct asfs_name*n){b8(n->length+1);for(u16 i=0;i<n->length;i++)b16(asfs_name_byte(n,i));b16(0);}
static int folder_handle(u32 h,u16*a){if(h<0x10000||h>=0x10020)return -1;*a=h-0x10000;struct asfs_folder f;return asfs_folder(*a,&f)||!f.present?-1:0;}
static int file_handle(u32 h,u16*a,u16*i,struct asfs_file*f){
#if WRITABLE
 if(!h||h>handle_count||handles[h-1].app==0xffff)return -1;*a=handles[h-1].app;*i=handles[h-1].index;
#else
 if(!h||h>=0x10000)return -1;h--;*a=h>>8;*i=h&255;
#endif
 return asfs_file(*a,*i,f);
}
static u32 handle_at(u16 a,u16 i){
#if WRITABLE
 for(u16 h=0;h<handle_count;h++)if(handles[h].app==a&&handles[h].index==i)return h+1;return 0;
#else
 return 1u+((u32)a<<8)+i;
#endif
}
/* PTP hosts may refuse Undefined objects without thumbnails. Only explicit
 * .TXT exports are Text; native AlphaWord data remains Undefined (no conversion). */
static u16 format(const struct asfs_file*f){
 if(f->name.length>=4){u16 n=f->name.length-4;
  if(asfs_name_byte(&f->name,n)=='.'&&
     (asfs_name_byte(&f->name,n+1)|32)=='t'&&
     (asfs_name_byte(&f->name,n+2)|32)=='x'&&
     (asfs_name_byte(&f->name,n+3)|32)=='t')return 0x3004;
 }return 0x3000;
}
static u32 matching_handle(u32 ordinal){
 for(u16 a=0;a<32;a++){struct asfs_folder folder;if(asfs_folder(a,&folder)||!folder.present)continue;
  if(!filter_format||filter_format==0x3001){if((filter_parent==0||filter_parent==0xffffffffu)&&ordinal--==0)return FOLDER(a);}
  if(filter_parent==0||filter_parent==FOLDER(a))for(u16 i=0;i<folder.count;i++){struct asfs_file f;if(asfs_file(a,i,&f))continue;if(filter_format&&filter_format!=format(&f))continue;u32 h=handle_at(a,i);if(h&&ordinal--==0)return h;}
 }return 0;
}
static u32 matching_count(void){u32 n=0;while(matching_handle(n))n++;return n;}
static void make_response(u16 code,const u32*p,u8 count){response_len=12+4*count;response_off=0;response_zlp=(response_len&7)==0;put32(response,response_len);put16(response+4,3);put16(response+6,code);put32(response+8,transaction);for(u8 i=0;i<count;i++)put32(response+12+4*i,p[i]);}
static void reply(u16 code){make_response(code,0,0);remaining=txsize=0;txoff=0;need_zlp=0;phase=OUTPUT;}
static void data_start(u8 src,u32 n){source=src;txsize=n+12;txoff=0;need_zlp=(txsize&7)==0;phase=OUTPUT;make_response(OK,0,0);}
#if WRITABLE
static void queue_event(u16 code,u32 h){if(event_left||event_zlp)return;put32(event_bytes,16);put16(event_bytes+4,4);put16(event_bytes+6,code);put32(event_bytes+8,transaction);put32(event_bytes+12,h);event_used=0;event_left=16;event_zlp=1;}
static void indices_deleted(u16 a,u16 i){for(u16 h=0;h<handle_count;h++)if(handles[h].app==a){if(handles[h].index==i)handles[h].app=0xffff;else if(handles[h].index>i)handles[h].index--;}}
static void discard_upload(void){if(upload.created){struct asfs_folder f;if(!asfs_folder(upload.app,&f)&&f.count){select_folder(upload.app);if(FileDelete(upload.id)==0)indices_deleted(upload.app,upload.index);}}upload.valid=upload.created=0;write_used=0;}
static int rebuild(void){handle_count=0;for(u16 a=0;a<32;a++){struct asfs_folder f;if(asfs_folder(a,&f))return -1;for(u16 i=0;i<f.count;i++){if(handle_count==MAX_HANDLES)return -1;handles[handle_count].app=a;handles[handle_count++].index=i;}}return 0;}
static int flush_write(void){if(!write_used)return 0;select_folder(upload.app);int32_t n=FileWriteBuffer(upload.id,write_buffer,write_used,1);if(n!=write_used)return -1;write_used=0;return 0;}
static u16 upload_info(void){if(used<53)return 0xa806;u32 size=get32(dataset+8);u16 a;if(get16(dataset+4)!=0x3000)return 0x200b;if(folder_handle(params[1],&a)||a==0)return 0x201a;if(params[0]!=STORAGE)return 0x2008;
 u8 chars=dataset[52];if(chars<2||chars>16||used<53u+2u*chars)return 0xa806;
 for(u16 i=0;i<chars;i++){u16 c=get16(dataset+53+2*i);if(i==chars-1){if(c)return 0xa806;}else if(c<32||c>126||c=='/'||c=='\\'||c==':'||c=='*'||c=='?'||c=='"'||c=='<'||c=='>'||c=='|')return 0xa806;upload.name[i]=(char)c;}
 if(upload.name[0]=='.'&&(upload.name[1]==0||(upload.name[1]=='.'&&upload.name[2]==0)))return 0xa806;
 struct asfs_folder folder;if(asfs_folder(a,&folder)||folder.count>=254||handle_count==MAX_HANDLES)return 0x200c;
 for(u16 i=0;i<folder.count;i++){struct asfs_file f;if(asfs_file(a,i,&f))return 0x2002;u16 j=0;while(j<f.name.length&&upload.name[j]&&(u8)upload.name[j]==asfs_name_byte(&f.name,j))j++;if(j==f.name.length&&!upload.name[j])return 0x201d;}
 select_folder(a);if(size>FileGetFreeSpace()||size>0x28000)return 0x200c;
 upload.app=a;upload.size=size;upload.handle=++handle_count;handles[handle_count-1].app=0xffff;upload.valid=1;upload.created=0;return OK;
}
static u16 create_upload(void){select_folder(upload.app);int32_t id=FileCreate(0,upload.name,0,upload.size);if(id<0)return 0x200c;upload.id=id;upload.created=1;struct asfs_folder folder;if(asfs_folder(upload.app,&folder))return 0x2002;
 for(u16 i=0;i<folder.count;i++){struct asfs_file f;if(asfs_file(upload.app,i,&f))return 0x2002;if(f.id==(u16)id){upload.index=i;for(u16 h=0;h<handle_count;h++)if(handles[h].app==upload.app&&handles[h].index>=i)handles[h].index++;return OK;}}return 0x2002;}
static u16 commit_upload(void){if(flush_write())return 0x200c;struct asfs_folder folder;struct asfs_file f;if(asfs_folder(upload.app,&folder)||!folder.count||asfs_file(upload.app,upload.index,&f)||f.id!=upload.id||f.length!=upload.size)return 0x2002;handles[upload.handle-1].app=upload.app;handles[upload.handle-1].index=upload.index;queue_event(0x4002,upload.handle);upload.created=upload.valid=0;return OK;}
#endif
void mtp_reset(void){
#if WRITABLE
 discard_upload();event_left=event_zlp=0;
#endif
 used=0;phase=COMMAND;session=0;remaining=0;txsize=0;}
int mtp_init(void){mtp_reset();
#if WRITABLE
 return rebuild();
#else
 return asfs_metadata_hash()?0:-1;
#endif
}
static void object_info(u32 h){struct asfs_file f;u16 a,i;struct asfs_folder folder;int isfolder=!folder_handle(h,&a);if(!isfolder&&file_handle(h,&a,&i,&f)){reply(0x2009);return;}if(isfolder)asfs_folder(a,&folder);
 built=0;b32(STORAGE);b16(isfolder?0x3001:format(&f));b16(!WRITABLE||isfolder?1:0);b32(isfolder?0:f.length);b16(0);for(u8 j=0;j<6;j++)b32(0);b32(isfolder?0:FOLDER(a));b16(isfolder?1:0);b32(0);b32(0);
 if(isfolder)name(&folder.name);else if(f.name.length)name(&f.name);else{char fallback[]="File-0000.BIN";const char*hex="0123456789ABCDEF";for(u8 j=0;j<4;j++)fallback[5+j]=hex[(f.id>>(12-j*4))&15];str(fallback);}b8(0);b8(0);b8(0);data_start(BUFFER,built);
}
static void command(void){opcode=get16(header+6);transaction=get32(header+8);u16 n=(used-12)/4;for(u8 i=0;i<5;i++)params[i]=i<n?get32(header+12+4*i):0;
 if(opcode!=0x1001&&opcode!=0x1002&&!session){reply(0x2003);return;}
#if WRITABLE
 if(upload.valid&&opcode!=0x100d)discard_upload();
#endif
 built=0;
 switch(opcode){
 case 0x1001:{static const u16 ops[]={0x1001,0x1002,0x1003,0x1004,0x1005,0x1006,0x1007,0x1008,0x1009,
#if WRITABLE
 0x100b,0x100c,0x100d,
#endif
 };b16(100);b32(PLAIN_PTP?0:6);b16(PLAIN_PTP?0:100);if(PLAIN_PTP)b8(0);else str("microsoft.com: 1.0;");b16(0);b32(sizeof ops/sizeof ops[0]);for(u16 i=0;i<sizeof ops/sizeof ops[0];i++)b16(ops[i]);b32(WRITABLE?2:0);if(WRITABLE){b16(0x4002);b16(0x4003);}b32(0);b32(0);b32(3);b16(0x3000);b16(0x3001);b16(0x3004);str("AlphaSmart");str("AlphaSmart Files");str("0.1");str(PLAIN_PTP?"AS3KPTP1":"AS3KMTP1");data_start(BUFFER,built);break;}
 case 0x1002:if(session)reply(0x201e);else if(!params[0])reply(0x201d);else{
#if WRITABLE
 if(rebuild()){reply(0x200c);break;}
#endif
 session=params[0];reply(OK);}break;
 case 0x1003:mtp_reset();reply(OK);break;
 case 0x1004:b32(1);b32(STORAGE);data_start(BUFFER,built);break;
 case 0x1005:if(params[0]!=STORAGE){reply(0x2008);break;}b16(3);b16(2);b16(WRITABLE?0:1);b64(*(const volatile u32*)0x354e - 0x4558);
#if WRITABLE
 b64(FileGetFreeSpace());
#else
 b64(0);
#endif
 #if WRITABLE
 {u32 last=*(const volatile u32*)0x3446;u32 slots=127;while(last>0x1042&&slots){last-=72;slots--;}u32 ids=MAX_HANDLES-handle_count;b32(slots<ids?slots:ids);}
#else
 b32(0);
#endif
str("AlphaSmart Files");str("AS3KRAM");data_start(BUFFER,built);break;
 case 0x1006:case 0x1007:if(params[0]!=STORAGE&&params[0]!=0xffffffffu){reply(0x2008);break;}filter_format=params[1];filter_parent=params[2];if(filter_parent&&filter_parent!=0xffffffffu){u16 a;if(folder_handle(filter_parent,&a)){reply(0x201a);break;}}if(opcode==0x1006){u32 count=matching_count();reply(OK);make_response(OK,&count,1);}else data_start(HANDLES,4+matching_count()*4);break;
 case 0x1008:object_info(params[0]);break;
 case 0x1009:{u16 a,i;struct asfs_file f;if(file_handle(params[0],&a,&i,&f)){reply(0x2009);break;}file_address=f.address;data_start(FILE_BYTES,f.length);break;}
#if WRITABLE
 case 0x100b:{u16 a,i;struct asfs_file f;if(file_handle(params[0],&a,&i,&f)||!a){reply(0x2009);break;}select_folder(a);if(FileDelete(f.id)){reply(0x2002);break;}indices_deleted(a,i);queue_event(0x4003,params[0]);reply(OK);break;}
 case 0x100c:discard_upload();phase=INPUT;rxkind=1;used=0;remaining=0;break;
 case 0x100d:if(!upload.valid){reply(0x2015);break;}phase=INPUT;rxkind=2;used=0;remaining=0;write_used=0;break;
#endif
 default:reply(0x2005);break;
 }
}
int mtp_can_receive(void){return phase!=OUTPUT;}
void mtp_receive(const u8*p,u8 n){
 if(phase==COMMAND){if(used+n>sizeof header){mtp_reset();return;}for(u8 i=0;i<n;i++)header[used++]=p[i];if(used>=4){u32 len=get32(header);if(len<12||len>32||(len&3)){mtp_reset();return;}if(used==len){if(get16(header+4)!=1){mtp_reset();return;}command();if(phase==OUTPUT)used=0;}else if(used>len||n<8)mtp_reset();}return;}
#if WRITABLE
 if(phase!=INPUT)return;
 for(u8 i=0;i<n;i++){
  if(rxkind<=2){header[used++]=p[i];if(used==12){u32 len=get32(header);if(len<12||get16(header+4)!=2||get16(header+6)!=opcode||get32(header+8)!=transaction){discard_upload();reply(0xa806);return;}remaining=len-12;result=OK;if(rxkind==1){used=0;rxkind=3;if(remaining>sizeof dataset)result=0xa806;}else{rxkind=4;if(remaining!=upload.size)result=0x2007;else result=upload.valid==2?OK:create_upload();}if(!remaining)goto finish;}continue;}
  /* INPUT body states use header completion sentinel, not a packet boundary. */
  if(rxkind==3){if(used<sizeof dataset)dataset[used++]=p[i];}else if(result==OK){write_buffer[write_used++]=p[i];if(write_used==sizeof write_buffer&&flush_write())result=0x200c;}
  if(remaining)remaining--;if(!remaining){finish:
   if(rxkind==3){if(result==OK)result=upload_info();if(result==OK){u32 q[]={STORAGE,FOLDER(upload.app),upload.handle};reply(OK);make_response(OK,q,3);if(upload.size==0){u16 r=create_upload();if(r==OK)r=commit_upload();if(r!=OK){discard_upload();reply(r);}else upload.valid=2;}}else reply(result);}
   else{if(result==OK){if(upload.valid==2)upload.valid=0;else result=commit_upload();}if(result!=OK)discard_upload();reply(result);}return;}
 }
 if(rxkind>=3)used=rxkind==3?used:12;
#else
 (void)p;(void)n;
#endif
}
/* Return one USB packet, -1 when idle. The data and response phases are separate
 * USB transfers; a multiple-of-eight data transfer ends with an explicit ZLP. */
int mtp_transmit(u8*p){if(phase!=OUTPUT)return -1;
 if(txoff<txsize){u8 n=txsize-txoff>8?8:txsize-txoff;for(u8 j=0;j<n;j++){u32 o=txoff+j;if(o<12){u8 h[12];put32(h,txsize);put16(h+4,2);put16(h+6,opcode);put32(h+8,transaction);p[j]=h[o];}else{o-=12;if(source==BUFFER)p[j]=dataset[o];else if(source==FILE_BYTES)p[j]=asfs_memory_byte(file_address+o);else{u32 v=o<4?(txsize-16)/4:matching_handle((o-4)/4);p[j]=v>>((o&3)*8);}}}txoff+=n;return n;}
 if(need_zlp){need_zlp=0;return 0;}
 if(response_off<response_len){u8 n=response_len-response_off;if(n>8)n=8;for(u8 j=0;j<n;j++)p[j]=response[response_off++];if(response_off==response_len&&!response_zlp){phase=COMMAND;used=0;}return n;}
 if(response_zlp){response_zlp=0;phase=COMMAND;used=0;return 0;}
 return -1;
}
int mtp_event(u8*p){
#if WRITABLE
 if(event_left){u8 n=event_left>8?8:event_left;for(u8 i=0;i<n;i++)p[i]=event_bytes[event_used++];event_left-=n;return n;}if(event_zlp){event_zlp=0;return 0;}
#else
 (void)p;
#endif
 return -1;}
unsigned mtp_phase(void){return phase;}

int mtp_has_output(void){return phase==OUTPUT;}
int mtp_has_event(void){
#if WRITABLE
 return event_left||event_zlp;
#else
 return 0;
#endif
}
