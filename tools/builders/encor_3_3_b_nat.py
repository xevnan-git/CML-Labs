# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6"]
# ///
"""Build configs + topology files for the ENCOR 3.3.b NAT/PAT lab pair (learn-nat + ts-nat).

One source of truth for every variant. After running, run tools/sync_notes.py.
  learn boot  ("clean"): addressing and static routing up, no NAT (ISP1 has no route to 192.168.x, so nothing works)
  final       ("final"): learn end state = ts design: PAT for both inside LANs on one pool address (198.51.100.1),
                         SRV1 published by port forwarding on 198.51.100.14 (80 -> 80, 2222 -> 22),
                         outside ACL on R1 e0/2 written against global addresses
  ts boot     ("ts"):    final + the injected faults (all on R1, see FAULTS)
ISP1 routes the customer block 198.51.100.0/28 to R1 and nothing else. SRV1 runs a web server and a monitoring
heartbeat (ping PC2 every 10 s), so it always holds a dynamic translation: that makes pool exhaustion deterministic.
Usage: uv run tools/builders/encor_3_3_b_nat.py [--chunks DIR]   (DIR: both labs as JSON for the MCP;
       each lab is 5 licensed nodes, so a chunk is the whole lab)
"""
import json, sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
TOPIC = REPO / "labs/encor/3-infrastructure/nat"
LEARN, TS = TOPIC / "learn-nat", TOPIC / "ts-nat"
LEARN_YAML, TS_YAML = "encor-3.3.b-nat-learn-nat.yaml", "encor-3.3.b-nat-ts-nat.yaml"

BASE = """hostname {h}
no ip domain lookup
ip domain name lab.local
enable secret cisco
username cisco privilege 15 secret cisco
!
"""
LINES = """line con 0
 exec-timeout 0 0
 logging synchronous
 privilege level 15
line vty 0 4
 login local
 transport input telnet ssh
!
end
"""
PHYS = [f"Ethernet0/{i}" for i in range(4)]

# interface -> (ip mask, description); unlisted Ethernet0/x are shut
INTS = {
 "R1": [("Loopback0", "10.255.255.1 255.255.255.255", None),
        ("Ethernet0/0", "192.168.10.1 255.255.255.0", "VLAN 10 staff LAN (PC1)"),
        ("Ethernet0/1", "192.168.20.1 255.255.255.0", "VLAN 20 server LAN (SRV1)"),
        ("Ethernet0/2", "203.0.113.1 255.255.255.0", "ISP1 e0/0 (internet)")],
 "ISP1": [("Loopback0", "10.255.255.101 255.255.255.255", None),
          ("Ethernet0/0", "203.0.113.101 255.255.255.0", "customer R1 e0/2"),
          ("Ethernet0/1", "192.0.2.1 255.255.255.0", "internet host LAN (PC2)")],
}
# NAT role per interface (final design); the faults can swap them
NAT_ROLE = {("R1", "Ethernet0/0"): "inside", ("R1", "Ethernet0/1"): "inside", ("R1", "Ethernet0/2"): "outside"}
OUTSIDE_ACL_IF = ("R1", "Ethernet0/2")

ROUTING = {
 "R1": "ip route 0.0.0.0 0.0.0.0 203.0.113.101 name DEFAULT-VIA-ISP1\n!\n",
 "ISP1": "ip route 198.51.100.0 255.255.255.240 203.0.113.1 name CUSTOMER-BLOCK\n!\n",
}

# R1's NAT (final = learn end state = ts design). After the interfaces.
NAT = """ip access-list standard NAT-INSIDE
 10 permit 192.168.10.0 0.0.0.255
 20 permit 192.168.20.0 0.0.0.255
ip access-list extended OUTSIDE-IN
 10 permit tcp any host 198.51.100.14 eq www
 20 permit tcp any host 198.51.100.14 eq 2222
 30 permit icmp any any
 40 permit tcp any any established
 50 deny ip any any
!
ip nat pool NAT-POOL 198.51.100.1 198.51.100.1 prefix-length 28
ip nat inside source list NAT-INSIDE pool NAT-POOL overload
ip nat inside source static tcp 192.168.20.10 80 198.51.100.14 80 extendable
ip nat inside source static tcp 192.168.20.10 22 198.51.100.14 2222 extendable
!
"""

