# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6"]
# ///
"""Build configs + topology files for the ENCOR 3.2.c eBGP lab pair (learn-ebgp + ts-ebgp).

One source of truth for every variant. After running, run tools/sync_notes.py.
  ISP1-3 are "the provider" and boot fully configured in every variant; only R1 changes.
  learn boot  ("clean"): R1 hostname/login only, interfaces shut
  final       ("final"): R1 dual-homed, local-pref 200 from ISP1, prepend x3 toward ISP2, no transit
  ts boot     ("ts"):    final + the injected faults (all on R1, see FAULTS)
Usage: uv run tools/builders/encor_3_2_c_ebgp.py [--chunks DIR]   (DIR: both labs as JSON for the MCP;
       test by starting <=5 licensed nodes at a time)
"""
import json, sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
TOPIC = REPO / "labs/encor/3-infrastructure/bgp"
LEARN, TS = TOPIC / "learn-ebgp", TOPIC / "ts-ebgp"
LEARN_YAML, TS_YAML = "encor-3.2.c-bgp-learn-ebgp.yaml", "encor-3.2.c-bgp-ts-ebgp.yaml"

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
 transport input ssh telnet
!
end
"""
PHYS = [f"Ethernet0/{i}" for i in range(4)]
ISP2_PASSWORD = "isp2peer"

# interface -> (ip mask, description); unlisted Ethernet0/x are shut
INTS = {
 "R1": [("Loopback0", "10.255.255.1 255.255.255.255", None),
        ("Ethernet0/0", "10.1.101.1 255.255.255.0", "ISP1 (primary) e0/0"),
        ("Ethernet0/1", "10.1.102.1 255.255.255.0", "ISP2 (backup) e0/0"),
        ("Ethernet0/2", "192.168.10.1 255.255.255.0", "PC1 LAN")],
 "ISP1": [("Loopback0", "10.255.255.101 255.255.255.255", None),
          ("Ethernet0/0", "10.1.101.101 255.255.255.0", "customer R1 e0/0 (AS 65001)"),
          ("Ethernet0/1", "10.101.103.101 255.255.255.0", "ISP3 e0/0 (AS 64513)")],
 "ISP2": [("Loopback0", "10.255.255.102 255.255.255.255", None),
          ("Ethernet0/0", "10.1.102.102 255.255.255.0", "customer R1 e0/1 (AS 65001)"),
          ("Ethernet0/1", "10.102.103.102 255.255.255.0", "ISP3 e0/1 (AS 64513)")],
 "ISP3": [("Loopback0", "10.255.255.103 255.255.255.255", None),
          ("Loopback1", "203.0.113.1 255.255.255.0", "simulated internet prefix"),
          ("Ethernet0/0", "10.101.103.103 255.255.255.0", "ISP1 e0/1 (AS 64511)"),
          ("Ethernet0/1", "10.102.103.103 255.255.255.0", "ISP2 e0/1 (AS 64512)"),
          ("Ethernet0/2", "198.51.100.1 255.255.255.0", "PC2 LAN (internet host)")],
}

BGP = {
 "ISP1": """router bgp 64511
 bgp router-id 10.255.255.101
 bgp log-neighbor-changes
 neighbor 10.1.101.1 remote-as 65001
 neighbor 10.1.101.1 description customer R1
 neighbor 10.101.103.103 remote-as 64513
 neighbor 10.101.103.103 description ISP3
 network 10.255.255.101 mask 255.255.255.255
!
""",
 "ISP2": f"""router bgp 64512
 bgp router-id 10.255.255.102
 bgp log-neighbor-changes
 neighbor 10.1.102.1 remote-as 65001
 neighbor 10.1.102.1 description customer R1
 neighbor 10.1.102.1 password {ISP2_PASSWORD}
 neighbor 10.102.103.103 remote-as 64513
 neighbor 10.102.103.103 description ISP3
 network 10.255.255.102 mask 255.255.255.255
!
""",
 "ISP3": """router bgp 64513
 bgp router-id 10.255.255.103
 bgp log-neighbor-changes
 neighbor 10.101.103.101 remote-as 64511
 neighbor 10.101.103.101 description ISP1
 neighbor 10.102.103.102 remote-as 64512
 neighbor 10.102.103.102 description ISP2
 network 10.255.255.103 mask 255.255.255.255
 network 198.51.100.0
 network 203.0.113.0
