# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6"]
# ///
"""Build configs + topology files for the ENCOR 5.2.a ACL lab pair (learn-acl + ts-acl).

One source of truth for every variant. After running, run tools/sync_notes.py.
  learn boot  ("clean"):  addressing + OSPF up, no ACLs (the topic is ACLs, not routing)
  final       ("final"):  learn end state: CONTRACTORS-IN (with time-range), BRANCH-IN, VTY-ADMIN on R1 and R2
  intended    ("design"): ts design = final without the time-range (TS symptoms must not depend on the clock)
  ts boot     ("ts"):     design + the injected faults (see FAULTS)
Usage: uv run tools/builders/encor_5_2_a_acl.py [--chunks DIR]   (DIR: both labs as JSON for the MCP;
       each lab is 5 licensed nodes, so a chunk is the whole lab)
"""
import json, sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
TOPIC = REPO / "labs/encor/5-security/infra-security"
LEARN, TS = TOPIC / "learn-acl", TOPIC / "ts-acl"
LEARN_YAML, TS_YAML = "encor-5.2.a-infra-security-learn-acl.yaml", "encor-5.2.a-infra-security-ts-acl.yaml"

BASE = """hostname {h}
no ip domain lookup
ip domain name lab.local
enable secret cisco
username cisco privilege 15 secret cisco
crypto key generate rsa modulus 2048
!
"""
LINES = """line con 0
 exec-timeout 0 0
 logging synchronous
 privilege level 15
line vty 0 4
 login local
 transport input ssh telnet
{vty}!
end
"""
PHYS = [f"Ethernet0/{i}" for i in range(4)]

# interface -> (ip mask, description, ospf passive); unlisted Ethernet0/x are shut
INTS = {
 "R1": [("Loopback0", "10.255.255.1 255.255.255.255", None),
        ("Ethernet0/0", "10.1.2.1 255.255.255.0", "HQ R2 e0/0"),
        ("Ethernet0/1", "192.168.10.1 255.255.255.0", "VLAN 10 Staff (PC1)"),
        ("Ethernet0/2", "192.168.11.1 255.255.255.0", "VLAN 11 Contractors (PC2)")],
 "R2": [("Loopback0", "10.255.255.2 255.255.255.255", None),
        ("Loopback1", "172.18.0.1 255.255.255.0", "HQ users (simulated)"),
        ("Ethernet0/0", "10.1.2.2 255.255.255.0", "Branch R1 e0/0"),
        ("Ethernet0/1", "192.168.50.1 255.255.255.0", "VLAN 50 Servers (SRV1)")],
}
PASSIVE = {"R1": ["Ethernet0/1", "Ethernet0/2"], "R2": ["Loopback1", "Ethernet0/1"]}

# ACL blocks per router (final = learn end state). Interface bindings are separate so the faults can move them.
ACLS = {
 "R1": """time-range BUSINESS-HOURS
 periodic weekdays 8:00 to 17:00
!
ip access-list standard VTY-ADMIN
 10 permit 192.168.10.0 0.0.0.255
!
ip access-list extended CONTRACTORS-IN
 10 permit tcp 192.168.11.0 0.0.0.255 host 192.168.50.10 eq www time-range BUSINESS-HOURS
 20 permit icmp 192.168.11.0 0.0.0.255 host 192.168.50.10 echo
 30 deny ip 192.168.11.0 0.0.0.255 192.168.50.0 0.0.0.255 log
 40 permit ip 192.168.11.0 0.0.0.255 any
!
ip access-list extended BRANCH-IN
 10 permit ospf any any
 20 permit tcp any 192.168.10.0 0.0.1.255 established
 30 permit icmp any any
 40 deny ip any any log
!
""",
 "R2": """ip access-list standard VTY-ADMIN
 10 permit 192.168.10.0 0.0.0.255
!
""",
}
BIND = {"R1": {"Ethernet0/0": " ip access-group BRANCH-IN in\n", "Ethernet0/2": " ip access-group CONTRACTORS-IN in\n"},
        "R2": {}}
VTY = " access-class VTY-ADMIN in\n"

