#!/usr/bin/env python3
"""Состояние DOLI producer-ноды текстом — для cron, который шлёт stdout в чат (Discord, Telegram…).

  doli-status.py daily  — сводка, первая строка 🟢/🟡/🔴 (раз в день)
  doli-status.py watch  — молчит, пока всё нормально; пишет, когда проблема появилась,
                          изменилась или ушла, и один раз — о новом релизе (раз в 10 минут).

Только чтение, без секретов. Нужны: docker (контейнер doli-node), python3 3.8+.
Переменные окружения: DOLI_ADDRESS и DOLI_PUBKEY (из `doli info`), DOLI_NODE_DIR (как NODE_DIR в .env).
"""
import datetime
import json
import os
import subprocess
import sys
import time
import urllib.request

CONTAINER = "doli-node"
RPC = "http://127.0.0.1:8500"
REF_RPC = "https://explorer.doli.network/api/mainnet/seed1"   # высота сети для сравнения
RELEASES = "https://api.github.com/repos/doli-network/doli/releases/latest"
ADDRESS = os.environ.get("DOLI_ADDRESS", "")
PUBKEY = os.environ.get("DOLI_PUBKEY", "")
DATA = os.environ.get("DOLI_NODE_DIR", "/srv/doli/node")
STATE = os.path.expanduser(os.environ.get("DOLI_STATE", "~/.local/state/doli_state.json"))
LAG_MAX = 30          # блоков (~5 мин)
PEERS_MIN = 3
MEM_PCT_MAX = 85
MISSED_MIN_MAX = 6    # 90% от 60 минут эпохи
UNIT = 1e8

DIRECT = urllib.request.build_opener(urllib.request.ProxyHandler({}))   # localhost — мимо HTTP(S)_PROXY
VIA_ENV = urllib.request.build_opener()                                  # интернет — с прокси из окружения, если есть


def rpc(method, params=None, url=RPC, opener=DIRECT):
    body = json.dumps({"jsonrpc": "2.0", "method": method, "params": params or {}, "id": 1}).encode()
    if url == RPC:   # через контейнер: не зависит от того, опубликован ли RPC на хосте
        out = sh("docker", "exec", CONTAINER, "curl", "-s", "-m", "15", "-X", "POST", RPC,
                 "-H", "Content-Type: application/json", "-d", body.decode())
        try:
            d = json.loads(out)
        except Exception:
            return None
        return d.get("result") if "result" in d else {"_error": d.get("error", {}).get("message", "?")}
    req = urllib.request.Request(url, body, {"Content-Type": "application/json"})
    try:
        with opener.open(req, timeout=15) as r:
            d = json.load(r)
    except Exception:
        return None
    return d.get("result") if "result" in d else {"_error": d.get("error", {}).get("message", "?")}


def sh(*cmd, timeout=20):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip() if r.returncode == 0 else None
    except Exception:
        return None


def num(n):
    return f"{int(n):,}".replace(",", " ")


def doli(v):
    return f"{v / UNIT:.4f}".rstrip("0").rstrip(".")


def mem_bytes(s):
    s = s.strip()
    for suf, k in (("GiB", 2**30), ("MiB", 2**20), ("KiB", 2**10), ("B", 1)):
        if s.endswith(suf):
            return float(s[: -len(suf)]) * k
    return 0.0


def latest_release():
    try:
        req = urllib.request.Request(RELEASES, headers={"User-Agent": "doli-status"})
        with VIA_ENV.open(req, timeout=15) as r:
            return json.load(r).get("tag_name")
    except Exception:
        return None


