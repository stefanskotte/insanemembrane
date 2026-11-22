"""Board-geometry helpers shared by the build stages, so they work for every model.

Defaults reproduce the A1200 rev A exactly (31 contacts 0.75 x 6.35 mm from 0.35 mm of the tail end;
LED pads = circles r 1.3 on nets 31 / 9). A board_geom.json can override them with "contact" and "led_pads".
"""
import math

A1200_CONTACT = dict(from_end=0.35, len=6.35, w=0.75)


def contact(G):
    return G.get("contact", A1200_CONTACT)


def x_contact_in(G):
    c = contact(G)
    return G["tail"]["end_x"] - c["from_end"] - c["len"]


def contact_items(G):
    """[(net, Polygon)] for the tail contacts / fingers (half length + 0.025 as the A1200 stages used)"""
    c = contact(G)
    from shapely.geometry import Polygon
    hl, hw = c["len"] / 2 + 0.025, c["w"] / 2
    out = []
    for p in G["pins"]:
        x = p["x_end"] - c["from_end"] - c["len"] / 2
        out.append((str(p["pin"]), Polygon([(x - hl, p["y"] - hw), (x + hl, p["y"] - hw), (x + hl, p["y"] + hw), (x - hl, p["y"] + hw)])))
    return out


def led_items(G):
    """[(net, geometry)] for the LED pads"""
    from shapely.geometry import Point, Polygon
    from shapely import affinity
    if "led_pads" not in G:
        l1, l2 = G["led"]
        return [("31", Point(l1).buffer(1.3)), ("9", Point(l2).buffer(1.3))]
    out = []
    for p in G["led_pads"]:
        a, b = p["size"]
        r = Polygon([(-a / 2, -b / 2), (a / 2, -b / 2), (a / 2, b / 2), (-a / 2, b / 2)])
        r = affinity.rotate(r, p.get("angle", 0.0), origin=(0, 0))
        out.append((p["net"], affinity.translate(r, *p["pos"])))
    return out


def on_contact(G, net, P):
    """is point P on the contact of this net (used to keep trace ends that land on a contact)"""
    c = contact(G)
    for p in G["pins"]:
        if str(p["pin"]) == net and abs(P.y - p["y"]) < c["w"] / 2 + 0.025 and P.x > p["x_end"] - c["from_end"] - c["len"] - 0.3:
            return True
    return False
