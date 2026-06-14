#!/usr/bin/env python3
"""
runner.py — the per-minute executor. Runs every job in jobs.json, writes the bulletproof
board (device/bulletproof.json), a dashboard (views/dashboard.html), and the next action
(device/next_action.txt). BULLETPROOF = all integrity-gate jobs green. A cron `* * * * *`
invokes this; the PreToolUse gate reads bulletproof.json to allow/deny phase tools.
"""
import os, json, subprocess, time
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
DEVICE = os.path.join(ROOT, "device"); VIEWS = os.path.join(ROOT, "views")
for d in (DEVICE, VIEWS): os.makedirs(d, exist_ok=True)

def run():
    man = json.load(open(os.path.join(HERE, "jobs.json")))
    results = []
    for j in man["jobs"]:
        try:
            r = subprocess.run(j["check"], shell=True, cwd=HERE, capture_output=True, text=True, timeout=60)
            green = r.returncode == 0
            msg = (r.stdout or r.stderr).strip().splitlines()[-1][:120] if (r.stdout or r.stderr).strip() else ("ok" if green else "fail")
        except Exception as e:
            green, msg = False, f"runner error: {e}"[:120]
        results.append({**{k: j[k] for k in ("id", "kind", "group", "gate", "nudge")}, "green": green, "msg": msg})

    integ = [x for x in results if x["kind"] == "integrity"]
    ig_green = sum(1 for x in integ if x["green"])
    bulletproof = ig_green == len(integ) and len(integ) > 0
    prog = [x for x in results if x["kind"] == "progress"]
    pg_green = sum(1 for x in prog if x["green"])
    board = {"ts": int(time.time()), "bulletproof": bulletproof,
             "integrity": {"green": ig_green, "total": len(integ)},
             "progress": {"green": pg_green, "total": len(prog)},
             "jobs": results}
    json.dump(board, open(os.path.join(DEVICE, "bulletproof.json"), "w"), indent=2)

    # next action: first red integrity (repair first) else first red progress (advance)
    nxt = next((x for x in integ if not x["green"]), None) or next((x for x in prog if not x["green"]), None)
    action = (f"[REPAIR] {nxt['id']}: {nxt['msg']}" if nxt and nxt["kind"] == "integrity"
              else f"[ADVANCE] {nxt['nudge']}" if nxt else "ALL GREEN — project complete")
    open(os.path.join(DEVICE, "next_action.txt"), "w").write(action + "\n")

    # dashboard
    def row(x):
        c = "#3fb950" if x["green"] else "#ff5555"
        return f"<tr><td style='color:{c}'>{'●' if x['green'] else '○'}</td><td>{x['id']}</td><td>{x['group']}</td><td class=m>{x['msg']}</td></tr>"
    rows = "".join(row(x) for x in results)
    bp = "#3fb950" if bulletproof else "#ff5555"
    html = f"""<!doctype html><meta charset=utf-8><meta http-equiv=refresh content=60><title>bulletproof board</title>
<style>body{{background:#0e1116;color:#e6edf3;font:12px ui-monospace,monospace;padding:18px}}
h1{{font-size:16px}}table{{border-collapse:collapse;width:100%}}td{{padding:2px 8px;border-bottom:1px solid #222}}.m{{color:#9aa7b4}}
.big{{font-size:22px;color:{bp}}}</style>
<h1>XCZU19EG — bulletproof board <span class=big>{'BULLETPROOF' if bulletproof else 'RED'}</span></h1>
<p>integrity {ig_green}/{len(integ)} · progress {pg_green}/{len(prog)} · next: {action}</p>
<table>{rows}</table>"""
    open(os.path.join(VIEWS, "dashboard.html"), "w").write(html)

    print(f"runner: {len(results)} jobs · integrity {ig_green}/{len(integ)} · progress {pg_green}/{len(prog)} · "
          f"{'BULLETPROOF' if bulletproof else 'RED'}")
    print(f"  next: {action}")
    return 0 if bulletproof else 1

if __name__ == "__main__":
    import sys; sys.exit(run())
