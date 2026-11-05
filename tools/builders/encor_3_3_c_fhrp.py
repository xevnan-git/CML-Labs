# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6"]
# ///
"""Build configs + topology files for the ENCOR 3.3.c FHRP lab pair (learn-fhrp + ts-fhrp).

One source of truth for every variant. After running, run tools/sync_notes.py.
  learn boot  ("clean"): addressing + OSPF up (LAN interfaces passive), no FHRP: the PCs' gateway .1 doesn't exist
  final       ("final"): learn end state = ts design:
                         LAN10 HSRPv2 group 10, VIP .1, R1 active (110, preempt, MD5, track 1 decrement 20), R2 100 preempt
                         LAN20 VRRPv3 group 20, VIP .1, R2 master (110, track 1 decrement 20), R1 100
                         track 1 = route to R3's Lo0 (lost when the router's own uplink fails)
  ts boot     ("ts"):    final + the injected faults (see FAULTS)
Usage: uv run tools/builders/encor_3_3_c_fhrp.py [--chunks DIR]   (DIR: both labs as JSON for the MCP;
       each lab is 5 licensed nodes + 2 unmanaged switches, so a chunk is the whole lab)
"""
import json, sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
TOPIC = REPO / "labs/encor/3-infrastructure/fhrp"
LEARN, TS = TOPIC / "learn-fhrp", TOPIC / "ts-fhrp"
LEARN_YAML, TS_YAML = "encor-3.3.c-fhrp-learn-fhrp.yaml", "encor-3.3.c-fhrp-ts-fhrp.yaml"

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


# interface -> (ip mask, description, ospf passive?)
INTS = {
 "R1": [("Loopback0", "10.255.255.1 255.255.255.255", None),
        ("Ethernet0/0", "192.168.10.2 255.255.255.0", "LAN10 staff (PC1) via SW1"),
        ("Ethernet0/1", "192.168.20.2 255.255.255.0", "LAN20 lab (PC2) via SW2"),
        ("Ethernet0/2", "10.1.3.1 255.255.255.0", "uplink R3 e0/0")],
 "R2": [("Loopback0", "10.255.255.2 255.255.255.255", None),
        ("Ethernet0/0", "192.168.10.3 255.255.255.0", "LAN10 staff (PC1) via SW1"),
        ("Ethernet0/1", "192.168.20.3 255.255.255.0", "LAN20 lab (PC2) via SW2"),
        ("Ethernet0/2", "10.2.3.2 255.255.255.0", "uplink R3 e0/1")],
 "R3": [("Loopback0", "10.255.255.3 255.255.255.255", None),
        ("Loopback1", "172.16.0.100 255.255.255.255", "data-center server"),
        ("Ethernet0/0", "10.1.3.3 255.255.255.0", "R1 e0/2"),
        ("Ethernet0/1", "10.2.3.3 255.255.255.0", "R2 e0/2")],
}
RID = {"R1": "10.255.255.1", "R2": "10.255.255.2", "R3": "10.255.255.3"}
PASSIVE = {"R1": ["Ethernet0/0", "Ethernet0/1"], "R2": ["Ethernet0/0", "Ethernet0/1"], "R3": []}

# FHRP (final). Global part goes before the interfaces; per-interface lines after "ip address".
GLOBAL_FHRP = {
 "R1": "fhrp version vrrp v3\ntrack 1 ip route 10.255.255.3 255.255.255.255 reachability\n!\n",
 "R2": "fhrp version vrrp v3\ntrack 1 ip route 10.255.255.3 255.255.255.255 reachability\n!\n",
}
IF_FHRP = {
 ("R1", "Ethernet0/0"): (" standby version 2\n standby 10 ip 192.168.10.1\n standby 10 timers 1 3\n"
                         " standby 10 priority 110\n standby 10 preempt\n"
                         " standby 10 authentication md5 key-string FHRPsecret\n standby 10 track 1 decrement 20\n"),
 ("R2", "Ethernet0/0"): (" standby version 2\n standby 10 ip 192.168.10.1\n standby 10 timers 1 3\n"
                         " standby 10 preempt\n standby 10 authentication md5 key-string FHRPsecret\n"),
 ("R1", "Ethernet0/1"): " vrrp 20 address-family ipv4\n  address 192.168.20.1 primary\n  exit-vrrp\n",
 ("R2", "Ethernet0/1"): (" vrrp 20 address-family ipv4\n  priority 110\n  track 1 decrement 20\n"
                         "  address 192.168.20.1 primary\n  exit-vrrp\n"),
}

# Troubleshooting faults: (router, find, replace) on that router's final config text.
# Numbered as in ts-fhrp/solution/README.md.
FAULTS = [
 # Fault 1 R1's HSRP key differs in case: R1 and R2 ignore each other's hellos, both Active on LAN10
 ("R1", " standby 10 authentication md5 key-string FHRPsecret\n", " standby 10 authentication md5 key-string FHRPSecret\n"),
 # Fault 2 R2's VRRP VIP is .254: R2 (110) is Master for .254, R1 stays Backup, nobody answers ARP for .1
 ("R2", "  address 192.168.20.1 primary\n", "  address 192.168.20.254 primary\n"),
 # Fault 3 R1's track decrement too small: 110-5 = 105 still beats R2's 100 when R1's uplink fails
 ("R1", " standby 10 track 1 decrement 20\n", " standby 10 track 1 decrement 5\n"),
 # Fault 4 (after 3) R2 has no preempt: it never takes over from a degraded R1
 ("R2", " standby 10 preempt\n", ""),
 # Fault 5 R2's track object watches its LAN10 interface instead of the route upstream
 ("R2", "track 1 ip route 10.255.255.3 255.255.255.255 reachability\n", "track 1 interface Ethernet0/0 line-protocol\n"),
]


