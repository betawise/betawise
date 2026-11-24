#!/usr/bin/env python3
"""Run the existing RAM guest with USB/IP, waiting for the one-shot root checker."""
import asyncio, contextlib, importlib.util, json, logging
from pathlib import Path
import run as runner
spec=importlib.util.spec_from_file_location('asma3k_usbip',runner.ROOT/'mame-usb/scripts/alphasmart/usbip.py')
bridge=importlib.util.module_from_spec(spec);spec.loader.exec_module(bridge)
async def execute(out,port):
 await runner.waitfile(out/'ready')
 reader,writer=await asyncio.open_connection('127.0.0.1',port)
 wire=runner.Host(reader,writer,out)
 class LoggedChip(bridge.Chip):
  async def request(self,op,ep=0,data=b''):
   async with self.lock:return await wire.request(op,ep,data)
 chip=LoggedChip(reader,writer);export=bridge.Export(chip);server=None
 try:
  await chip.request(1);await export.discover()
  server=await asyncio.start_server(export.client,'127.0.0.1',3241)
  (out/'vhci-ready.json').write_text(json.dumps({'port':3241,'busid':'1-1','vid':'081e','pid':'bdff'})+'\n')
  print('READY: run sudo python3 '+str(runner.HERE/'vhci_check.py')+' '+str(out),flush=True)
  await runner.waitfile(out/'host-result.json',720)
  result=json.loads((out/'host-result.json').read_text())
  assert result['result']=='PASS',result
  await runner.waitfile(out/'host-detached',30)
  await chip.request(6);(out/'stop').write_text('stop\n');await runner.waitfile(out/'restored')
  guest=json.loads((out/'guest.json').read_text())
  assert guest['rom_gpio_writes']==guest['rom_usb_reads']==0
  assert guest['telemetry'][2]==0 and guest['telemetry'][17]&0x100000
  (out/'results.json').write_text(json.dumps({'result':'PASS','host':result,'guest':guest,'packet_requests':wire.count},indent=2)+'\n')
  print('PASS Linux VHCI + usb-storage + FAT filesystem; guest restored',flush=True)
 finally:
  if server:server.close();await server.wait_closed()
  with contextlib.suppress(Exception):await chip.request(6)
  (out/'stop').write_text('stop\n')
  with contextlib.suppress(Exception):await runner.waitfile(out/'restored',5)
  (out/'quit').write_text('quit\n');wire.log.close();writer.close();await writer.wait_closed()
if __name__=='__main__':
 logging.basicConfig(level=logging.INFO)
 runner.execute=execute;runner.main()
