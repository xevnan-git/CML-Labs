# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6"]
# ///
"""Build configs + topology files for the ENCOR 3.3.a NTP lab pair (learn-ntp + ts-ntp).

One source of truth for every variant. After running, run tools/sync_notes.py.
  learn boot  ("clean"): addressing and OSPF area 0 up, no NTP, no time zone (the topic is NTP)
  final       ("final"): learn end state = ts design: NTP1 master (stratum 3) -> R1 -> R2, R3; R2<->R3 peers;
                         MD5 auth everywhere; R1 restricts who may sync from it (ntp access-group)
  ts boot     ("ts"):    final + the injected faults (see FAULTS)
Usage: uv run tools/builders/encor_3_3_a_ntp.py [--chunks DIR]   (DIR: both labs as JSON for the MCP;
       each lab is 4 licensed nodes, so a chunk is the whole lab)
"""
import json, sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
TOPIC = REPO / "labs/encor/3-infrastructure/ntp"
LEARN, TS = TOPIC / "learn-ntp", TOPIC / "ts-ntp"
LEARN_YAML, TS_YAML = "encor-3.3.a-ntp-learn-ntp.yaml", "encor-3.3.a-ntp-ts-ntp.yaml"

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

# interface -> (ip mask, description); unlisted Ethernet0/x are shut. Everything is in OSPF area 0 except NO_OSPF.
INTS = {
 "NTP1": [("Loopback0", "10.255.255.100 255.255.255.255", "NTP service address"),
          ("Ethernet0/0", "10.1.100.100 255.255.255.0", "R1 e0/0")],
 "R1": [("Loopback0", "10.255.255.1 255.255.255.255", None),
        ("Ethernet0/0", "10.1.100.1 255.255.255.0", "NTP1 e0/0"),
        ("Ethernet0/1", "10.1.2.1 255.255.255.0", "R2 e0/0"),
        ("Ethernet0/2", "10.1.3.1 255.255.255.0", "R3 e0/0")],
 "R2": [("Loopback0", "10.255.255.2 255.255.255.255", None),
        ("Ethernet0/0", "10.1.2.2 255.255.255.0", "R1 e0/1"),
        ("Ethernet0/1", "10.2.3.2 255.255.255.0", "R3 e0/1")],
 "R3": [("Loopback0", "10.255.255.3 255.255.255.255", None),
        ("Loopback1", "172.19.0.1 255.255.255.0", "future management network (not in OSPF yet)"),
        ("Ethernet0/0", "10.1.3.3 255.255.255.0", "R1 e0/2"),
        ("Ethernet0/1", "10.2.3.3 255.255.255.0", "R2 e0/1")],
}
NO_OSPF = {("R3", "Loopback1")}
RID = {"NTP1": "10.255.255.100", "R1": "10.255.255.1", "R2": "10.255.255.2", "R3": "10.255.255.3"}

CLOCK = """clock timezone EST -5 0
clock summer-time EDT recurring
service timestamps log datetime msec localtime show-timezone
service timestamps debug datetime msec localtime show-timezone
!
"""
AUTH = """ntp authentication-key 1 md5 NTPsecret
ntp authenticate
ntp trusted-key 1
ntp source Loopback0
"""
# final NTP config per router (after the interfaces: ntp source names one)
NTP = {
 "NTP1": AUTH + "ntp master 3\n!\n",
 "R1": """ip access-list standard NTP-PEERS
 10 permit 10.255.255.100
ip access-list standard NTP-CLIENTS
 10 permit 10.255.255.2
 20 permit 10.255.255.3
!
""" + AUTH + """ntp access-group peer NTP-PEERS
ntp access-group serve-only NTP-CLIENTS
ntp server 10.255.255.100 key 1
!
""",
 "R2": AUTH + "ntp server 10.255.255.1 key 1\nntp peer 10.255.255.3 key 1\n!\n",
 "R3": AUTH + "ntp server 10.255.255.1 key 1\nntp peer 10.255.255.2 key 1\n!\n",
}

# Troubleshooting faults: (router, find, replace) on that router's final NTP text.
# Numbered as in ts-ntp/solution/README.md (the order a learner usually meets them).
FAULTS = [
 # Fault 1 R1's key 1 string differs from NTP1's: R1 never syncs, so nothing below it does
 ("R1", "ntp authentication-key 1 md5 NTPsecret\n", "ntp authentication-key 1 md5 NTPsecret1\n"),
 # Fault 2 R1's serve-only ACL lists R2's interface address, but R2 sources NTP from Loopback0
 ("R1", " 10 permit 10.255.255.2\n", " 10 permit 10.1.2.2\n"),
 # Fault 3 R2 has no trusted key: with ntp authenticate on, it won't sync to anyone
 ("R2", "ntp trusted-key 1\n", ""),
 # Fault 4 R3 sources NTP from Loopback1, which isn't in OSPF: nobody can answer it
 ("R3", "ntp source Loopback0\n", "ntp source Loopback1\n"),
 # Fault 5 R3's server is its own loopback (self-reference) instead of R1
 ("R3", "ntp server 10.255.255.1 key 1\n", "ntp server 10.255.255.3 key 1\n"),
]


