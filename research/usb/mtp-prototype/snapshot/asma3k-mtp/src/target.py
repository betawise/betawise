"""Resolve only our unique localhost VHCI prototype, including after a reset."""
from pathlib import Path
def target():
 found=[]
 for d in Path('/sys/bus/usb/devices').iterdir():
  try:
   if (d/'idVendor').read_text().strip()=='081e'and(d/'idProduct').read_text().strip()=='bdfe'and(d/'serial').read_text().strip()=='AS3KMTP1'and'vhci_hcd'in str(d.resolve()):found.append((int((d/'busnum').read_text()),int((d/'devnum').read_text())))
  except(FileNotFoundError,NotADirectoryError):pass
 assert len(found)==1,('Expected one VHCI prototype',found)
 return found[0]
