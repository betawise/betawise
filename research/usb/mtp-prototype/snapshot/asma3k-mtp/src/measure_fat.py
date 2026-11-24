#!/usr/bin/env python3
"""Run the unchanged FAT guest using the cached-register measurement harness."""
from pathlib import Path
import asyncio,importlib.util,subprocess,sys
import resources
ROOT=Path(__file__).resolve().parents[3]
spec=importlib.util.spec_from_file_location('fat_runner',ROOT/'.research-work/asma3k-msc-fs/src/run.py');fs=importlib.util.module_from_spec(spec);sys.path.insert(0,str(ROOT/'.research-work/asma3k-msc-fs/src'));spec.loader.exec_module(fs)
out=Path(sys.argv[1]).resolve();original=subprocess.Popen;watches=[]
def launch(*args,**kw):
 kw['preexec_fn']=resources.limits;proc=original(*args,**kw);watches.append(asyncio.create_task(resources.monitor(proc,out)));return proc
async def main():
 subprocess.Popen=launch
 try:await fs.execute(out,False)
 finally:
  for task in watches:task.cancel()
  await asyncio.gather(*watches,return_exceptions=True)
asyncio.run(main())
