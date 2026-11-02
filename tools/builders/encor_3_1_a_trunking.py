# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6"]
# ///
"""Build configs + topology for the ENCOR 3.1.a 802.1Q trunking troubleshooting lab (ts-trunking).

One source of truth for the final (healthy) and faulted configs. After running, run tools/sync_notes.py.
Usage: uv run tools/builders/encor_3_1_a_trunking.py [--chunks DIR]   (DIR: full ts lab as JSON for the MCP;
       test it by starting <=5 licensed nodes at a time)
"""
import json, sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
TS = REPO / "labs/encor/3-infrastructure/switching/ts-trunking"
YAML_NAME = "encor-3.1.a-switching-ts-trunking.yaml"

HEAD = """hostname {h}
no ip domain lookup
ip domain name lab.local
enable secret cisco
username cisco privilege 15 secret cisco
!
"""
VLANS = [(10, "SALES"), (20, "ENGINEERING"), (30, "FINANCE"), (99, "MGMT"), (999, "NATIVE-UNUSED")]
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
ALLOWED = "switchport trunk allowed vlan 10,20,30,99"
TRUNK = ["switchport trunk encapsulation dot1q", "switchport trunk native vlan 999", ALLOWED]
EDGE = ["spanning-tree portfast"]
PHYS = [f"Ethernet{s}/{p}" for s in range(2) for p in range(4)]


def access(vlan):
    return ["switchport mode access", f"switchport access vlan {vlan}"] + EDGE


# switch -> ports {iface: (description, lines)}, mgmt SVI address
SW = {
 "SW1": {"mgmt": "192.168.99.201",
         "ports": {"Ethernet0/0": ("to R1 e0/0 (router-on-a-stick)", TRUNK + ["switchport mode trunk", "switchport nonegotiate"]),
                   "Ethernet0/1": ("to SW2 e0/0", TRUNK + ["switchport mode dynamic desirable"]),
                   "Ethernet0/2": ("to SW3 e0/0", TRUNK + ["switchport mode trunk"])}},
 "SW2": {"mgmt": "192.168.99.202",
         "ports": {"Ethernet0/0": ("to SW1 e0/1", TRUNK + ["switchport mode dynamic auto"]),
                   "Ethernet1/0": ("PC1", access(10)), "Ethernet1/1": ("PC2", access(20))}},
 "SW3": {"mgmt": "192.168.99.203",
         "ports": {"Ethernet0/0": ("to SW1 e0/2", TRUNK + ["switchport mode dynamic auto"]),
                   "Ethernet1/0": ("PC3", access(30)), "Ethernet1/1": ("PC4", access(10))}},
}
R1_SUBIFS = [(10, "192.168.10.1"), (20, "192.168.20.1"), (30, "192.168.30.1"), (99, "192.168.99.1")]

