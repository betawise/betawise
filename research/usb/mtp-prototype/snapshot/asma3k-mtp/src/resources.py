"""Bound the temporary emulator, and log host resource use at one-second intervals."""
from pathlib import Path
import asyncio,fcntl,json,os,resource,time
RSS_LIMIT=512*1024 # KiB

def limits():
 fd=os.open("/tmp/alphasmart-usb-test-"+str(os.getuid())+".lock",os.O_CREAT|os.O_RDWR,0o600)
 fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);os.set_inheritable(fd,True)
 os.nice(10)
 resource.setrlimit(resource.RLIMIT_AS,(1536*1024*1024,1536*1024*1024))
async def monitor(proc,out):
 previous=None
 with(out/'resources.jsonl').open('w')as log:
  while proc.poll()is None:
   try:
    status=dict(line.split(':',1)for line in (Path('/proc')/str(proc.pid)/'status').read_text().splitlines()if ':'in line)
    stat=(Path('/proc')/str(proc.pid)/'stat').read_text().split();ticks=int(stat[13])+int(stat[14]);now=time.monotonic();mem=dict(line.split(':',1)for line in Path('/proc/meminfo').read_text().splitlines())
    row={'at':now,'pid':proc.pid,'rss_kib':int(status.get('VmRSS','0 kB').split()[0]),'swap_kib':int(status.get('VmSwap','0 kB').split()[0]),'available_kib':int(mem['MemAvailable'].split()[0]),'cpu_percent':None if previous is None else 100*(ticks-previous[1])/os.sysconf('SC_CLK_TCK')/(now-previous[0])};previous=(now,ticks);log.write(json.dumps(row)+'\n');log.flush()
    if row['rss_kib']>RSS_LIMIT or row['available_kib']<768*1024:
     proc.kill();raise RuntimeError('Stopped emulator at resource safety limit: '+json.dumps(row))
   except FileNotFoundError:return
   await asyncio.sleep(1)
