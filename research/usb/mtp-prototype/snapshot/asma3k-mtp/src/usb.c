/* AS3000/PDIUSBD11 native-file MTP polling driver.
 * GPIO/I2C and EP0 are derived from the qualified MSC experiment. Transaction
 * and native-object handling live in mtp.c; no disk image is synthesized. */
#include "native_fs.h"
#ifndef PLAIN_PTP
#define PLAIN_PTP 0
#endif
#include <stdint.h>
typedef uint8_t u8; typedef uint16_t u16; typedef uint32_t u32;
#define REG8(a) (*(volatile u8 *)(a))
#define REG32(a) (*(volatile u32 *)(a))
#define DIR REG8(0xfffff420)
#define DATA REG8(0xfffff421)
#define SEL REG8(0xfffff423)
#define IMR REG32(0xfffff304)
#define IPENDING REG32(0xfffff310)

struct telemetry {u32 magic,polls,i2c_errors,resets,setups,cbws,scsi,tx,rx,saved_imr,imr,sr,exit,done,phase,configuration,errors,pending_seen,fs_status,fs_files,fs_clusters;};
#define T (*(volatile struct telemetry *)0x3e000)
static u8 configuration,address_pending,address_value,control_status,ctrl_zlp;
static const u8 *ctrl_source;static u16 ctrl_left;
static u8 ctrlbuf[128] __attribute__((aligned(2))),halt_in,halt_out,cancel_left;
static const u8 devdesc[]={18,1,0x10,1,0,0,0,8,0x1e,8,PLAIN_PTP?0xfd:0xfe,0xbd,0,1,1,2,3,1};
/* Generic EP0 on D11 is index2/3; bulk EP1 index4/5; interrupt EP2 index6/7. */
static const u8 cfgdesc[]={9,2,39,0,1,1,0,0x80,50,9,4,0,0,3,6,1,1,4,7,5,0x81,2,8,0,0,7,5,1,2,8,0,0,7,5,0x82,3,8,0,16};
#include "mtp.h"
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
static void reset(void){T.resets++;configuration=0;address_pending=control_status=0;ctrl_left=0;ctrl_zlp=0;halt_in=halt_out=0;regwrite(0xd1,0x80);regwrite(0xd8,0);mtp_reset();clear_fifo(4);clear_fifo(5);clear_fifo(7);}
static void ctrl(const u8*p,u16 n,u16 requested){ctrl_source=p;ctrl_left=n<requested?n:requested;ctrl_zlp=(ctrl_left<requested&&(ctrl_left&7)==0);control_status=0;}
static void stall_control(void){regwrite(0x42,1);regwrite(0x43,1);ctrl_left=0;ctrl_zlp=control_status=0;}
static void setup(const u8 *s){u8 type=s[0],r=s[1];u16 value=le16(s+2),index=le16(s+4),len=le16(s+6);T.setups++;ctrl_left=0;ctrl_zlp=control_status=cancel_left=0;
 if(type==0x80&&r==6){u8 kind=value>>8,id=value;
  if(kind==1&&id==0){ctrl(devdesc,sizeof devdesc,len);return;}
  if(kind==2&&id==0){ctrl(cfgdesc,sizeof cfgdesc,len);return;}
  if(kind==3){if(id==0xee&&!PLAIN_PTP){static const u8 os[]={18,3,'M',0,'S',0,'F',0,'T',0,'1',0,'0',0,'0',0,1,0};ctrl(os,sizeof os,len);return;}if(id==0){ctrlbuf[0]=4;ctrlbuf[1]=3;ctrlbuf[2]=9;ctrlbuf[3]=4;ctrl(ctrlbuf,4,len);return;}const char *text=id==1?"AlphaSmart prototype":id==2?(PLAIN_PTP?"AlphaSmart Files PTP":"AlphaSmart MTP"):id==3?(PLAIN_PTP?"AS3KPTP1":"AS3KMTP1"):id==4?(PLAIN_PTP?"PTP":"MTP"):0;if(text){u8 n=2;while(*text&&n<62){ctrlbuf[n++]=*text++;ctrlbuf[n++]=0;}ctrlbuf[0]=n;ctrlbuf[1]=3;ctrl(ctrlbuf,n,len);return;}}
 }
 if(type==0&&r==5&&value<128&&index==0&&len==0){address_pending=1;address_value=value;control_status=1;return;}
 if(type==0&&r==9&&value<=1&&index==0&&len==0){configuration=value;regwrite(0xd8,value?3:0);halt(1,0);halt(0,0);mtp_reset();clear_fifo(4);clear_fifo(5);clear_fifo(7);control_status=1;return;}
 if(type==0x80&&r==8&&value==0&&index==0&&len==1){ctrlbuf[0]=configuration;ctrl(ctrlbuf,1,len);return;}
 if((type==0x80||type==0x81||type==0x82)&&r==0&&value==0&&len==2){ctrlbuf[0]=type==0x82?(index==0x81?halt_in:index==1?halt_out:0):0;ctrlbuf[1]=0;ctrl(ctrlbuf,2,len);return;}
 if(type==2&&(r==1||r==3)&&value==0&&len==0&&(index==0x81||index==1)){halt(index==0x81,r==3);control_status=1;return;}
 if(type==0x21&&r==0x64&&len==6){cancel_left=6;mtp_reset();clear_fifo(4);clear_fifo(5);return;}
 if(type==0x21&&r==0x66&&len==0){mtp_reset();clear_fifo(4);clear_fifo(5);control_status=1;return;}
 if(type==0xa1&&r==0x67&&len>=4){ctrlbuf[0]=4;ctrlbuf[1]=0;ctrlbuf[2]=1;ctrlbuf[3]=0x20;ctrl(ctrlbuf,4,len);return;}
 /* Microsoft OS 1.0 compatible-ID descriptor for Windows MTP binding. */
 if(!PLAIN_PTP&&type==0xc0&&r==1&&index==4){static const u8 os[]={40,0,0,0,0,1,4,0,1,0,0,0,0,0,0,0,0,1,'M','T','P',0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0};ctrl(os,sizeof os,len);return;}
 if(type==0x81&&r==10&&value==0&&index==0&&len==1){ctrlbuf[0]=0;ctrl(ctrlbuf,1,len);return;}
 if(type==1&&r==11&&value==0&&index==0&&len==0){control_status=1;return;}
 stall_control();
}
static void control_poll(void){u8 p[8];if(address_pending&&control_status==2&&!full(3)){regwrite(0xd1,0x80|address_value);address_pending=0;control_status=0;}
 if(full(2)){u8 status=last(2);if(status&0x20){cmd(2);cmd(0xf1);cmd(3);cmd(0xf1);}u8 n=receive(2,p);if((status&0x20)&&n==8)setup(p);else if(cancel_left){cancel_left=0;control_status=1;}}
 if((ctrl_left||ctrl_zlp||control_status==1)&&!full(3)){if(ctrl_left){u8 n=ctrl_left>8?8:ctrl_left;transmit(3,ctrl_source,n);ctrl_source+=n;ctrl_left-=n;}else if(ctrl_zlp){transmit(3,ctrlbuf,0);ctrl_zlp=0;}else if(control_status==1){transmit(3,ctrlbuf,0);control_status=2;}}
}
static void bulk_poll(void){u8 p[8];if(!configuration)return;
 if(mtp_can_receive()&&full(5)){(void)last(5);u8 n=receive(5,p);mtp_receive(p,n);}
 if(mtp_has_output()&&!full(4)){int n=mtp_transmit(p);if(n>=0)transmit(4,p,n);}
 if(mtp_has_event()&&!full(7)){int n=mtp_event(p);if(n>=0)transmit(7,p,n);}
}
void msc_main(void){u8 saved_dir=DIR,saved_data=DATA,saved_sel=SEL;u32 saved=IMR;T.saved_imr=saved;IMR=saved|0x00100000;T.imr=IMR;u16 sr;__asm__ volatile("move.w %%sr,%0":"=d"(sr));T.sr=sr;
 if(mtp_init()){T.fs_status=0xffffffffu;T.errors++;T.magic=0x4641494c;for(;;)__asm__ volatile("nop");}T.fs_status=1;
 DATA&=~6u;SEL|=6;lines(1,1);
 cmd(0xf3);start();put(0x34);put(0x91);put(3);stop();regwrite(0xd1,0x80);regwrite(0xd8,0);T.magic=0x4d534331;
 while(!T.exit){T.polls++;T.pending_seen|=IPENDING;u16 pending=irq();if(pending&0x4000)reset();control_poll();bulk_poll();T.phase=mtp_phase();T.configuration=configuration;}
 cmd(0xf3);start();put(0x34);put(0x81);put(3);stop();regwrite(0xd8,0);DATA=saved_data;SEL=saved_sel;DIR=saved_dir;IMR=saved;mtp_reset();T.done=0x444f4e45;for(;;)__asm__ volatile("nop");
}
