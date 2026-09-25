import json
import sys

print(json.dumps({"ok": True, "stub": True, "argv": sys.argv[1:]}))
