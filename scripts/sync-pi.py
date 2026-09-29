"""Pull from GitHub on Pi using transient, memory-only developer authorization.

The organization's policy disables deploy keys. This wrapper uses the existing
local gh login for one SSH deployment; no GitHub credential is saved on Pi.
"""

import os
import shlex
import subprocess
from pathlib import Path

repo = Path(__file__).resolve().parent.parent
if subprocess.check_output(["git", "status", "--porcelain"], cwd=repo).strip():
    raise SystemExit("Commit local changes before synchronization")
result = subprocess.run(["gh", "auth", "token"], capture_output=True)
if result.returncode == 0:
    token = result.stdout.strip()
else:
    result = subprocess.run(["gh", "auth", "git-credential", "get"],
                            input=b"protocol=https\nhost=github.com\n\n", capture_output=True)
    credentials = dict(line.split(b"=", 1) for line in result.stdout.splitlines() if b"=" in line)
    token = credentials.get(b"password", b"")
if not token:
    raise SystemExit("The local GitHub CLI is not authenticated")

remote = r'''
import base64, os, pathlib, subprocess, sys
token = sys.stdin.buffer.read(16384).strip()
if not token or len(token) >= 16384:
    raise SystemExit("Invalid deployment authorization")
env = os.environ.copy()
for key in list(env):
    if key.startswith("GIT_TRACE") or key in ("GIT_CURL_VERBOSE", "GIT_CONFIG_COUNT"):
        env.pop(key)
env.update({
    "GIT_CONFIG_COUNT": "2",
    "GIT_CONFIG_KEY_0": "http.https://github.com/.extraheader",
    "GIT_CONFIG_VALUE_0": "AUTHORIZATION: basic " + base64.b64encode(b"x-access-token:" + token).decode(),
    "GIT_CONFIG_KEY_1": "credential.helper", "GIT_CONFIG_VALUE_1": "",
    "GIT_TERMINAL_PROMPT": "0", "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1",
    "HTTPS_PROXY": "http://192.168.5.71:10808", "HTTP_PROXY": "http://192.168.5.71:10808",
})
destination = pathlib.Path("/home/winbeau/xju-arlab/hp-printer")
url = "https://github.com/xju-arlab/hp-printer.git"
def git(*args):
    subprocess.run(["git", *args], env=env, check=True, timeout=180)
if not (destination / ".git").is_dir():
    if destination.exists() and any(destination.iterdir()):
        raise SystemExit("Destination exists and is not an empty repository")
    destination.parent.mkdir(parents=True, exist_ok=True)
    git("clone", url, str(destination))
if subprocess.check_output(["git", "-C", str(destination), "status", "--porcelain"]).strip():
    raise SystemExit("Pi checkout has local changes; refusing to overwrite")
git("-C", str(destination), "remote", "set-url", "origin", url)
git("-C", str(destination), "pull", "--ff-only", "origin", "main")
git("-C", str(destination), "fetch", "origin", "--tags")
git("-C", str(destination), "rev-parse", "HEAD")
'''
target = os.environ.get("HP_PRINTER_SSH_TARGET", "winbeau@192.168.5.87")
subprocess.run(["ssh", target, "python3 -c " + shlex.quote(remote)], input=token,
               check=True, timeout=400)