# Troubleshooting faults, all on R1: (find, replace) on R1's final config text.
# Numbered as in ts-nat/solution/README.md (the order a learner usually meets them).
FAULTS = [
 # Fault 1 staff LAN and ISP interfaces have inside/outside swapped: nothing is translated toward the ISP
 ("interface Ethernet0/0\n description VLAN 10 staff LAN (PC1)\n ip address 192.168.10.1 255.255.255.0\n ip nat inside\n",
  "interface Ethernet0/0\n description VLAN 10 staff LAN (PC1)\n ip address 192.168.10.1 255.255.255.0\n ip nat outside\n"),
 ("ip address 203.0.113.1 255.255.255.0\n ip nat outside\n", "ip address 203.0.113.1 255.255.255.0\n ip nat inside\n"),
 # Fault 2 staff wildcard too narrow: /29 covers .0-.7, PC1 is .10, so PC1 isn't translated
 (" 10 permit 192.168.10.0 0.0.0.255\n", " 10 permit 192.168.10.0 0.0.0.7\n"),
 # Fault 3 one-address pool without overload: SRV1's heartbeat holds it, PC1 is a pool miss
 ("pool NAT-POOL overload\n", "pool NAT-POOL\n"),
 # Fault 4 pool address outside the block ISP1 routes to R1 (198.51.100.0/28): replies never come back
 ("ip nat pool NAT-POOL 198.51.100.1 198.51.100.1 prefix-length 28\n",
  "ip nat pool NAT-POOL 198.51.100.17 198.51.100.17 prefix-length 28\n"),
 # Fault 5 web port forward points to port 8080 on SRV1, where nothing listens
 ("static tcp 192.168.20.10 80 198.51.100.14 80 extendable\n", "static tcp 192.168.20.10 8080 198.51.100.14 80 extendable\n"),
]


def config(h, mode):
    """mode: clean | final | ts (only R1 differs; ISP1 is always final)"""
    out = [BASE.format(h=h)]
    used = set()
    for name, ip, desc in INTS[h]:
        used.add(name)
        s = f"interface {name}\n"
        if desc:
            s += f" description {desc}\n"
        s += f" ip address {ip}\n"
        if mode != "clean" and (h, name) in NAT_ROLE:
            s += f" ip nat {NAT_ROLE[(h, name)]}\n"
        if name.startswith("Ethernet"):
            s += " no shutdown\n"
        out.append(s + "!\n")
    for p in PHYS:
        if p not in used:
            out.append(f"interface {p}\n no ip address\n shutdown\n!\n")
    out.append(ROUTING[h])
    if h == "R1" and mode != "clean":
        out.append(NAT + f"interface {OUTSIDE_ACL_IF[1]}\n ip access-group OUTSIDE-IN in\n!\n")
    out.append(LINES)
    text = "".join(out)
    if h == "R1" and mode == "ts":
        for old, new in FAULTS:
            assert text.count(old) == 1, old
            text = text.replace(old, new)
    return text


PCS = {"PC1": ("192.168.10.10/24", "192.168.10.1"), "SRV1": ("192.168.20.10/24", "192.168.20.1"),
       "PC2": ("192.0.2.10/24", "192.0.2.1")}
# SRV1: busybox-extras httpd on port 80 (sshd runs by default), plus a monitoring heartbeat to PC2 every 10 s
SRV1_EXTRA = ("mkdir -p /srv/www\necho '<h1>SRV1 public web server</h1>' > /srv/www/index.html\n"
              "/usr/sbin/httpd -p 80 -h /srv/www\n"
              "# monitoring heartbeat: one ping to the internet host every 10 seconds\n"
              "(while true; do ping -c 1 -W 1 192.0.2.10 >/dev/null 2>&1; sleep 10; done) &\n")


def pc_config(h):
    ip, gw = PCS[h]
    s = (f"# this is a shell script which will be sourced at boot\nhostname {h}\nUSERNAME=cisco\nPASSWORD=cisco\n"
         f"ip address add {ip} dev eth0\nip link set dev eth0 up\nip route add default via {gw}\n")
    return s + (SRV1_EXTRA if h == "SRV1" else "")


ORDER = ["R1", "ISP1", "PC1", "SRV1", "PC2"]
POS = {"PC1": (-350, -150), "SRV1": (-350, 150), "R1": (0, 0), "ISP1": (350, 0), "PC2": (700, 0)}
LABELS = {
 "R1": "R1  edge (NAT)  cisco/cisco\nLo0   10.255.255.1/32\ne0/0  192.168.10.1/24 (PC1)\ne0/1  192.168.20.1/24 (SRV1)\n"
       "e0/2  203.0.113.1/24  (ISP1)\npublic block 198.51.100.0/28",
 "ISP1": "ISP1  cisco/cisco\nLo0   10.255.255.101/32\ne0/0  203.0.113.101/24 (R1)\ne0/1  192.0.2.1/24     (PC2)",
 "PC1": "PC1  staff  cisco/cisco\neth0 192.168.10.10/24\ngw   192.168.10.1",
 "SRV1": "SRV1  web server  cisco/cisco\neth0 192.168.20.10/24\ngw   192.168.20.1",
 "PC2": "PC2  internet host  cisco/cisco\neth0 192.0.2.10/24\ngw   192.0.2.1",
}
# (a, a's Ethernet0/x, b, b's Ethernet0/x or eth0)
LINKS = [("R1", 0, "PC1", None), ("R1", 1, "SRV1", None), ("R1", 2, "ISP1", 0), ("ISP1", 1, "PC2", None)]


