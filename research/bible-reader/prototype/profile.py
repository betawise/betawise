"""Invalidate shared objects/resources when a reader/translation profile changes."""
from pathlib import Path
import json,sys
path=Path(sys.argv[1]);data=json.dumps(sys.argv[2:],separators=(',',':'))+'\n'
if not path.exists()or path.read_text()!=data:path.write_text(data)