# Troubleshooting faults: (router, find, replace) applied to the "design" config text.
# Numbered as in ts-acl/solution/README.md (the order a learner usually meets them).
FAULTS = [
 # Fault 1 BRANCH-IN has no OSPF permit: the implicit deny drops R2's hellos, the branch loses every route
 ("R1", " 10 permit ospf any any\n", ""),
 # Fault 2 CONTRACTORS-IN bound outbound: traffic *to* PC2 never has a 192.168.11.x source, so the implicit
 #         deny drops all of it; contractors reach nothing beyond R1
 ("R1", " ip access-group CONTRACTORS-IN in\n", " ip access-group CONTRACTORS-IN out\n"),
 # Fault 3 established line covers VLAN 10 only: contractors' TCP replies (SYN-ACK) are dropped by line 40
 ("R1", " 20 permit tcp any 192.168.10.0 0.0.1.255 established\n", " 20 permit tcp any 192.168.10.0 0.0.0.255 established\n"),
 # Fault 4 ping permit added after the deny (appended at seq 50): contractors can't ping SRV1
 ("R1", " 20 permit icmp 192.168.11.0 0.0.0.255 host 192.168.50.10 echo\n 30 deny ",
        " 30 deny "),
 ("R1", " 40 permit ip 192.168.11.0 0.0.0.255 any\n",
        " 40 permit ip 192.168.11.0 0.0.0.255 any\n 50 permit icmp 192.168.11.0 0.0.0.255 host 192.168.50.10 echo\n"),
 # Fault 5 R2 VTY-ADMIN written with a subnet mask instead of a wildcard: matches only x.x.x.0, staff locked out
 ("R2", " 10 permit 192.168.10.0 0.0.0.255\n", " 10 permit 192.168.10.0 255.255.255.0\n"),
]


def config(h, mode):
    """mode: clean | final | design | ts"""
    out = [BASE.format(h=h)]
    acl = ACLS[h] if mode != "clean" else ""
    if mode in ("design", "ts"):  # no time-range in the TS design
        acl = acl.replace("time-range BUSINESS-HOURS\n periodic weekdays 8:00 to 17:00\n!\n", "")
        acl = acl.replace(" time-range BUSINESS-HOURS\n", "\n")
    out.append(acl)
    used = set()
    ints = []
    for name, ip, desc in INTS[h]:
        used.add(name)
        s = f"interface {name}\n"
        if desc:
            s += f" description {desc}\n"
        s += f" ip address {ip}\n ip ospf 1 area 0\n"
        if name == "Loopback1":  # advertise the /24, not the loopback /32
            s += " ip ospf network point-to-point\n"
        if mode != "clean":
            s += BIND[h].get(name, "")
        if name.startswith("Ethernet"):
            s += " no shutdown\n"
        ints.append(s + "!\n")
    out += ints
    for p in PHYS:
        if p not in used:
            out.append(f"interface {p}\n no ip address\n shutdown\n!\n")
    n = h[1:]
    out.append(f"router ospf 1\n router-id 10.255.255.{n}\n"
               + "".join(f" passive-interface {i}\n" for i in PASSIVE[h]) + "!\n")
    out.append(LINES.format(vty=VTY if mode != "clean" else ""))
    text = "".join(out)
    if mode == "ts":
        for r, old, new in FAULTS:
            if r == h:
                assert text.count(old) == 1, (h, old)
                text = text.replace(old, new)
    return text


PCS = {"PC1": ("192.168.10.10/24", "192.168.10.1"), "PC2": ("192.168.11.10/24", "192.168.11.1"),
       "SRV1": ("192.168.50.10/24", "192.168.50.1")}
# SRV1's "web server": busybox-extras httpd (not the busybox applet) serving one page on port 80; sshd runs by default
WEB = ("mkdir -p /srv/www\necho '<h1>SRV1 intranet</h1>' > /srv/www/index.html\n"
       "/usr/sbin/httpd -p 80 -h /srv/www\n")


def pc_config(h):
    ip, gw = PCS[h]
    s = (f"# this is a shell script which will be sourced at boot\nhostname {h}\nUSERNAME=cisco\nPASSWORD=cisco\n"
         f"ip address add {ip} dev eth0\nip link set dev eth0 up\nip route add default via {gw}\n")
    return s + (WEB if h == "SRV1" else "")


