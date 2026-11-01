# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6"]
# ///
"""Build configs + topology files for the ENCOR 3.1.c STP lab pair (learn-stp + ts-mst-guards).

One source of truth for every variant. After running, run tools/sync_notes.py.
  learn boot  ("clean"): VLANs, trunks, access ports and SVIs prebuilt; STP left at defaults; SW5 (rogue) links shut
  learn final ("final"): MST region LAB, PortFast + BPDU guard on edge ports, root guard toward SW5
  ts final    ("tsok"):  MST region LAB, root guard on distribution downlinks, PortFast + BPDU guard on PC ports
  ts boot     ("ts"):    tsok + injected faults
Usage: uv run tools/builders/encor_3_1_c_stp.py [--chunks DIR]   (DIR: both labs as JSON for the MCP;
       test by starting <=5 licensed nodes at a time)
"""
import json, sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
TOPIC = REPO / "labs/encor/3-infrastructure/switching"
LEARN, TS = TOPIC / "learn-stp", TOPIC / "ts-mst-guards"
LEARN_YAML, TS_YAML = "encor-3.1.c-switching-learn-stp.yaml", "encor-3.1.c-switching-ts-mst-guards.yaml"

BASE = """hostname {h}
no ip domain lookup
ip domain name lab.local
enable secret cisco
username cisco privilege 15 secret cisco
!
vtp domain LAB
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
         "switchport trunk allowed vlan 10,20,99", "switchport mode trunk"]
EDGE = ["spanning-tree portfast", "spanning-tree bpduguard enable"]
PHYS = [f"Ethernet{s}/{p}" for s in range(2) for p in range(4)]
MST = ["spanning-tree mode mst", "spanning-tree mst configuration", " name LAB", " revision 1",
       " instance 1 vlan 10", " instance 2 vlan 20", "!"]
PRIO = {"SW1": ["spanning-tree mst 0-1 priority 4096", "spanning-tree mst 2 priority 8192"],
        "SW2": ["spanning-tree mst 0-1 priority 8192", "spanning-tree mst 2 priority 4096"]}


def access(vlan, desc):
    return (desc, ["switchport mode access", f"switchport access vlan {vlan}"])


# switch -> {iface: (description, lines)}; SVIs; default gateway
SW = {
 "SW1": {"ports": {"Ethernet0/0": ("to SW2 e0/0", TRUNK), "Ethernet0/1": ("to SW3 e0/0", TRUNK),
                   "Ethernet0/2": ("to SW4 e0/0", TRUNK)},
         "svis": [(10, "192.168.10.1"), (20, "192.168.20.1"), (99, "192.168.99.1")], "routing": True},
 "SW2": {"ports": {"Ethernet0/0": ("to SW1 e0/0", TRUNK), "Ethernet0/1": ("to SW3 e0/1", TRUNK),
                   "Ethernet0/2": ("to SW4 e0/1", TRUNK)},
         "svis": [(99, "192.168.99.202")], "gw": "192.168.99.1"},
 "SW3": {"ports": {"Ethernet0/0": ("to SW1 e0/1", TRUNK), "Ethernet0/1": ("to SW2 e0/1", TRUNK),
                   "Ethernet1/0": access(10, "PC1")},
         "svis": [(99, "192.168.99.203")], "gw": "192.168.99.1"},
 "SW4": {"ports": {"Ethernet0/0": ("to SW1 e0/2", TRUNK), "Ethernet0/1": ("to SW2 e0/2", TRUNK),
                   "Ethernet1/0": access(20, "PC2")},
         "svis": [(99, "192.168.99.204")], "gw": "192.168.99.1"},
}
# Learning lab only: the spare ports SW5 plugs into, and SW5 itself
LEARN_EXTRA = {"SW3": {"Ethernet1/2": access(10, "spare desk port (SW5 e0/0)")},
               "SW4": {"Ethernet1/2": access(10, "lab bench port (SW5 e0/1)")}}
SW5_CFG = BASE.format(h="SW5") + """spanning-tree mode rapid-pvst
spanning-tree vlan 1-4094 priority 0
!
interface Ethernet0/0
 description to SW3 e1/2
 switchport mode access
 switchport access vlan 10
 shutdown
!
interface Ethernet0/1
 description to SW4 e1/2
 switchport mode access
 switchport access vlan 10
 shutdown
!
""" + "".join(f"interface {p}\n shutdown\n!\n" for p in PHYS[2:]) + """interface Vlan10
 ip address 192.168.10.205 255.255.255.0
 no shutdown
