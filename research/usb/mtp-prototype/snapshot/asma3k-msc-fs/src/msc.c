/* AS3000/PDIUSBD11 read-only USB view of native files.
 * FAT12 sectors are generated into the existing eight-byte packet buffer.
 * No disk image, FAT table, directory table or sector buffer in guest RAM. */
#include "fat12.h"
#include <stdint.h>
typedef uint8_t u8; typedef uint16_t u16; typedef uint32_t u32;
#define REG8(a) (*(volatile u8 *)(a))
#define REG32(a) (*(volatile u32 *)(a))
#define DIR REG8(0xfffff420)
#define DATA REG8(0xfffff421)
#define SEL REG8(0xfffff423)
#define IMR REG32(0xfffff304)
#define IPENDING REG32(0xfffff310)
#define SECTORS FAT12_SECTORS
struct telemetry {u32 magic,polls,i2c_errors,resets,setups,cbws,scsi,tx,rx,saved_imr,imr,sr,exit,done,phase,configuration,errors,pending_seen,fs_status,fs_files,fs_clusters;};
#define T (*(volatile struct telemetry *)0x3e000)
static u8 configuration,address_pending,address_value,control_status,ctrl_zlp;
static const u8 *ctrl_source;
static u16 ctrl_left;
static u8 small[36] __attribute__((aligned(2))), ctrlbuf[64] __attribute__((aligned(2))), cbw[31] __attribute__((aligned(2))), csw[13] __attribute__((aligned(2))), sense_key,sense_asc;
static u8 cbw_used,bot_state,bot_status,bot_zlp,halt_in,halt_out;
static const u8 *bulk_source;
static u32 bulk_left,host_length,residue,drain_left;
static u8 csw_offset,bulk_generated;
static u32 bulk_offset;
enum { WAIT_CBW, DATA_IN, DATA_OUT, STATUS_IN, NEED_RESET };
static const u8 devdesc[]={18,1,0x10,1,0,0,0,8,0x1e,8,0xff,0xbd,0,1,1,2,3,1};
static const u8 cfgdesc[]={9,2,32,0,1,1,0,0x80,50,9,4,0,0,2,8,6,0x50,0,7,5,0x81,2,8,0,0,7,5,1,2,8,0,0};
static void lines(u8 scl,u8 sda){u8 v=DIR;DIR=(v&~6u)|(scl?0:4)|(sda?0:2);}
static void start(void){lines(0,1);lines(1,1);lines(1,0);lines(0,0);}
static void stop(void){lines(0,0);lines(1,0);lines(1,1);}
static void put(u8 v){for(u8 i=0;i<8;i++){u8 bit=(v&0x80)!=0;lines(0,bit);lines(1,bit);lines(0,bit);v<<=1;}lines(0,1);lines(1,1);if(DATA&2)T.i2c_errors++;lines(0,1);}
static u8 get(u8 last){u8 v=0;for(u8 i=0;i<8;i++){lines(0,1);lines(1,1);v=(v<<1)|((DATA>>1)&1);lines(0,1);}lines(0,last);lines(1,last);lines(0,last);lines(0,1);return v;}
static void cmd(u8 c){start();put(0x36);put(c);stop();}
static void wr(u8 v){start();put(0x34);put(v);stop();}
static u8 rd(void){start();put(0x35);u8 v=get(1);stop();return v;}
static void regwrite(u8 c,u8 v){cmd(c);wr(v);}
static u8 full(u8 ep){cmd(ep);return rd()&1;}
static u16 irq(void){cmd(0xf4);start();put(0x35);u16 v=get(0);v|=(u16)get(1)<<8;stop();return v;}
static u8 last(u8 ep){cmd(0x40+ep);return rd();}
static void clear_fifo(u8 ep){cmd(ep);cmd(0xf2);}
static void transmit(u8 ep,const u8 *p,u8 n){cmd(ep);cmd(0xf0);start();put(0x34);put(0);put(n);for(u8 i=0;i<n;i++)put(p[i]);stop();cmd(0xfa);T.tx++;}
static u8 receive(u8 ep,u8 *p){cmd(ep);cmd(0xf0);start();put(0x35);(void)get(0);u8 n=get(0);if(n>8){n=8;T.errors++;}for(u8 i=0;i<n;i++)p[i]=get(i+1==n);/* Header-only FIFO reads still end the transaction. */stop();clear_fifo(ep);T.rx++;return n;}
static void halt(u8 in,u8 on){regwrite(in?0x44:0x45,on);if(in)halt_in=on;else halt_out=on;}
static u16 le16(const volatile u8*p){return p[0]|(u16)p[1]<<8;}
static u32 le32(const volatile u8*p){return p[0]|(u32)p[1]<<8|(u32)p[2]<<16|(u32)p[3]<<24;}
static u32 be32(const volatile u8*p){return (u32)p[0]<<24|(u32)p[1]<<16|(u32)p[2]<<8|p[3];}
static void little32(u8*p,u32 v){for(u8 i=0;i<4;i++){p[i]=v;v>>=8;}}
static void big32(u8*p,u32 v){for(u8 i=0;i<4;i++){p[3-i]=v;v>>=8;}}
static void zero(u8*p,u16 n){while(n--)*p++=0;}
static void copy(u8*p,const u8*q,u16 n){while(n--)*p++=*q++;}
static void bot_reset(void){cbw_used=0;bot_state=WAIT_CBW;bulk_left=drain_left=0;csw_offset=0;bot_zlp=0;clear_fifo(4);clear_fifo(5);}
static void reset(void){T.resets++;configuration=0;address_pending=control_status=0;ctrl_left=0;ctrl_zlp=0;halt_in=halt_out=0;regwrite(0xd1,0x80);regwrite(0xd8,0);bot_reset();}
static void ctrl(const u8*p,u16 n,u16 requested){ctrl_source=p;ctrl_left=n<requested?n:requested;ctrl_zlp=(ctrl_left<requested&&(ctrl_left&7)==0);control_status=0;}
static void stall_control(void){regwrite(0x42,1);regwrite(0x43,1);ctrl_left=0;ctrl_zlp=control_status=0;}
static void setup(const u8 *s){u8 type=s[0],r=s[1];u16 value=le16(s+2),index=le16(s+4),len=le16(s+6);T.setups++;ctrl_left=0;ctrl_zlp=control_status=0;
 if(type==0x80&&r==6){u8 kind=value>>8,id=value;
  if(kind==1&&id==0){ctrl(devdesc,sizeof devdesc,len);return;}
  if(kind==2&&id==0){ctrl(cfgdesc,sizeof cfgdesc,len);return;}
  if(kind==3){if(id==0){ctrlbuf[0]=4;ctrlbuf[1]=3;ctrlbuf[2]=9;ctrlbuf[3]=4;ctrl(ctrlbuf,4,len);return;}const char *text=id==1?"AlphaSmart prototype":id==2?"AlphaSmart files":id==3?"AS3K0001":0;if(text){u8 n=2;while(*text&&n<62){ctrlbuf[n++]=*text++;ctrlbuf[n++]=0;}ctrlbuf[0]=n;ctrlbuf[1]=3;ctrl(ctrlbuf,n,len);return;}}
 }
 if(type==0&&r==5&&value<128&&index==0&&len==0){address_pending=1;address_value=value;control_status=1;return;}
 if(type==0&&r==9&&value<=1&&index==0&&len==0){configuration=value;regwrite(0xd8,value?2:0);halt(1,0);halt(0,0);bot_reset();control_status=1;return;}
 if(type==0x80&&r==8&&value==0&&index==0&&len==1){ctrlbuf[0]=configuration;ctrl(ctrlbuf,1,len);return;}
 if((type==0x80||type==0x81||type==0x82)&&r==0&&value==0&&len==2){ctrlbuf[0]=type==0x82?(index==0x81?halt_in:index==1?halt_out:0):0;ctrlbuf[1]=0;ctrl(ctrlbuf,2,len);return;}
 if(type==2&&(r==1||r==3)&&value==0&&len==0&&(index==0x81||index==1)){halt(index==0x81,r==3);control_status=1;return;}
 if(type==0xa1&&r==0xfe&&value==0&&index==0&&len==1){ctrlbuf[0]=0;ctrl(ctrlbuf,1,len);return;}
 if(type==0x21&&r==0xff&&value==0&&index==0&&len==0){bot_reset();control_status=1;return;}
 if(type==0x81&&r==10&&value==0&&index==0&&len==1){ctrlbuf[0]=0;ctrl(ctrlbuf,1,len);return;}
 if(type==1&&r==11&&value==0&&index==0&&len==0){control_status=1;return;}
 stall_control();
}
static void control_poll(void){u8 p[8];if(address_pending&&control_status==2&&!full(3)){regwrite(0xd1,0x80|address_value);address_pending=0;control_status=0;}
 if(full(2)){u8 status=last(2);if(status&0x20){cmd(2);cmd(0xf1);cmd(3);cmd(0xf1);}u8 n=receive(2,p);if((status&0x20)&&n==8)setup(p);}
 if(!full(3)){if(ctrl_left){u8 n=ctrl_left>8?8:ctrl_left;transmit(3,ctrl_source,n);ctrl_source+=n;ctrl_left-=n;}else if(ctrl_zlp){transmit(3,ctrlbuf,0);ctrl_zlp=0;}else if(control_status==1){transmit(3,ctrlbuf,0);control_status=2;}}
}
static void failed(u8 key,u8 asc){sense_key=key;sense_asc=asc;bot_status=1;}
static void begin_status(void){csw[0]='U';csw[1]='S';csw[2]='B';csw[3]='S';copy(csw+4,cbw+4,4);little32(csw+8,residue);csw[12]=bot_status;csw_offset=0;bot_state=STATUS_IN;}
static void scsi(void){const volatile u8 *c=cbw+15;u32 n=0;const u8 *source=small;zero(small,sizeof small);T.scsi++;host_length=le32(cbw+8);residue=host_length;bot_status=0;bot_zlp=0;bulk_generated=0;
 switch(c[0]){
 case 0:if(!fat12_stable())failed(2,0x3a);break; /* TEST UNIT READY */
 case 3:small[0]=0x70;small[2]=sense_key;small[7]=10;small[12]=sense_asc;n=c[4]<18?c[4]:18;sense_key=sense_asc=0;break;
 case 0x12:if(c[1]&1){if(c[2]==0){small[1]=0;small[3]=1;small[4]=0;n=5;}else failed(5,0x24);}else{small[0]=0;small[1]=0x80;small[2]=4;small[3]=2;small[4]=31;copy(small+8,(const u8*)"ALPHASMT",8);copy(small+16,(const u8*)"NATIVE FILES    ",16);copy(small+32,(const u8*)"0001",4);n=36;}if(n>c[4])n=c[4];break;
 case 0x1a:small[0]=3;small[2]=0x80;n=c[4]<4?c[4]:4;break;
 case 0x5a:small[1]=6;small[3]=0x80;n=8;if(n>((u32)c[7]<<8|c[8]))n=(u16)c[7]<<8|c[8];break;
 case 0x23:small[3]=8;big32(small+4,SECTORS);small[8]=2;small[10]=2;n=12;break;
 case 0x25:if(!fat12_stable())failed(2,0x3a);else{big32(small,SECTORS-1);big32(small+4,512);n=8;}break;
 case 0x28:{u32 lba=be32(c+2),count=(u16)c[7]<<8|c[8];if(lba>=SECTORS||count>SECTORS-lba)failed(5,0x21);else if(!fat12_stable())failed(2,0x3a);else{n=count*512;bulk_generated=1;bulk_offset=lba*512;}break;}
 case 0x2a:failed(7,0x27);break; /* WRITE(10): consume then fail, preserve disk */
 case 0x1b:case 0x1e:case 0x35:break;
 default:failed(5,0x20);break;
 }
 if(host_length&&!(cbw[12]&0x80)){if(c[0]!=0x2a)bot_status=2;drain_left=host_length;bot_state=DATA_OUT;return;}
 if(n>host_length){n=host_length;bot_status=2;}
 if(n&&!(cbw[12]&0x80)){bot_status=2;n=0;}
 bulk_source=source;bulk_left=n;residue=host_length-n;bot_zlp=host_length>n&&(n&7)==0;
 if(n||bot_zlp)bot_state=DATA_IN;else begin_status();
}
static void bulk_poll(void){u8 p[8];if(!configuration)return;
 if(full(5)){(void)last(5);u8 n=receive(5,p);
  if(bot_state==DATA_OUT){if(n>drain_left){T.errors++;bot_state=NEED_RESET;halt(1,1);halt(0,1);}else{drain_left-=n;if(!drain_left)begin_status();}}
  else if(bot_state==WAIT_CBW){if(cbw_used+n>31){bot_state=NEED_RESET;}else{copy(cbw+cbw_used,p,n);cbw_used+=n;if(n<8){if(cbw_used!=31||le32(cbw)!=0x43425355||cbw[13]!=0||(cbw[12]&0x7f)||cbw[14]==0||cbw[14]>16)bot_state=NEED_RESET;else{T.cbws++;cbw_used=0;scsi();}}}if(bot_state==NEED_RESET){halt(1,1);halt(0,1);}}
 }
 if(!halt_in&&!full(4)){
  if(bot_state==DATA_IN){if(bulk_left){u8 n=bulk_left>8?8:bulk_left;if(bulk_generated){if(fat12_read(bulk_offset,p,n)){failed(4,0x44);residue+=bulk_left;bulk_left=0;bot_zlp=1;T.errors++;return;}transmit(4,p,n);bulk_offset+=n;}else{transmit(4,bulk_source,n);bulk_source+=n;}bulk_left-=n;}else if(bot_zlp){transmit(4,small,0);bot_zlp=0;}else begin_status();}
  else if(bot_state==STATUS_IN){u8 n=13-csw_offset;if(n>8)n=8;transmit(4,csw+csw_offset,n);csw_offset+=n;if(csw_offset==13)bot_state=WAIT_CBW;}
 }
}
void msc_main(void){u8 saved_dir=DIR,saved_data=DATA,saved_sel=SEL;u32 saved=IMR;T.saved_imr=saved;IMR=saved|0x00100000;T.imr=IMR;u16 sr;__asm__ volatile("move.w %%sr,%0":"=d"(sr));T.sr=sr;
 if(fat12_mount()){T.fs_status=0xffffffffu;T.errors++;T.magic=0x4641494c;for(;;)__asm__ volatile("nop");}
 T.fs_status=1;T.fs_files=fat12_file_count();T.fs_clusters=fat12_used_clusters();
 DATA&=~6u;SEL|=6;lines(1,1);
 cmd(0xf3);start();put(0x34);put(0x91);put(3);stop();regwrite(0xd1,0x80);regwrite(0xd8,0);T.magic=0x4d534331;
 while(!T.exit){T.polls++;T.pending_seen|=IPENDING;u16 pending=irq();if(pending&0x4000)reset();control_poll();bulk_poll();T.phase=bot_state;T.configuration=configuration;}
 cmd(0xf3);start();put(0x34);put(0x81);put(3);stop();regwrite(0xd8,0);DATA=saved_data;SEL=saved_sel;DIR=saved_dir;IMR=saved;fat12_unmount();T.done=0x444f4e45;for(;;)__asm__ volatile("nop");
}