def collect():
    s = {"problems": [], "info": []}
    p = s["problems"]
    st = sh("docker", "inspect", "-f", "{{.State.Status}} {{if .State.Health}}{{.State.Health.Status}}{{end}} {{.RestartCount}}", CONTAINER)
    if not st:
        p.append("контейнер doli-node не найден")
        return s
    parts = st.split()
    s["state"], s["health"], s["restarts"] = parts[0], (parts[1] if len(parts) > 2 else "-"), int(parts[-1])
    if s["state"] != "running":
        p.append(f"контейнер {s['state']}")
        return s
    if s["health"] == "unhealthy":
        p.append("healthcheck: unhealthy")

    mem = sh("docker", "stats", "--no-stream", "--format", "{{.MemUsage}}", CONTAINER)
    if mem and "/" in mem:
        used, limit = (mem_bytes(x) for x in mem.split("/"))
        s["mem"] = (used, limit)
        if limit and used / limit * 100 > MEM_PCT_MAX:
            p.append(f"память {used / 2**30:.1f}/{limit / 2**30:.0f} GiB (>{MEM_PCT_MAX}%) — возможен gossip flood")
    du = sh("du", "-sb", DATA)
    s["disk"] = int(du.split()[0]) if du else None

    chain, net, node = rpc("getChainInfo"), rpc("getNetworkInfo"), rpc("getNodeInfo")
    if not chain or "_error" in chain:
        p.append("RPC ноды не отвечает")
        return s
    s["height"], s["version"] = chain["bestHeight"], (node or {}).get("version", chain.get("version"))
    s["peers"] = (net or {}).get("peerCount")
    if s["peers"] is not None and s["peers"] < PEERS_MIN:
        p.append(f"пиров {s['peers']} (<{PEERS_MIN})")
    ref = rpc("getChainInfo", url=REF_RPC, opener=VIA_ENV)
    if ref and "bestHeight" in ref:
        s["net_height"] = ref["bestHeight"]
        if ref["bestHeight"] - s["height"] > LAG_MAX:
            p.append(f"отстаёт на {num(ref['bestHeight'] - s['height'])} блоков (сеть {num(ref['bestHeight'])})")

    s["balance"] = (rpc("getBalance", {"address": ADDRESS}) or {}) if ADDRESS else {}
    prod = rpc("getProducer", [PUBKEY]) if PUBKEY else None
    if prod and "_error" not in prod:
        s["producer"] = prod
        if prod.get("status") not in ("active", "pending"):
            p.append(f"producer: статус {prod.get('status')}")
        if prod.get("status") == "active":
            att = rpc("getAttestationStats") or {}
            me = next((x for x in att.get("producers", []) if x.get("publicKey") == PUBKEY), None)
            s["attest"] = me
            s["epoch"] = att.get("epoch")
            if me is None:
                p.append("producer active, но не в attestation-статистике эпохи")
            else:
                missed = me["totalMinutes"] - me["attestedMinutes"]
                if missed > MISSED_MIN_MAX:
                    p.append(f"attestation: пропущено {missed} мин в эпохе {att.get('epoch')} — награда за эпоху под угрозой")
                if not me.get("hasBls"):
                    p.append("attestation: hasBls=false — см. docs/bls-key-recovery.md в репозитории DOLI")

    s["latest"] = latest_release()
    if s["latest"] and s.get("version") and s["latest"].lstrip("v") != str(s["version"]).lstrip("v"):
        s["info"].append(f"новый релиз {s['latest']} (у нас {s['version']}) — обновить: README, раздел «Обновление»")
    return s


def load_state():
    try:
        with open(STATE) as f:
            return json.load(f)
    except Exception:
        return {}


def save_state(d):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    with open(STATE, "w") as f:
        json.dump(d, f)


def daily(s):
    light = "🔴" if s["problems"] else ("🟡" if s["info"] else "🟢")
    today = datetime.datetime.now().strftime("%d.%m %H:%M")
    out = [f"{light} **DOLI** · {today}"]
    out += [f"• {x}" for x in s["problems"] + s["info"]]
    if "height" in s:
        net = f" (сеть {num(s['net_height'])})" if "net_height" in s else ""
        out.append(f"Нода: v{s.get('version')} · высота {num(s['height'])}{net} · пиры {s.get('peers')}")
    if "mem" in s:
        used, limit = s["mem"]
        disk = f" · диск {s['disk'] / 2**20:.0f} MB" if s.get("disk") else ""
        out.append(f"Ресурсы: RAM {used / 2**20:.0f} MiB / {limit / 2**30:.0f} GiB{disk} · рестартов {s.get('restarts')}")
    b = s.get("balance") or {}
    if b:
        out.append(f"Кошелёк: …{ADDRESS[-6:]} · {doli(b.get('confirmed', 0))} DOLI"
                   f" (bonded {doli(b.get('bonded', 0))}, immature {doli(b.get('immature', 0))})")
    pr = s.get("producer")
    if pr:
        out.append(f"Producer: {pr.get('status')} · bonds {pr.get('bondCount')} · с блока {num(pr.get('registrationHeight', 0))}")
        a = s.get("attest")
        if a:
            out.append(f"Attestation (эпоха {s.get('epoch')}): {a['attestedMinutes']}/{a['totalMinutes']} мин"
                       f" · {'qualified ✓' if a.get('qualified') else 'not qualified'}")
    elif "height" in s:
        out.append("Producer: не зарегистрирован (ждём faucet)")
    return "\n".join(out)


def watch(s):
    st = load_state()
    prev = st.get("problems", [])
    cur = s["problems"]
    lines = []
    if cur and cur != prev:
        lines.append("🔴 **DOLI**: проблема")
        lines += [f"• {x}" for x in cur]
    elif prev and not cur:
        lines.append("🟢 **DOLI**: снова в норме (было: " + "; ".join(prev) + ")")
    if s.get("restarts") is not None and st.get("restarts") is not None and s["restarts"] > st["restarts"]:
        lines.append(f"🟡 **DOLI**: контейнер перезапускался ({st['restarts']} → {s['restarts']})")
    if s["info"] and s.get("latest") != st.get("release_notified"):
        lines += [f"🟡 **DOLI**: {x}" for x in s["info"]]
        st["release_notified"] = s.get("latest")
    st["problems"] = cur
    if s.get("restarts") is not None:
        st["restarts"] = s["restarts"]
    st["checked"] = int(time.time())
    save_state(st)
    return "\n".join(lines)


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "daily"
    data = collect()
    text = daily(data) if mode == "daily" else watch(data)
    if text:
        print(text)