def config(h, mode):
    """mode: clean | final | ts"""
    out = [BASE.format(h=h)]
    if mode != "clean" and h in GLOBAL_FHRP:
        out.append(GLOBAL_FHRP[h])
    used = set()
    for name, ip, desc in INTS[h]:
        used.add(name)
        s = f"interface {name}\n"
        if desc:
            s += f" description {desc}\n"
        s += f" ip address {ip}\n ip ospf 1 area 0\n"
        if mode != "clean" and (h, name) in IF_FHRP:
            s += IF_FHRP[(h, name)]
        if name.startswith("Ethernet"):
            s += " no shutdown\n"
        out.append(s + "!\n")
    for p in PHYS:
        if p not in used:
            out.append(f"interface {p}\n no ip address\n shutdown\n!\n")
    ospf = f"router ospf 1\n router-id {RID[h]}\n" + "".join(f" passive-interface {i}\n" for i in PASSIVE[h]) + "!\n"
    out.append(ospf)
    out.append(LINES)
    text = "".join(out)
    if mode == "ts":
        for r, old, new in FAULTS:
            if r == h:
                assert text.count(old) == 1, old
                text = text.replace(old, new)
    return text


PCS = {"PC1": ("192.168.10.10/24", "192.168.10.1"), "PC2": ("192.168.20.10/24", "192.168.20.1")}


def pc_config(h):
    ip, gw = PCS[h]
    return (f"# this is a shell script which will be sourced at boot\nhostname {h}\nUSERNAME=cisco\nPASSWORD=cisco\n"
            f"ip address add {ip} dev eth0\nip link set dev eth0 up\nip route add default via {gw}\n")


SWITCHES = ["SW1", "SW2"]
ORDER = ["R1", "R2", "R3", "SW1", "SW2", "PC1", "PC2"]
POS = {"R3": (0, -250), "R1": (-250, -50), "R2": (250, -50), "SW1": (-150, 150), "SW2": (150, 150),
       "PC1": (-150, 330), "PC2": (150, 330)}
LABELS = {
 "R1": "R1  gateway  cisco/cisco\nLo0   10.255.255.1/32\ne0/0  192.168.10.2/24 (LAN10)\ne0/1  192.168.20.2/24 (LAN20)\n"
       "e0/2  10.1.3.1/24     (R3)",
 "R2": "R2  gateway  cisco/cisco\nLo0   10.255.255.2/32\ne0/0  192.168.10.3/24 (LAN10)\ne0/1  192.168.20.3/24 (LAN20)\n"
       "e0/2  10.2.3.2/24     (R3)",
 "R3": "R3  upstream  cisco/cisco\nLo0   10.255.255.3/32\nLo1   172.16.0.100/32 (server)\n"
       "e0/0  10.1.3.3/24 (R1)\ne0/1  10.2.3.3/24 (R2)",
 "PC1": "PC1  LAN10  cisco/cisco\neth0 192.168.10.10/24\ngw   192.168.10.1 (virtual)",
 "PC2": "PC2  LAN20  cisco/cisco\neth0 192.168.20.10/24\ngw   192.168.20.1 (virtual)",
}
# (a, a-iface, b, b-iface): router ifaces as Ethernet0/x index, switch ports as "pN", hosts as None
LINKS = [("R1", 0, "SW1", "p0"), ("R2", 0, "SW1", "p1"), ("PC1", None, "SW1", "p2"),
         ("R1", 1, "SW2", "p0"), ("R2", 1, "SW2", "p1"), ("PC2", None, "SW2", "p2"),
         ("R1", 2, "R3", 0), ("R2", 2, "R3", 1)]


def iol_ifaces(h):
    out = []
    for k, n in enumerate(["Loopback0"] + PHYS):  # CML only models Loopback0 (R3's Loopback1 lives in the config)
        i = {"id": f"i{k}", "label": n, "type": "loopback" if n.startswith("Loop") else "physical"}
        if not n.startswith("Loop"):
            i["slot"] = PHYS.index(n)
        out.append(i)
    return out


def iface_id(h, x):
    if h in SWITCHES:
        return f"i{int(x[1:])}"
    if x is None:
        return "i0"
    return next(i["id"] for i in iol_ifaces(h) if i["label"] == f"Ethernet0/{x}")


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
        elif h in SWITCHES:
            n.update(node_definition="unmanaged_switch",
                     interfaces=[{"id": f"i{p}", "label": f"port{p}", "slot": p, "type": "physical"} for p in range(4)])
        else:
            n.update(node_definition="iol-xe", image_definition="iol-xe-17-18-02", interfaces=iol_ifaces(h),
                     configuration=[{"name": "ios_config.txt", "content": config(h, mode)}])
        nodes.append(n)
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
 "learn": (LEARN, LEARN_YAML, "[LEARN] ENCOR 3.3.c FHRP (HSRP and VRRP)",
           "Learning: give two LANs a redundant default gateway with HSRPv2 and VRRPv3, tune priority, preempt, tracking and authentication, and watch failover.",
           "clean"),
 "ts": (TS, TS_YAML, "[TSHOOT] ENCOR 3.3.c FHRP (HSRP and VRRP)",
        "Troubleshooting: the gateway failover test failed, one LAN has no gateway and the logs complain about HSRP.",
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
            t = topology(f"[TEST] fhrp {key}", "temporary test chunk", mode)
            t["annotations"] = []  # keeps the MCP payload small; annotations are validated on the real files
            (OUT / f"{key}.json").write_text(json.dumps(t), encoding="utf-8")
    print("done")
