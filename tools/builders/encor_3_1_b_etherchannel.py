# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6"]
# ///
"""Build configs + topology for the ENCOR 3.1.b EtherChannel troubleshooting lab (ts-etherchannel).

One source of truth for the final (healthy) and faulted configs. After running, run tools/sync_notes.py.
Usage: uv run tools/builders/encor_3_1_b_etherchannel.py [--chunks DIR]   (DIR: full ts lab as JSON for the MCP;
       test it by starting <=5 licensed nodes at a time)

IOL-L2-XE 17.18 has no "port-channel min-links" and silently ignores "lacp max-bundle", and IOL-XE routers can't
bundle at all ("Invalid channel group number"). So the L3 bundle goes to an L3 switch (SW5) and no fault uses either.
"""
import json, sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
TS = REPO / "labs/encor/3-infrastructure/switching/ts-etherchannel"
YAML_NAME = "encor-3.1.b-switching-ts-etherchannel.yaml"

HEAD = """hostname {h}
no ip domain lookup
ip domain name lab.local
enable secret cisco
username cisco privilege 15 secret cisco
!
"""
L2HEAD = """vtp domain LAB
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
ALLOWED = "switchport trunk allowed vlan 10,20,99"
TRUNK = ["switchport trunk encapsulation dot1q", "switchport trunk native vlan 999", ALLOWED, "switchport mode trunk"]
L3MEMBER = ["no switchport", "no ip address", "channel-group 4 mode active"]
PHYS = [f"Ethernet{s}/{p}" for s in range(2) for p in range(4)]


def members(ports, group, mode, desc):
    return {p: (f"{desc} (Po{group})", TRUNK + [f"channel-group {group} mode {mode}"]) for p in ports}


# switch -> port-channels {name: (description, lines)}, ports {iface: (description, lines)}, SVIs, global tail
SW = {
 "SW1": {"pos": {"Port-channel1": ("to SW2 Po1 (LACP)", TRUNK),
                 "Port-channel2": ("to SW3 Po2 (LACP)", TRUNK),
                 "Port-channel4": ("to SW5 Po4 (L3 LACP)", ["no switchport", "ip address 10.1.5.1 255.255.255.0"])},
         "ports": {**members(["Ethernet0/0", "Ethernet0/1"], 1, "active", "to SW2"),
                   **members(["Ethernet0/2", "Ethernet0/3"], 2, "active", "to SW3"),
                   **{p: ("to SW5 (Po4)", L3MEMBER) for p in ["Ethernet1/0", "Ethernet1/1"]}},
         "svis": [(10, "192.168.10.1"), (20, "192.168.20.1"), (99, "192.168.99.1")],
         "tail": "ip routing\nip route 0.0.0.0 0.0.0.0 10.1.5.5\n!\n"},
 "SW2": {"pos": {"Port-channel1": ("to SW1 Po1 (LACP)", TRUNK), "Port-channel3": ("to SW4 Po3 (PAgP)", TRUNK)},
         "ports": {**members(["Ethernet0/0", "Ethernet0/1"], 1, "active", "to SW1"),
                   **members(["Ethernet0/2", "Ethernet0/3"], 3, "desirable", "to SW4")},
         "svis": [(99, "192.168.99.202")]},
 "SW3": {"pos": {"Port-channel2": ("to SW1 Po2 (LACP)", TRUNK)},
         "ports": {**members(["Ethernet0/0", "Ethernet0/1"], 2, "passive", "to SW1"),
                   "Ethernet1/0": ("PC1", ["switchport mode access", "switchport access vlan 10", "spanning-tree portfast"])},
         "svis": [(99, "192.168.99.203")]},
 "SW4": {"pos": {"Port-channel3": ("to SW2 Po3 (PAgP)", TRUNK)},
         "ports": {**members(["Ethernet0/0", "Ethernet0/1"], 3, "auto", "to SW2"),
                   "Ethernet1/0": ("PC2", ["switchport mode access", "switchport access vlan 20", "spanning-tree portfast"])},
         "svis": [(99, "192.168.99.204")]},
 "SW5": {"l3": True,
         "loops": "interface Loopback0\n ip address 10.255.255.5 255.255.255.255\n!\n"
                  "interface Loopback1\n description simulated Internet\n ip address 203.0.113.1 255.255.255.0\n!\n",
         "pos": {"Port-channel4": ("to SW1 Po4 (L3 LACP)", ["no switchport", "ip address 10.1.5.5 255.255.255.0"])},
         "ports": {p: ("to SW1 (Po4)", L3MEMBER) for p in ["Ethernet0/0", "Ethernet0/1"]},
         "svis": [],
         "tail": "ip routing\nip route 192.168.0.0 255.255.0.0 10.1.5.1\n!\n"},
}

# Faults: node -> list of (where, old or None (append), new)
FAULTS = {
 "SW3": [("Ethernet0/0", "channel-group 2 mode passive", "channel-group 2 mode on"),     # F1 static bundle facing LACP
         ("Ethernet0/1", "channel-group 2 mode passive", "channel-group 2 mode on"),
         ("Ethernet0/1", ALLOWED, "switchport trunk allowed vlan 10,20")],             # F2 one member differs -> suspended
 "SW4": [("Ethernet0/0", "channel-group 3 mode auto", "channel-group 3 mode active"),   # F3 LACP facing PAgP
         ("Ethernet0/1", "channel-group 3 mode auto", "channel-group 3 mode active")],
 "SW2": [(w, ALLOWED, "switchport trunk allowed vlan 10,99")                            # F4 VLAN 20 removed at the bundle
         for w in ("Port-channel3", "Ethernet0/2", "Ethernet0/3")],
 # F5 one member link passive on both ends. (A member in the wrong group number was tried first: which link SW5
 # bundled was a race, so it sometimes took the Internet down outright instead of halving Po4.)
 "SW1": [("Ethernet1/1", "channel-group 4 mode active", "channel-group 4 mode passive")],
 "SW5": [("Ethernet0/1", "channel-group 4 mode active", "channel-group 4 mode passive")],
}


def _apply(h, where, lines, mode):
    out = list(lines)
    if mode != "ts":
        return out
    for w, old, new in FAULTS.get(h, []):
        if w != where:
            continue
        if old is None:
            out.append(new)
        else:
            out = [new if l == old else l for l in out]
    return out


def _intf(h, name, desc, lines, mode):
    s = f"interface {name}\n description {desc}\n" + "".join(f" {l}\n" for l in _apply(h, name, lines, mode))
    return s + (" no shutdown\n" if name.startswith("Ethernet") else "") + "!\n"


def sw_config(h, mode):
    d = SW[h]
    out = [HEAD.format(h=h), "" if d.get("l3") else L2HEAD, d.get("loops", "")]
    # Port-channels first so member ports can join them (the L3 one needs "no switchport" before its members do)
    out += [_intf(h, n, desc, lines, mode) for n, (desc, lines) in d["pos"].items()]
    for p in PHYS:
        if p in d["ports"]:
            desc, lines = d["ports"][p]
            out.append(_intf(h, p, desc, lines, mode))
        else:
            out.append(f"interface {p}\n shutdown\n!\n")
    out += [f"interface Vlan{v}\n ip address {ip} 255.255.255.0\n no shutdown\n!\n" for v, ip in d["svis"]]
    # IOL-L2 runs with ip routing on by default, which makes it ignore ip default-gateway
    out.append(d.get("tail", "no ip routing\nip default-gateway 192.168.99.1\n!\n"))
    out.append(LINES)
    return "".join(out)


PCS = {"PC1": ("192.168.10.10/24", "192.168.10.1"), "PC2": ("192.168.20.10/24", "192.168.20.1")}


def pc_config(h):
    ip, gw = PCS[h]
    return (f"# this is a shell script which will be sourced at boot\nhostname {h}\nUSERNAME=cisco\nPASSWORD=cisco\n"
            f"ip address add {ip} dev eth0\nip link set dev eth0 up\nip route add default via {gw}\n")


ORDER = ["SW5", "SW1", "SW2", "SW3", "SW4", "PC1", "PC2"]
POS = {"SW5": (-240, -400), "SW1": (-240, -160), "SW2": (240, -160), "SW3": (-240, 120), "SW4": (240, 120),
       "PC1": (-240, 340), "PC2": (240, 340)}
LABELS = {
 "SW5": "SW5  Internet edge (L3)  cisco/cisco\nLo0 10.255.255.5/32\nLo1 203.0.113.1/24 (Internet)\nPo4 10.1.5.5/24 (e0/0-1)",
 "SW1": "SW1  distribution  cisco/cisco\nPo4 10.1.5.1/24 (e1/0-1 -> SW5)\nVlan10 192.168.10.1/24\nVlan20 192.168.20.1/24\n"
        "Vlan99 192.168.99.1/24\nPo1 e0/0-1 -> SW2   Po2 e0/2-3 -> SW3",
 "SW2": "SW2  distribution  cisco/cisco\nVlan99 192.168.99.202/24\nPo1 e0/0-1 -> SW1   Po3 e0/2-3 -> SW4",
 "SW3": "SW3  access  cisco/cisco\nVlan99 192.168.99.203/24\nPo2 e0/0-1 -> SW1\ne1/0 PC1 (vlan 10)",
 "SW4": "SW4  access  cisco/cisco\nVlan99 192.168.99.204/24\nPo3 e0/0-1 -> SW2\ne1/0 PC2 (vlan 20)",
 "PC1": "PC1  cisco/cisco\neth0 192.168.10.10/24\ngw   192.168.10.1",
 "PC2": "PC2  cisco/cisco\neth0 192.168.20.10/24\ngw   192.168.20.1",
}
LINKS = [("SW5", "Ethernet0/0", "SW1", "Ethernet1/0"), ("SW5", "Ethernet0/1", "SW1", "Ethernet1/1"),
         ("SW1", "Ethernet0/0", "SW2", "Ethernet0/0"), ("SW1", "Ethernet0/1", "SW2", "Ethernet0/1"),
         ("SW1", "Ethernet0/2", "SW3", "Ethernet0/0"), ("SW1", "Ethernet0/3", "SW3", "Ethernet0/1"),
         ("SW2", "Ethernet0/2", "SW4", "Ethernet0/0"), ("SW2", "Ethernet0/3", "SW4", "Ethernet0/1"),
         ("SW3", "Ethernet1/0", "PC1", "eth0"), ("SW4", "Ethernet1/0", "PC2", "eth0")]


def ifaces():
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
            n.update(node_definition="ioll2-xe", image_definition="ioll2-xe-17-18-02", interfaces=ifaces(),
                     configuration=[{"name": "ios_config.txt", "content": sw_config(h, mode)}])
        else:
            n.update(node_definition="alpine", image_definition="alpine-base-3-23-3",
                     interfaces=[{"id": "i0", "label": "eth0", "slot": 0, "type": "physical"}],
                     configuration=[{"name": "node.cfg", "content": pc_config(h)}])
        nodes.append(n)
    links = [{"id": f"l{k}", "n1": ids[a], "i1": iface_id(a, ia), "n2": ids[b], "i2": iface_id(b, ib)}
             for k, (a, ia, b, ib) in enumerate(LINKS)]
    anns = []
    for h in ORDER:
        x, y = POS[h]
        dx = -320 if h in ("SW1", "SW3", "SW5") else 60
        dy = 40 if h.startswith("PC") else -20
        if h.startswith("PC"):
            dx = -70
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


TITLE = "[TSHOOT] ENCOR 3.1.b EtherChannel (LACP, PAgP, L3)"
DESC = "Troubleshooting: four bundles after a 'standardization' change — both PCs are down and the Internet uplink runs on one link."

if __name__ == "__main__":
    (TS / "solution/configs").mkdir(parents=True, exist_ok=True)
    for old in (TS / "solution/configs").glob("R1.cfg"):
        old.unlink()
    for h in SW:
        (TS / f"solution/configs/{h}.cfg").write_text(sw_config(h, "final"), encoding="utf-8", newline="\n")
    for h in PCS:
        (TS / f"solution/configs/{h}.cfg").write_text(pc_config(h), encoding="utf-8", newline="\n")
    write_yaml(TS / YAML_NAME, topology(TITLE, DESC, "ts"))
    if "--chunks" in sys.argv:
        OUT = Path(sys.argv[sys.argv.index("--chunks") + 1])
        OUT.mkdir(parents=True, exist_ok=True)
        t = topology("[TEST] etherchannel ts", "temporary test lab (start <=5 licensed nodes at a time)", "ts")
        t["annotations"] = []
        (OUT / "etherchannel.json").write_text(json.dumps(t), encoding="utf-8")
    print("done")