def config(h, mode):
    """mode: clean | final | ts"""
    out = [BASE.format(h=h)]
    if mode != "clean":
        out.append(CLOCK)
    used = set()
    for name, ip, desc in INTS[h]:
        used.add(name)
        s = f"interface {name}\n"
        if desc:
            s += f" description {desc}\n"
        s += f" ip address {ip}\n"
        if (h, name) not in NO_OSPF:
            s += " ip ospf 1 area 0\n"
        if name.startswith("Ethernet"):
            s += " no shutdown\n"
        out.append(s + "!\n")
    for p in PHYS:
        if p not in used:
            out.append(f"interface {p}\n no ip address\n shutdown\n!\n")
    out.append(f"router ospf 1\n router-id {RID[h]}\n!\n")
    if mode != "clean":
        ntp = NTP[h]
        if mode == "ts":
            for r, old, new in FAULTS:
                if r == h:
                    assert ntp.count(old) == 1, old
                    ntp = ntp.replace(old, new)
        out.append(ntp)
    out.append(LINES)
    return "".join(out)


ORDER = ["NTP1", "R1", "R2", "R3"]
POS = {"NTP1": (0, -300), "R1": (0, -50), "R2": (-250, 200), "R3": (250, 200)}
LABELS = {
 "NTP1": "NTP1  time source  cisco/cisco\nLo0   10.255.255.100/32\ne0/0  10.1.100.100/24 (R1)",
 "R1": "R1  cisco/cisco\nLo0   10.255.255.1/32\ne0/0  10.1.100.1/24 (NTP1)\ne0/1  10.1.2.1/24   (R2)\ne0/2  10.1.3.1/24   (R3)",
 "R2": "R2  cisco/cisco\nLo0   10.255.255.2/32\ne0/0  10.1.2.2/24 (R1)\ne0/1  10.2.3.2/24 (R3)",
 "R3": "R3  cisco/cisco\nLo0   10.255.255.3/32\nLo1   172.19.0.1/24 (not in OSPF)\ne0/0  10.1.3.3/24 (R1)\ne0/1  10.2.3.3/24 (R2)",
}
# (a, a's Ethernet0/x, b, b's Ethernet0/x)
LINKS = [("R1", 0, "NTP1", 0), ("R1", 1, "R2", 0), ("R1", 2, "R3", 0), ("R2", 1, "R3", 1)]


def iol_ifaces(h):
    names = ["Loopback0"] + PHYS  # CML only models Loopback0; other loopbacks come from the config
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
        nodes.append({"id": nid, "label": h, "x": x, "y": y, "node_definition": "iol-xe",
                      "image_definition": "iol-xe-17-18-02", "interfaces": iol_ifaces(h),
                      "configuration": [{"name": "ios_config.txt", "content": config(h, mode)}]})
    links = [{"id": f"l{k}", "n1": ids[a], "i1": iface_id(a, ia), "n2": ids[b], "i2": iface_id(b, ib)}
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
 "learn": (LEARN, LEARN_YAML, "[LEARN] ENCOR 3.3.a NTP",
           "Learning: build an NTP hierarchy (master, client, peers), read stratum and associations, then secure it with MD5 authentication, ntp source and access-groups.",
           "clean"),
 "ts": (TS, TS_YAML, "[TSHOOT] ENCOR 3.3.a NTP",
        "Troubleshooting: after an NTP hardening change, none of the routers keep the right time.",
        "ts"),
}

if __name__ == "__main__":
    for d, fname, title, desc, mode in LABS.values():
        (d / "solution/configs").mkdir(parents=True, exist_ok=True)
        for h in INTS:
            (d / f"solution/configs/{h}.cfg").write_text(config(h, "final"), encoding="utf-8", newline="\n")
        write_yaml(d / fname, topology(title, desc, mode))
    if "--chunks" in sys.argv:
        OUT = Path(sys.argv[sys.argv.index("--chunks") + 1])
        OUT.mkdir(parents=True, exist_ok=True)
        for key, (d, fname, title, desc, mode) in LABS.items():
            t = topology(f"[TEST] ntp {key}", "temporary test chunk", mode)
            t["annotations"] = []  # keeps the MCP payload small; annotations are validated on the real files
            (OUT / f"{key}.json").write_text(json.dumps(t), encoding="utf-8")
    print("done")