# Faults: node -> list of (where, old or None (append), new). where = interface, "vlans" (remove a VLAN) or subif number.
FAULTS = {
 "R1": [("sub20", "encapsulation dot1Q 20", "encapsulation dot1Q 200")],                 # F1 wrong tag on router
 "SW2": [("Ethernet0/0", "switchport trunk native vlan 999", "switchport trunk native vlan 99")],  # F2 native mismatch
 "SW1": [("Ethernet0/2", None, "switchport nonegotiate"),                               # F3 DTP off vs dynamic auto
         ("vlans", 30, None),                                                           # F4 VLAN 30 missing on transit
         ("Ethernet0/1", ALLOWED, "switchport trunk allowed vlan 10,30,99")],          # F5 VLAN 20 not allowed
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


def sw_config(h, mode):
    d = SW[h]
    out = [HEAD.format(h=h), "vtp domain LAB\nvtp mode transparent\n!\n"]
    removed = [o for w, o, _ in FAULTS.get(h, []) if w == "vlans"] if mode == "ts" else []
    out += [f"vlan {v}\n name {n}\n" for v, n in VLANS if v not in removed]
    out.append("!\nspanning-tree mode rapid-pvst\n!\n")
    for p in PHYS:
        if p not in d["ports"]:
            out.append(f"interface {p}\n shutdown\n!\n")
            continue
        desc, lines = d["ports"][p]
        out.append(f"interface {p}\n description {desc}\n" + "".join(f" {l}\n" for l in _apply(h, p, lines, mode))
                   + " no shutdown\n!\n")
    # IOL-L2 runs with ip routing on by default, which makes it ignore ip default-gateway
    out.append(f"interface Vlan99\n ip address {d['mgmt']} 255.255.255.0\n no shutdown\n!\n"
               "no ip routing\nip default-gateway 192.168.99.1\n!\n")
    out.append(LINES)
    return "".join(out)


def r1_config(mode):
    out = [HEAD.format(h="R1"), "interface Loopback0\n ip address 10.255.255.1 255.255.255.255\n!\n",
           "interface Ethernet0/0\n description trunk to SW1 e0/0\n no ip address\n no shutdown\n!\n"]
    for vlan, ip in R1_SUBIFS:
        lines = _apply("R1", f"sub{vlan}", [f"encapsulation dot1Q {vlan}"], mode) + [f"ip address {ip} 255.255.255.0"]
        out.append(f"interface Ethernet0/0.{vlan}\n" + "".join(f" {l}\n" for l in lines) + "!\n")
    out.append("interface Ethernet0/0.999\n description native VLAN (no IP)\n encapsulation dot1Q 999 native\n!\n")
    out += [f"interface {p}\n no ip address\n shutdown\n!\n" for p in PHYS[1:4]]
    out.append(LINES)
    return "".join(out)


PCS = {"PC1": ("192.168.10.10/24", "192.168.10.1"), "PC2": ("192.168.20.10/24", "192.168.20.1"),
       "PC3": ("192.168.30.10/24", "192.168.30.1"), "PC4": ("192.168.10.11/24", "192.168.10.1")}


def pc_config(h):
    ip, gw = PCS[h]
    return (f"# this is a shell script which will be sourced at boot\nhostname {h}\nUSERNAME=cisco\nPASSWORD=cisco\n"
            f"ip address add {ip} dev eth0\nip link set dev eth0 up\nip route add default via {gw}\n")


ORDER = ["R1", "SW1", "SW2", "SW3", "PC1", "PC2", "PC3", "PC4"]
POS = {"R1": (0, -360), "SW1": (0, -160), "SW2": (-280, 80), "SW3": (280, 80),
       "PC1": (-400, 300), "PC2": (-160, 300), "PC3": (160, 300), "PC4": (400, 300)}
LABELS = {
 "R1": "R1  router-on-a-stick  cisco/cisco\nLo0     10.255.255.1/32\ne0/0.10 192.168.10.1/24\ne0/0.20 192.168.20.1/24\n"
       "e0/0.30 192.168.30.1/24\ne0/0.99 192.168.99.1/24\ne0/0.999 native (no IP)",
 "SW1": "SW1  distribution  cisco/cisco\nVlan99 192.168.99.201/24\ne0/0 -> R1   e0/1 -> SW2   e0/2 -> SW3",
 "SW2": "SW2  access  cisco/cisco\nVlan99 192.168.99.202/24\ne0/0 -> SW1 e0/1\ne1/0 PC1 (vlan 10)  e1/1 PC2 (vlan 20)",
 "SW3": "SW3  access  cisco/cisco\nVlan99 192.168.99.203/24\ne0/0 -> SW1 e0/2\ne1/0 PC3 (vlan 30)  e1/1 PC4 (vlan 10)",
 "PC1": "PC1  cisco/cisco\neth0 192.168.10.10/24\ngw   192.168.10.1",
 "PC2": "PC2  cisco/cisco\neth0 192.168.20.10/24\ngw   192.168.20.1",
 "PC3": "PC3  cisco/cisco\neth0 192.168.30.10/24\ngw   192.168.30.1",
 "PC4": "PC4  cisco/cisco\neth0 192.168.10.11/24\ngw   192.168.10.1",
}
LINKS = [("R1", "Ethernet0/0", "SW1", "Ethernet0/0"), ("SW1", "Ethernet0/1", "SW2", "Ethernet0/0"),
         ("SW1", "Ethernet0/2", "SW3", "Ethernet0/0"), ("SW2", "Ethernet1/0", "PC1", "eth0"),
         ("SW2", "Ethernet1/1", "PC2", "eth0"), ("SW3", "Ethernet1/0", "PC3", "eth0"), ("SW3", "Ethernet1/1", "PC4", "eth0")]


def ifaces(h):
    names = ["Loopback0"] + (PHYS[:4] if h == "R1" else PHYS)
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
        if h == "R1":
            n.update(node_definition="iol-xe", image_definition="iol-xe-17-18-02", interfaces=ifaces(h),
                     configuration=[{"name": "ios_config.txt", "content": r1_config(mode)}])
        elif h.startswith("SW"):
            n.update(node_definition="ioll2-xe", image_definition="ioll2-xe-17-18-02", interfaces=ifaces(h),
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
        dx = 60 if h in ("R1", "SW1", "SW3") else -300
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


TITLE = "[TSHOOT] ENCOR 3.1.a 802.1Q Trunking and DTP"
DESC = "Troubleshooting: router-on-a-stick campus after a VLAN rollout — three of four PCs and one switch are unreachable."

if __name__ == "__main__":
    (TS / "solution/configs").mkdir(parents=True, exist_ok=True)
    (TS / "solution/configs/R1.cfg").write_text(r1_config("final"), encoding="utf-8", newline="\n")
    for h in SW:
        (TS / f"solution/configs/{h}.cfg").write_text(sw_config(h, "final"), encoding="utf-8", newline="\n")
    for h in PCS:
        (TS / f"solution/configs/{h}.cfg").write_text(pc_config(h), encoding="utf-8", newline="\n")
    write_yaml(TS / YAML_NAME, topology(TITLE, DESC, "ts"))
    if "--chunks" in sys.argv:
        OUT = Path(sys.argv[sys.argv.index("--chunks") + 1])
        OUT.mkdir(parents=True, exist_ok=True)
        t = topology("[TEST] trunking ts", "temporary test lab (start <=5 licensed nodes at a time)", "ts")
        t["annotations"] = []
        (OUT / "trunking.json").write_text(json.dumps(t), encoding="utf-8")
    print("done")