ORDER = ["R1", "R2", "PC1", "PC2", "SRV1"]
POS = {"PC1": (-600, -150), "PC2": (-600, 150), "R1": (-300, 0), "R2": (0, 0), "SRV1": (300, 0)}
LABELS = {
 "R1": "R1  branch  cisco/cisco\nLo0   10.255.255.1/32\ne0/0  10.1.2.1/24     (R2)\ne0/1  192.168.10.1/24 (VLAN 10)\ne0/2  192.168.11.1/24 (VLAN 11)",
 "R2": "R2  HQ  cisco/cisco\nLo0   10.255.255.2/32\nLo1   172.18.0.1/24\ne0/0  10.1.2.2/24     (R1)\ne0/1  192.168.50.1/24 (VLAN 50)",
 "PC1": "PC1  Staff  cisco/cisco\neth0 192.168.10.10/24\ngw   192.168.10.1",
 "PC2": "PC2  Contractor  cisco/cisco\neth0 192.168.11.10/24\ngw   192.168.11.1",
 "SRV1": "SRV1  intranet web  cisco/cisco\neth0 192.168.50.10/24\ngw   192.168.50.1",
}
# (a, a's Ethernet0/x, b, b's Ethernet0/x or eth0)
LINKS = [("R1", 0, "R2", 0), ("R1", 1, "PC1", None), ("R1", 2, "PC2", None), ("R2", 1, "SRV1", None)]


def iol_ifaces(h):
    names = [n for n, _, _ in INTS[h] if n.startswith("Loop")] + PHYS
    nl = sum(n.startswith("Loop") for n in names)
    return [{"id": f"i{k}", "label": n, "type": "loopback" if n.startswith("Loop") else "physical",
             **({"slot": k - nl} if k >= nl else {})} for k, n in enumerate(names)]


def topology(title, description, mode):
    nodes, ids, ifid = [], {}, {}
    for k, h in enumerate(ORDER):
        nid = f"n{k}"; ids[h] = nid
        x, y = POS[h]
        n = {"id": nid, "label": h, "x": x, "y": y}
        if h in PCS:
            n.update(node_definition="alpine", image_definition="alpine-base-3-23-3",
                     interfaces=[{"id": "i0", "label": "eth0", "slot": 0, "type": "physical"}],
                     configuration=[{"name": "node.cfg", "content": pc_config(h)}])
            ifid[h] = {None: "i0"}
        else:
            ifs = iol_ifaces(h)
            n.update(node_definition="iol-xe", image_definition="iol-xe-17-18-02", interfaces=ifs,
                     configuration=[{"name": "ios_config.txt", "content": config(h, mode)}])
            ifid[h] = {i["slot"]: i["id"] for i in ifs if "slot" in i}
        nodes.append(n)
    links = [{"id": f"l{k}", "n1": ids[a], "i1": ifid[a][ia], "n2": ids[b], "i2": ifid[b][ib]}
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
 "learn": (LEARN, LEARN_YAML, "[LEARN] ENCOR 5.2.a ACLs",
           "Learning: filter a branch with standard, extended, named and time-based ACLs; placement, wildcards, implicit deny, established, vty access-class.",
           "clean", "final"),
 "ts": (TS, TS_YAML, "[TSHOOT] ENCOR 5.2.a ACLs",
        "Troubleshooting: after a branch ACL rollout, the branch is cut off from HQ and the access policy is wrong.",
        "ts", "design"),
}

if __name__ == "__main__":
    for d, fname, title, desc, boot, sol in LABS.values():
        (d / "solution/configs").mkdir(parents=True, exist_ok=True)
        for h in INTS:
            (d / f"solution/configs/{h}.cfg").write_text(config(h, sol), encoding="utf-8", newline="\n")
        for h in PCS:
            (d / f"solution/configs/{h}.cfg").write_text(pc_config(h), encoding="utf-8", newline="\n")
        write_yaml(d / fname, topology(title, desc, boot))
    if "--chunks" in sys.argv:
        OUT = Path(sys.argv[sys.argv.index("--chunks") + 1])
        OUT.mkdir(parents=True, exist_ok=True)
        for key, (d, fname, title, desc, boot, sol) in LABS.items():
            for mode in (boot, sol):
                t = topology(f"[TEST] acl {key} {mode}", "temporary test chunk", mode)
                t["annotations"] = []  # keeps the MCP payload small; annotations are validated on the real files
                (OUT / f"{key}-{mode}.json").write_text(json.dumps(t), encoding="utf-8")
    print("done")
