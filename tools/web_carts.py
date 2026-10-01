#!/usr/bin/env python3
"""Copy built carts into the web build and write carts.json (title from the MEI1 header).
usage: web_carts.py OUT_DIR cart.mei..."""
import json, os, shutil, sys

out = sys.argv[1]
os.makedirs(out, exist_ok=True)
entries = []
for path in sys.argv[2:]:
    data = open(path, "rb").read()
    name = os.path.basename(path)
    title = os.path.splitext(name)[0]
    if data[4:8] == b"MEI1":
        title = data[8:40].split(b"\0")[0].decode("utf-8", "replace") or title
    shutil.copyfile(path, os.path.join(out, name))
    entries.append({"file": name, "title": title, "size": len(data)})
json.dump(entries, open(os.path.join(out, "carts.json"), "w"), indent=1)
print(f"{len(entries)} carts -> {out}")