!
""",
 "R1": f"""ip as-path access-list 1 permit ^$
!
route-map ISP1-IN permit 10
 set local-preference 200
!
route-map ISP2-OUT permit 10
 set as-path prepend 65001 65001 65001
!
router bgp 65001
 bgp router-id 10.255.255.1
 bgp log-neighbor-changes
 neighbor 10.1.101.101 remote-as 64511
 neighbor 10.1.101.101 description ISP1 (primary)
 neighbor 10.1.102.102 remote-as 64512
 neighbor 10.1.102.102 description ISP2 (backup)
 neighbor 10.1.102.102 password {ISP2_PASSWORD}
 network 192.168.10.0
 neighbor 10.1.101.101 route-map ISP1-IN in
 neighbor 10.1.101.101 filter-list 1 out
 neighbor 10.1.102.102 route-map ISP2-OUT out
 neighbor 10.1.102.102 filter-list 1 out
!
""",
}

# Troubleshooting faults, all on R1 (the replaced edge router): (find, replace) on the final config text.
# Numbered as in ts-ebgp/solution/README.md (the order a learner usually meets them).
FAULTS = [
 # Fault 1 MD5 password mismatch toward ISP2 (both sides log Invalid MD5 digest)
 (f" neighbor 10.1.102.102 password {ISP2_PASSWORD}\n", " neighbor 10.1.102.102 password isp2-peer\n"),
 # Fault 2 network statement has no exact RIB match (/16 vs the connected /24): LAN never advertised.
 # (192.168.10.0 mask 255.255.0.0 would be rejected outright: host bits set.)
 (" network 192.168.10.0\n", " network 192.168.0.0 mask 255.255.0.0\n"),
 # Fault 3 session to ISP1 sourced from Lo0: ISP1 only knows 10.1.101.1, so TCP never completes (Idle/Active)
 (" neighbor 10.1.101.101 description ISP1 (primary)\n",
  " neighbor 10.1.101.101 description ISP1 (primary)\n neighbor 10.1.101.101 update-source Loopback0\n"),
 # Fault 4 (hidden behind 3) wrong remote-as for ISP1: bad peer AS NOTIFICATION once TCP comes up
 (" neighbor 10.1.101.101 remote-as 64511\n", " neighbor 10.1.101.101 remote-as 64521\n"),
 # Fault 5 local-pref policy applied to the backup ISP: outbound traffic prefers ISP2
 (" neighbor 10.1.101.101 route-map ISP1-IN in\n", " neighbor 10.1.102.102 route-map ISP1-IN in\n"),
]


def config(h, mode):
    """mode: clean | final | ts (R1 only differs; ISPs are always final)"""
    out = [BASE.format(h=h)]
    if h == "R1" and mode == "clean":
        out.append("interface range Ethernet0/0 - 3\n no ip address\n shutdown\n!\n")
        out.append(LINES)
        return "".join(out)
    used = set()
    for name, ip, desc in INTS[h]:
        used.add(name)
        s = f"interface {name}\n"
        if desc:
            s += f" description {desc}\n"
        s += f" ip address {ip}\n"
        if name.startswith("Ethernet"):
            s += " no shutdown\n"
        out.append(s + "!\n")
    for p in PHYS:
        if p not in used:
            out.append(f"interface {p}\n no ip address\n shutdown\n!\n")
    bgp = BGP[h]
    if h == "R1" and mode == "ts":
        for old, new in FAULTS:
            assert bgp.count(old) == 1, old
            bgp = bgp.replace(old, new)
    out.append(bgp)
    out.append(LINES)
    return "".join(out)


PCS = {"PC1": ("192.168.10.10/24", "192.168.10.1"), "PC2": ("198.51.100.10/24", "198.51.100.1")}


def pc_config(h):
    ip, gw = PCS[h]
    return (f"# this is a shell script which will be sourced at boot\nhostname {h}\nUSERNAME=cisco\nPASSWORD=cisco\n"
            f"ip address add {ip} dev eth0\nip link set dev eth0 up\nip route add default via {gw}\n")


ORDER = ["R1", "ISP1", "ISP2", "ISP3", "PC1", "PC2"]
POS = {"PC1": (-600, 0), "R1": (-300, 0), "ISP1": (0, -200), "ISP2": (0, 200), "ISP3": (300, 0), "PC2": (600, 0)}
LABELS = {
 "R1": "R1  AS 65001 (you)  cisco/cisco\nLo0   10.255.255.1/32\ne0/0  10.1.101.1/24  (ISP1)\ne0/1  10.1.102.1/24  (ISP2)\ne0/2  192.168.10.1/24 (PC1)",
 "ISP1": "ISP1  AS 64511 primary  cisco/cisco\nLo0   10.255.255.101/32\ne0/0  10.1.101.101/24  (R1)\ne0/1  10.101.103.101/24 (ISP3)",
 "ISP2": "ISP2  AS 64512 backup  cisco/cisco\nLo0   10.255.255.102/32\ne0/0  10.1.102.102/24  (R1)\ne0/1  10.102.103.102/24 (ISP3)",
 "ISP3": "ISP3  AS 64513 internet  cisco/cisco\nLo0   10.255.255.103/32\nLo1   203.0.113.1/24\ne0/0  10.101.103.103/24 (ISP1)\ne0/1  10.102.103.103/24 (ISP2)\ne0/2  198.51.100.1/24 (PC2)",
 "PC1": "PC1  cisco/cisco\neth0 192.168.10.10/24\ngw   192.168.10.1",
 "PC2": "PC2  internet host  cisco/cisco\neth0 198.51.100.10/24\ngw   198.51.100.1",
}
# (a, a's Ethernet0/x, b, b's Ethernet0/x or eth0)
LINKS = [("R1", 0, "ISP1", 0), ("R1", 1, "ISP2", 0), ("ISP1", 1, "ISP3", 0), ("ISP2", 1, "ISP3", 1),
         ("R1", 2, "PC1", None), ("ISP3", 2, "PC2", None)]


def iol_ifaces():
    names = ["Loopback0"] + PHYS
    return [{"id": f"i{k}", "label": n, "type": "loopback" if n.startswith("Loop") else "physical",
             **({"slot": k - 1} if k else {})} for k, n in enumerate(names)]


def topology(title, description, mode):
    nodes, ids = [], {}
    for k, h in enumerate(ORDER):
        nid = f"n{k}"; ids[h] = nid
        x, y = POS[h]
        n = {"id": nid, "label": h, "x": x, "y": y}
        if h.startswith("PC"):
            n.update(node_definition="alpine", image_definition="alpine-base-3-23-3",
                     interfaces=[{"id": "i0", "label": "eth0", "slot": 0, "type": "physical"}],
                     configuration=[{"name": "node.cfg", "content": pc_config(h)}])
        else:
            n.update(node_definition="iol-xe", image_definition="iol-xe-17-18-02", interfaces=iol_ifaces(),
                     configuration=[{"name": "ios_config.txt", "content": config(h, mode)}])
        nodes.append(n)
    links = [{"id": f"l{k}", "n1": ids[a], "i1": f"i{ia + 1}", "n2": ids[b], "i2": "i0" if ib is None else f"i{ib + 1}"}
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
 "learn": (LEARN, LEARN_YAML, "[LEARN] ENCOR 3.2.c eBGP Dual-Homed Edge",
           "Learning: peer an edge router with two ISPs over eBGP, read neighbor states, and steer best-path selection with weight, local-pref and AS-path prepending.",
           "clean"),
 "ts": (TS, TS_YAML, "[TSHOOT] ENCOR 3.2.c eBGP Peering and Best Path",
        "Troubleshooting: after the edge router was replaced, the internet is down and the backup ISP carries the traffic.",
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
            t = topology(f"[TEST] ebgp {key}", "temporary test chunk", mode)
            t["annotations"] = []  # keeps the MCP payload small; annotations are validated on the real files
            (OUT / f"{key}.json").write_text(json.dumps(t), encoding="utf-8")
    print("done")
