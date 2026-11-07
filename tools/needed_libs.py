#!/usr/bin/env python3
"""Print the libraries of <dir>/libs.aarch64 that <dir>/love needs, directly or through each other.

  python3 tools/needed_libs.py /path/to/bin     (the folder holding `love` and `libs.aarch64`)

Everything `love` needs that is NOT in libs.aarch64 (SDL2, OpenAL, libc ...) is expected from muOS itself.
Needs `readelf` (binutils).
"""
import collections
import os
import re
import subprocess
import sys

root = sys.argv[1]
libdir = os.path.join(root, "libs.aarch64")
have = set(os.listdir(libdir))


def needed(path):
    env = os.environ.copy(); env["LC_ALL"] = "C"; env["LANG"] = "C"
    out = subprocess.run(["readelf", "-d", path], capture_output=True, text=True, check=True, env=env).stdout
    return re.findall(r"Shared library: \[([^\]]+)\]", out)


seen, queue = collections.OrderedDict(), [os.path.join(root, "love")]
while queue:
    for n in needed(queue.pop(0)):
        if n in have and n not in seen:
            seen[n] = 1
            queue.append(os.path.join(libdir, n))
if seen:
    print("\n".join(seen))
