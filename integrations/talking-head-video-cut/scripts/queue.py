# -*- coding: utf-8 -*-
"""排隊渲染多支，一支跑完再跑下一支"""
import os, sys, subprocess, time
W = r"C:\videoedit\_whisper"
PY = os.path.join(W, ".venv", "Scripts", "python.exe")
for tag in sys.argv[1:]:
    t0 = time.time()
    print(">>>", tag, flush=True)
    p = subprocess.run([PY, os.path.join(W, "long_run.py"), tag], cwd=W,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    for ln in (p.stdout or "").splitlines():
        if ln.strip(): print("   ", ln, flush=True)
    if p.returncode:
        print("FAIL", tag); print((p.stderr or "")[-1500:], flush=True)
    else:
        print("   %s 完成 %.1f 分" % (tag, (time.time()-t0)/60), flush=True)
print("BATCH_DONE", flush=True)