def iol_ifaces(h):
    names = ["Loopback0"] + PHYS  # CML only models Loopback0
    out = []
    for k, n in enumerate(names):
        i = {"id": f"i{k}", "label": n, "type": "loopback" if n.startswith("Loop") else "physical"}
        if not n.startswith("Loop"):
            i["slot"] = PHYS.index(n)
        out.append(i)
    return out


def iface_id(h, eth):
    return next(i["id"] for i in iol_ifaces(h) if i["label"] == f"Ethernet0/{eth}")


def topology(title, description, mode):
    nodes, ids = [], {}
    for k, h in enumerate(ORDER):
        nid = f"n{k}"; ids[h] = nid
        x, y = POS[h]
        n = {"id": nid, "label": h, "x": x, "y": y}
        if h in PCS:
            n.update(node_definition="alpine", image_definition="alpine-base-3-23-3",
                     interfaces=[{"id": "i0", "label": "eth0", "slot": 0, "type": "physical"}],
                     configuration=[{"name": "node.cfg", "content": pc_config(h)}])
        else:
            n.update(node_definition="iol-xe", image_definition="iol-xe-17-18-02", interfaces=iol_ifaces(h),
                     configuration=[{"name": "ios_config.txt", "content": config(h, mode)}])
        nodes.append(n)
    links = [{"id": f"l{k}", "n1": ids[a], "i1": iface_id(a, ia), "n2": ids[b],
              "i2": "i0" if ib is None else iface_id(b, ib)}
             for k, (a, ia, b, ib) in enumerate(LINKS)]
    anns = []
    for h, text in LABELS.items():
        x, y = POS[h]
        anns.append({"type": "text", "text_content": text, "x1": x - 70, "y1": y + 40, "rotation": 0,
                     "text_bold": False, "text_italic": False, "text_size": 10, "text_unit": "pt",
                     "text_font": "monospace", "color": "#5A5A5AFF", "border_color": "#00000000",
                     # CML file format: '' = solid, '2,2' = dotted, '4,2' = dashed (the MCP tool wants words)
                     "border_style": "", "thickness": 1, "z_index": 1})
    return {"lab": {"title": title, "description": description, "notes": "", "version": "0.3.0"},
            "nodes": nodes, "links": links, "annotations": anns}


class D(yaml.SafeDumper):
    pass


D.add_representer(str, lambda d, s: d.represent_scalar("tag:yaml.org,2002:str", s, style="|" if "\n" in s else None))


def write_yaml(path, topo):
    if path.exists():  # keep the synced notes so a rebuild doesn't need sync_notes to pass validate
        topo["lab"]["notes"] = (yaml.safe_load(path.read_text(encoding="utf-8"))["lab"].get("notes") or "")
    path.write_text(yaml.dump(topo, Dumper=D, sort_keys=False, allow_unicode=True, width=1000), encoding="utf-8", newline="\n")


LABS = {
 "learn": (LEARN, LEARN_YAML, "[LEARN] ENCOR 3.3.b NAT and PAT",
           "Learning: give a private network internet access with static NAT, port forwarding, a dynamic pool and PAT, and read the translation table.",
           "clean"),
 "ts": (TS, TS_YAML, "[TSHOOT] ENCOR 3.3.b NAT and PAT",
        "Troubleshooting: after the edge router was replaced, staff have no internet and the public web server is unreachable.",
        "ts"),
}

if __name__ == "__main__":
    for d, fname, title, desc, mode in LABS.values():
        (d / "solution/configs").mkdir(parents=True, exist_ok=True)
        for h in INTS:
            (d / f"solution/configs/{h}.cfg").write_text(config(h, "final"), encoding="utf-8", newline="\n")
        for h in PCS:
            (d / f"solution/configs/{h}.cfg").write_text(pc_config(h), encoding="utf-8", newline="\n")
        write_yaml(d / fname, topology(title, desc, mode))
    if "--chunks" in sys.argv:
        OUT = Path(sys.argv[sys.argv.index("--chunks") + 1])
        OUT.mkdir(parents=True, exist_ok=True)
        for key, (d, fname, title, desc, mode) in LABS.items():
            t = topology(f"[TEST] nat {key}", "temporary test chunk", mode)
            t["annotations"] = []  # keeps the MCP payload small; annotations are validated on the real files
            (OUT / f"{key}.json").write_text(json.dumps(t), encoding="utf-8")
    print("done")