!
""" + LINES

# Final-state per-port additions: mode -> switch -> iface -> extra lines
ADD = {
 "final": {"SW3": {"Ethernet1/0": EDGE, "Ethernet1/2": EDGE}, "SW4": {"Ethernet1/0": EDGE, "Ethernet1/2": ["spanning-tree guard root"]}},
 "tsok": {"SW1": {"Ethernet0/1": ["spanning-tree guard root"], "Ethernet0/2": ["spanning-tree guard root"]},
          "SW2": {"Ethernet0/1": ["spanning-tree guard root"], "Ethernet0/2": ["spanning-tree guard root"]},
          "SW3": {"Ethernet1/0": EDGE}, "SW4": {"Ethernet1/0": EDGE}},
}
# Troubleshooting faults on top of tsok: switch -> list of (where, old or None (append), new)
FAULTS = {
 "SW3": [("global", " name LAB", " name Lab"),                       # F1 region name case mismatch
         ("global", None, "spanning-tree mst 1 priority 0")],        # F2 access switch claims MSTI 1 root (masked by F1)
 "SW4": [("Ethernet0/1", None, "spanning-tree portfast trunk"),      # F3 PortFast + BPDU guard on an uplink
         ("Ethernet0/1", None, "spanning-tree bpduguard enable"),
         ("Ethernet0/0", None, "spanning-tree guard root")],          # F4 root guard on the root port
}


def _fault(h, where, lines, mode):
    if mode != "ts":
        return lines
    out = list(lines)
    for w, old, new in FAULTS.get(h, []):
        if w != where:
            continue
        if old is None:
            out.append(new)
        else:
            out = [new if l == old else l for l in out]
    return out


def config(h, mode):
    """mode: clean | final | tsok | ts"""
    if h == "SW5":
        return SW5_CFG
    d = SW[h]
    out = [BASE.format(h=h)]
    stp = []
    if mode != "clean":
        stp = MST + PRIO.get(h, [])
    stp = _fault(h, "global", stp, mode)
    out.append("".join(l + "\n" for l in stp) + ("!\n" if stp else ""))
    if d.get("routing"):
        out.append("ip routing\n!\n")
    ports = dict(d["ports"])
    if mode in ("clean", "final"):
        ports.update(LEARN_EXTRA.get(h, {}))
    add = ADD.get("tsok" if mode == "ts" else mode, {}).get(h, {})
    for p in PHYS:
        if p not in ports:
            out.append(f"interface {p}\n shutdown\n!\n")
            continue
        desc, lines = ports[p]
        lines = _fault(h, p, list(lines) + list(add.get(p, [])), mode)
        out.append(f"interface {p}\n description {desc}\n" + "".join(f" {l}\n" for l in lines) + " no shutdown\n!\n")
    for vlan, ip in d["svis"]:
        out.append(f"interface Vlan{vlan}\n ip address {ip} 255.255.255.0\n no shutdown\n!\n")
    if d.get("gw"):
        # IOL-L2 runs with ip routing on by default, which makes it ignore ip default-gateway
        out.append(f"no ip routing\nip default-gateway {d['gw']}\n!\n")
    out.append(LINES)
    return "".join(out)


PCS = {"PC1": ("192.168.10.10/24", "192.168.10.1"), "PC2": ("192.168.20.10/24", "192.168.20.1")}


def pc_config(h):
    ip, gw = PCS[h]
    return (f"# this is a shell script which will be sourced at boot\nhostname {h}\nUSERNAME=cisco\nPASSWORD=cisco\n"
            f"ip address add {ip} dev eth0\nip link set dev eth0 up\nip route add default via {gw}\n")


POS = {"SW1": (-240, -200), "SW2": (240, -200), "SW3": (-240, 120), "SW4": (240, 120),
       "SW5": (0, 320), "PC1": (-240, 360), "PC2": (240, 360)}
UPL = "e0/0 -> SW1   e0/1 -> SW2"
LABELS = {
 "SW1": "SW1  distribution  cisco/cisco\nVlan10 192.168.10.1/24\nVlan20 192.168.20.1/24\nVlan99 192.168.99.1/24\n"
        "e0/0 -> SW2  e0/1 -> SW3  e0/2 -> SW4",
 "SW2": "SW2  distribution  cisco/cisco\nVlan99 192.168.99.202/24\ne0/0 -> SW1  e0/1 -> SW3  e0/2 -> SW4",
 "SW3": f"SW3  access  cisco/cisco\nVlan99 192.168.99.203/24\n{UPL}\ne1/0 PC1 (vlan 10)",
 "SW4": f"SW4  access  cisco/cisco\nVlan99 192.168.99.204/24\n{UPL}\ne1/0 PC2 (vlan 20)",
 "SW5": "SW5  rogue switch  cisco/cisco\nSTP priority 0, ports shut at boot\ne0/0 -> SW3 e1/2  e0/1 -> SW4 e1/2\n"
        "Vlan10 192.168.10.205/24",
 "PC1": "PC1  cisco/cisco\neth0 192.168.10.10/24\ngw   192.168.10.1",
 "PC2": "PC2  cisco/cisco\neth0 192.168.20.10/24\ngw   192.168.20.1",
}
LINKS = [("SW1", "Ethernet0/0", "SW2", "Ethernet0/0"), ("SW1", "Ethernet0/1", "SW3", "Ethernet0/0"),
         ("SW1", "Ethernet0/2", "SW4", "Ethernet0/0"), ("SW2", "Ethernet0/1", "SW3", "Ethernet0/1"),
         ("SW2", "Ethernet0/2", "SW4", "Ethernet0/1"), ("SW3", "Ethernet1/0", "PC1", "eth0"),
         ("SW4", "Ethernet1/0", "PC2", "eth0"), ("SW3", "Ethernet1/2", "SW5", "Ethernet0/0"),
         ("SW4", "Ethernet1/2", "SW5", "Ethernet0/1")]


def sw_ifaces():
    names = ["Loopback0"] + PHYS
    return [{"id": f"i{k}", "label": n, "type": "loopback" if n.startswith("Loop") else "physical",
             **({"slot": k - 1} if k else {})} for k, n in enumerate(names)]


def iface_id(h, name):
    return "i0" if h.startswith("PC") else f"i{PHYS.index(name) + 1}"


def topology(title, description, mode):
    order = ["SW1", "SW2", "SW3", "SW4"] + (["SW5"] if mode in ("clean", "final") else []) + ["PC1", "PC2"]
    nodes, ids = [], {}
    for k, h in enumerate(order):
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
             for k, (a, ia, b, ib) in enumerate(l for l in LINKS if l[0] in ids and l[2] in ids)]
    anns = []
    for h in order:
        x, y = POS[h]
        dx = -300 if h in ("SW1", "SW3", "PC1") else 60
        dy = 40 if h.startswith("PC") or h == "SW5" else -20
        anns.append({"type": "text", "text_content": LABELS[h], "x1": x + dx, "y1": y + dy,
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
    if path.exists():  # keep the synced notes
        topo["lab"]["notes"] = (yaml.safe_load(path.read_text(encoding="utf-8"))["lab"] or {}).get("notes", "")
    path.write_text(yaml.dump(topo, Dumper=D, sort_keys=False, allow_unicode=True, width=1000), encoding="utf-8", newline="\n")


LABS = {
 "learn": (LEARN, LEARN_YAML, "[LEARN] ENCOR 3.1.c Spanning Tree (RSTP, MST, Guards)",
           "Learning: from default PVST+ to Rapid PVST+ with per-VLAN roots, PortFast/BPDU guard, root guard vs a rogue switch, then MST.",
           "clean", "final", ["SW1", "SW2", "SW3", "SW4", "SW5"]),
 "ts": (TS, TS_YAML, "[TSHOOT] ENCOR 3.1.c MST and STP Guards",
        "Troubleshooting: an MST campus after a 'hardening' change — PC2 is isolated and VLAN 20 paths are wrong.",
        "ts", "tsok", ["SW1", "SW2", "SW3", "SW4"]),
}

if __name__ == "__main__":
    for key, (d, fname, title, desc, boot, final, sws) in LABS.items():
        (d / "solution/configs").mkdir(parents=True, exist_ok=True)
        for h in sws:
            (d / f"solution/configs/{h}.cfg").write_text(config(h, final), encoding="utf-8", newline="\n")
        for h in PCS:
            (d / f"solution/configs/{h}.cfg").write_text(pc_config(h), encoding="utf-8", newline="\n")
        write_yaml(d / fname, topology(title, desc, boot))
    if "--chunks" in sys.argv:
        OUT = Path(sys.argv[sys.argv.index("--chunks") + 1])
        OUT.mkdir(parents=True, exist_ok=True)
        for key, (_, _, _, _, boot, _, _) in LABS.items():
            t = topology(f"[TEST] stp {key}", "temporary test lab (start <=5 licensed nodes at a time)", boot)
            t["annotations"] = []
            (OUT / f"stp-{key}.json").write_text(json.dumps(t), encoding="utf-8")
    print("done")
