# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6"]
# ///
"""Build configs + topology for the ENCOR 3.1.a/3.1.b trunking + EtherChannel troubleshooting lab.

One source of truth for the final (healthy) and faulted configs. After running, run tools/sync_notes.py.
Usage: uv run tools/builders/encor_3_1_ab_trunk_etherchannel.py [--chunks DIR]   (DIR: full ts lab as JSON for the MCP;
       test it by starting <=5 licensed nodes at a time)
"""
import json, sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
TS = REPO / "labs/encor/3-infrastructure/switching/ts-trunk-etherchannel"
YAML_NAME = "encor-3.1.ab-switching-ts-trunk-etherchannel.yaml"

BASE = """hostname {h}
no ip domain lookup
ip domain name lab.local
enable secret cisco
username cisco privilege 15 secret cisco
!
vtp domain {vtp}
vtp mode transparent
!
vlan 10
 name SALES
vlan 20
 name ENGINEERING
vlan 99
 name MGMT
vlan 999
 name NATIVE-UNUSED
!
spanning-tree mode rapid-pvst
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
TRUNK = ["switchport trunk encapsulation dot1q", "switchport trunk native vlan 999",
         "switchport trunk allowed vlan 10,20,99"]
STATIC = TRUNK + ["switchport mode trunk"]
PHYS = [f"Ethernet{s}/{p}" for s in range(2) for p in range(4)]

# Per switch: STP priority, SVIs (vlan, ip), default gateway, port-channels, physical ports.
# Port-channel / port entries: (name, description, lines)
SW = {
 "SW1": {"prio": 4096, "routing": True,
         "svis": [(10, "192.168.10.1"), (20, "192.168.20.1"), (99, "192.168.99.1")],
         "pos": [("Port-channel1", "to SW2 Po1 (LACP)", STATIC), ("Port-channel2", "to SW3 Po2 (LACP)", STATIC)],
         "ports": [("Ethernet0/0", "to SW2 e0/0 (Po1)", STATIC + ["channel-group 1 mode active"]),
                   ("Ethernet0/1", "to SW2 e0/1 (Po1)", STATIC + ["channel-group 1 mode active"]),
                   ("Ethernet0/2", "to SW3 e0/0 (Po2)", STATIC + ["channel-group 2 mode active"]),
                   ("Ethernet0/3", "to SW3 e0/1 (Po2)", STATIC + ["channel-group 2 mode active"]),
                   ("Ethernet1/0", "to SW4 e0/2 (static trunk)", STATIC + ["switchport nonegotiate"])]},
 "SW2": {"prio": 8192, "svis": [(99, "192.168.99.202")], "gw": "192.168.99.1",
         "pos": [("Port-channel1", "to SW1 Po1 (LACP)", STATIC), ("Port-channel3", "to SW4 Po3 (PAgP)", STATIC)],
         "ports": [("Ethernet0/0", "to SW1 e0/0 (Po1)", STATIC + ["channel-group 1 mode active"]),
                   ("Ethernet0/1", "to SW1 e0/1 (Po1)", STATIC + ["channel-group 1 mode active"]),
                   ("Ethernet0/2", "to SW3 e0/2 (DTP)", TRUNK + ["switchport mode dynamic desirable"]),
                   ("Ethernet1/0", "to SW4 e0/0 (Po3)", STATIC + ["channel-group 3 mode desirable"]),
                   ("Ethernet1/1", "to SW4 e0/1 (Po3)", STATIC + ["channel-group 3 mode desirable"])]},
 "SW3": {"svis": [(99, "192.168.99.203")], "gw": "192.168.99.1",
         "pos": [("Port-channel2", "to SW1 Po2 (LACP)", STATIC)],
         "ports": [("Ethernet0/0", "to SW1 e0/2 (Po2)", STATIC + ["channel-group 2 mode passive"]),
                   ("Ethernet0/1", "to SW1 e0/3 (Po2)", STATIC + ["channel-group 2 mode passive"]),
                   ("Ethernet0/2", "to SW2 e0/2 (DTP)", TRUNK + ["switchport mode dynamic auto"]),
                   ("Ethernet1/0", "PC1", ["switchport mode access", "switchport access vlan 10", "spanning-tree portfast"]),
                   ("Ethernet1/1", "PC2", ["switchport mode access", "switchport access vlan 20", "spanning-tree portfast"])]},
 "SW4": {"svis": [(99, "192.168.99.204")], "gw": "192.168.99.1",
         "pos": [("Port-channel3", "to SW2 Po3 (PAgP)", STATIC)],
         "ports": [("Ethernet0/0", "to SW2 e1/0 (Po3)", STATIC + ["channel-group 3 mode auto"]),
                   ("Ethernet0/1", "to SW2 e1/1 (Po3)", STATIC + ["channel-group 3 mode auto"]),
                   ("Ethernet0/2", "to SW1 e1/0 (static trunk)", STATIC + ["switchport nonegotiate"]),
                   ("Ethernet1/0", "PC3", ["switchport mode access", "switchport access vlan 10", "spanning-tree portfast"])]},
}

# Troubleshooting faults: switch -> list of (where, old line or None, new line). where = interface name or "vtp".
FAULTS = {
 "SW3": [("vtp", "LAB", "LAB-SW3")],                                          # F1 VTP domain mismatch kills DTP
 "SW1": [("Ethernet0/2", "channel-group 2 mode active", "channel-group 2 mode passive"),   # F2 LACP passive/passive
         ("Ethernet0/3", "channel-group 2 mode active", "channel-group 2 mode passive"),
         ("Ethernet1/0", "switchport trunk allowed vlan 10,20,99", "switchport trunk allowed vlan 20,99")],  # F4 VLAN 10 pruned
 "SW4": [("Ethernet0/0", "channel-group 3 mode auto", "channel-group 3 mode on"),  # F3 PAgP vs mode on
         ("Ethernet0/1", "channel-group 3 mode auto", "channel-group 3 mode on")],
}


def _apply(h, where, lines, mode):
    if mode != "ts":
        return lines
    out = list(lines)
    for w, old, new in FAULTS.get(h, []):
        if w == where:
            out = [new if l == old else l for l in out]
    return out


def config(h, mode):
    """mode: final | ts"""
    d = SW[h]
    vtp = _apply(h, "vtp", ["LAB"], mode)[0]
    out = [BASE.format(h=h, vtp=vtp)]
    if d.get("prio"):
        out.append(f"spanning-tree vlan 1,10,20,99 priority {d['prio']}\n")
    out.append("!\n")
    if d.get("routing"):
        out.append("ip routing\n!\n")
    # Port-channels first so member ports can join them; then members, then SVIs.
    for name, desc, lines in d["pos"]:
        out.append(f"interface {name}\n description {desc}\n" + "".join(f" {l}\n" for l in _apply(h, name, lines, mode)) + "!\n")
    used = set()
    for name, desc, lines in d["ports"]:
        used.add(name)
        out.append(f"interface {name}\n description {desc}\n" + "".join(f" {l}\n" for l in _apply(h, name, lines, mode))
                   + " no shutdown\n!\n")
    for p in PHYS:
        if p not in used:
            out.append(f"interface {p}\n shutdown\n!\n")
    for vlan, ip in d["svis"]:
        out.append(f"interface Vlan{vlan}\n ip address {ip} 255.255.255.0\n no shutdown\n!\n")
    if d.get("gw"):
        # IOL-L2 runs with ip routing on by default, which makes it ignore ip default-gateway
        out.append(f"no ip routing\nip default-gateway {d['gw']}\n!\n")
    out.append(LINES)
    return "".join(out)


PCS = {"PC1": ("192.168.10.10/24", "192.168.10.1"), "PC2": ("192.168.20.10/24", "192.168.20.1"),
       "PC3": ("192.168.10.11/24", "192.168.10.1")}


def pc_config(h):
    ip, gw = PCS[h]
    return (f"# this is a shell script which will be sourced at boot\nhostname {h}\nUSERNAME=cisco\nPASSWORD=cisco\n"
            f"ip address add {ip} dev eth0\nip link set dev eth0 up\nip route add default via {gw}\n")


POS = {"SW1": (-240, -200), "SW2": (240, -200), "SW3": (-240, 120), "SW4": (240, 120),
       "PC1": (-400, 360), "PC2": (-120, 360), "PC3": (240, 360)}

LABELS = {
 "SW1": "SW1  distribution  cisco/cisco\nSTP root (prio 4096), gateway\nVlan10 192.168.10.1/24\nVlan20 192.168.20.1/24\n"
        "Vlan99 192.168.99.1/24\nPo1 e0/0-1 -> SW2   Po2 e0/2-3 -> SW3\ne1/0 -> SW4 e0/2",
 "SW2": "SW2  distribution  cisco/cisco\nSTP prio 8192\nVlan99 192.168.99.202/24\nPo1 e0/0-1 -> SW1   Po3 e1/0-1 -> SW4\n"
        "e0/2 -> SW3 e0/2",
 "SW3": "SW3  access  cisco/cisco\nVlan99 192.168.99.203/24\nPo2 e0/0-1 -> SW1\ne0/2 -> SW2 e0/2\n"
        "e1/0 PC1 (vlan 10)  e1/1 PC2 (vlan 20)",
 "SW4": "SW4  access  cisco/cisco\nVlan99 192.168.99.204/24\nPo3 e0/0-1 -> SW2\ne0/2 -> SW1 e1/0\ne1/0 PC3 (vlan 10)",
 "PC1": "PC1  cisco/cisco\neth0 192.168.10.10/24\ngw   192.168.10.1",
 "PC2": "PC2  cisco/cisco\neth0 192.168.20.10/24\ngw   192.168.20.1",
 "PC3": "PC3  cisco/cisco\neth0 192.168.10.11/24\ngw   192.168.10.1",
}
ORDER = ["SW1", "SW2", "SW3", "SW4", "PC1", "PC2", "PC3"]
# (a, a-interface, b, b-interface) by interface name
LINKS = [("SW1", "Ethernet0/0", "SW2", "Ethernet0/0"), ("SW1", "Ethernet0/1", "SW2", "Ethernet0/1"),
         ("SW1", "Ethernet0/2", "SW3", "Ethernet0/0"), ("SW1", "Ethernet0/3", "SW3", "Ethernet0/1"),
         ("SW1", "Ethernet1/0", "SW4", "Ethernet0/2"), ("SW2", "Ethernet0/2", "SW3", "Ethernet0/2"),
         ("SW2", "Ethernet1/0", "SW4", "Ethernet0/0"), ("SW2", "Ethernet1/1", "SW4", "Ethernet0/1"),
         ("SW3", "Ethernet1/0", "PC1", "eth0"), ("SW3", "Ethernet1/1", "PC2", "eth0"),
         ("SW4", "Ethernet1/0", "PC3", "eth0")]


def sw_ifaces():
    names = ["Loopback0"] + PHYS
    return [{"id": f"i{k}", "label": n, "type": "loopback" if n.startswith("Loop") else "physical",
             **({"slot": k - 1} if k else {})} for k, n in enumerate(names)]


def iface_id(h, name):
    return "i0" if h.startswith("PC") else f"i{PHYS.index(name) + 1}"


def topology(title, description, mode):
    nodes, ids = [], {}
    for k, h in enumerate(ORDER):
        nid = f"n{k}"; ids[h] = nid
        x, y = POS[h]
        n = {"id": nid, "label": h, "x": x, "y": y}
        if h.startswith("SW"):
            n.update(node_definition="ioll2-xe", image_definition="ioll2-xe-17-18-02", interfaces=sw_ifaces(),
                     configuration=[{"name": "ios_config.txt", "content": config(h, mode)}])
        else:
            n.update(node_definition="alpine", image_definition="alpine-base-3-23-3",
                     interfaces=[{"id": "i0", "label": "eth0", "slot": 0, "type": "physical"}],
                     configuration=[{"name": "node.cfg", "content": pc_config(h)}])
        nodes.append(n)
    links = [{"id": f"l{k}", "n1": ids[a], "i1": iface_id(a, ia), "n2": ids[b], "i2": iface_id(b, ib)}
             for k, (a, ia, b, ib) in enumerate(LINKS)]
    anns = []
    for h, text in LABELS.items():
        x, y = POS[h]
        dx = -300 if h in ("SW1", "SW3") else 60
        anns.append({"type": "text", "text_content": text, "x1": x + dx, "y1": y + (40 if h.startswith("PC") else -20),
                     "rotation": 0, "text_bold": False, "text_italic": False, "text_size": 10, "text_unit": "pt",
                     "text_font": "monospace", "color": "#5A5A5AFF", "border_color": "#00000000",
                     # CML file format: '' = solid, '2,2' = dotted, '4,2' = dashed.
                     "border_style": "", "thickness": 1, "z_index": 1})
    return {"lab": {"title": title, "description": description, "notes": "", "version": "0.3.0"},
            "nodes": nodes, "links": links, "annotations": anns}


class D(yaml.SafeDumper):
    pass


D.add_representer(str, lambda d, s: d.represent_scalar("tag:yaml.org,2002:str", s, style="|" if "\n" in s else None))


def write_yaml(path, topo):
    path.write_text(yaml.dump(topo, Dumper=D, sort_keys=False, allow_unicode=True, width=1000), encoding="utf-8", newline="\n")


TITLE = "[TSHOOT] ENCOR 3.1.a-b Trunking and EtherChannel"
DESC = "Troubleshooting: four switches after an uplink 'cleanup' — PC3 is isolated and port-channels are alarming."

if __name__ == "__main__":
    (TS / "solution/configs").mkdir(parents=True, exist_ok=True)
    for h in SW:
        (TS / f"solution/configs/{h}.cfg").write_text(config(h, "final"), encoding="utf-8", newline="\n")
    for h in PCS:
        (TS / f"solution/configs/{h}.cfg").write_text(pc_config(h), encoding="utf-8", newline="\n")
    path = TS / YAML_NAME
    topo = topology(TITLE, DESC, "ts")
    if path.exists():  # keep the synced notes
        topo["lab"]["notes"] = (yaml.safe_load(path.read_text(encoding="utf-8"))["lab"] or {}).get("notes", "")
    write_yaml(path, topo)
    if "--chunks" in sys.argv:
        OUT = Path(sys.argv[sys.argv.index("--chunks") + 1])
        OUT.mkdir(parents=True, exist_ok=True)
        t = topology("[TEST] trunk-etherchannel ts", "temporary test lab (start <=5 licensed nodes at a time)", "ts")
        t["annotations"] = []
        (OUT / "ts.json").write_text(json.dumps(t), encoding="utf-8")
    print("done")
