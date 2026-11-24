"""Fonctions avancées Kit IP Planner 3.0 : VLAN et répartition des équipements."""
from __future__ import annotations
import ipaddress
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class VLANAssignment:
    device: str
    vlan_id: int
    vlan_name: str
    ip: str
    subnet: str
    gateway: str


def validate_vlans(vlans: Iterable[dict]) -> list[dict]:
    """Valide les VLAN (ID, nom, IPv4, sous-réseaux non chevauchants)."""
    result, ids, names, networks = [], set(), set(), []
    for raw in vlans:
        try:
            vid = int(raw.get("id"))
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("Chaque VLAN doit avoir un ID entier.") from exc
        name = str(raw.get("name", "")).strip()
        purpose = str(raw.get("purpose", "")).strip()
        subnet_text = str(raw.get("subnet", "")).strip()
        if not 1 <= vid <= 4094:
            raise ValueError(f"ID VLAN {vid} invalide : la plage autorisée est 1 à 4094.")
        if not name:
            raise ValueError(f"Le VLAN {vid} doit avoir un nom.")
        if vid in ids:
            raise ValueError(f"ID VLAN dupliqué : {vid}.")
        if name.casefold() in names:
            raise ValueError(f"Nom VLAN dupliqué : {name}.")
        try:
            network = ipaddress.ip_network(subnet_text, strict=False)
        except ValueError as exc:
            raise ValueError(f"Sous-réseau invalide pour VLAN {vid} : {subnet_text}.") from exc
        if network.version != 4:
            raise ValueError("La gestion VLAN de cette version utilise IPv4 uniquement.")
        if network.prefixlen > 30:
            raise ValueError(f"VLAN {vid} : utiliser un sous-réseau /30 ou plus large pour des équipements.")
        for other_id, other in networks:
            if network.overlaps(other):
                raise ValueError(f"Les VLAN {vid} et {other_id} ont des sous-réseaux qui se chevauchent.")
        ids.add(vid); names.add(name.casefold()); networks.append((vid, network))
        result.append({"id": vid, "name": name, "subnet": str(network), "purpose": purpose})
    return result


def assign_vlan_ips(vlans: Iterable[dict], counts: dict[str, int], assignments: dict[str, int] | None = None,
                    gateway_offset: int = 1, device_offset: int = 10) -> list[VLANAssignment]:
    """Attribue les IP dans chaque VLAN. .1 est réservé à la passerelle, appareils à partir de .10."""
    clean = validate_vlans(vlans)
    assignments = assignments or {}
    by_id = {v["id"]: v for v in clean}
    result: list[VLANAssignment] = []
    cursors: dict[int, int] = {}
    for key, count in counts.items():
        if key == "gateway" or int(count) <= 0:
            continue
        vid = int(assignments.get(key, clean[0]["id"] if clean else 0))
        if vid not in by_id:
            raise ValueError(f"Le type {key} est affecté au VLAN {vid}, absent du projet.")
        vlan = by_id[vid]
        network = ipaddress.ip_network(vlan["subnet"])
        hosts = list(network.hosts())
        if gateway_offset < 1 or gateway_offset > len(hosts):
            raise ValueError(f"VLAN {vid} : offset de passerelle invalide.")
        gateway = str(hosts[gateway_offset - 1])
        # Reserve the gateway and allocate deterministically, skipping its address.
        available = [str(h) for h in hosts if str(h) != gateway]
        start = max(0, device_offset - 2)
        cursor = max(cursors.get(vid, 0), start)
        available = available[cursor:]
        if int(count) > len(available):
            raise ValueError(f"VLAN {vid} ({network}) : {count} appareils {key} demandés, seulement {len(available)} IP disponibles après réservations.")
        label = key.upper()
        for i in range(int(count)):
            result.append(VLANAssignment(f"{label}-{i+1:02d}", vid, vlan["name"], available[i], str(network), gateway))
        cursors[vid] = cursor + int(count)
    return result


@dataclass
class SwitchLoad:
    switch_number: int
    ports_used: int
    ports_available: int
    poe_used_w: float
    poe_budget_w: float | None
    devices: list[str]
    warnings: list[str]


def distribute_devices(devices: list[tuple[str, float]], switch_count: int, ports_per_switch: int,
                       poe_budget_per_switch_w: float | None = None, uplink_ports: int = 2) -> list[SwitchLoad]:
    """Répartition greedy, en réservant des ports uplink sur chaque switch.
    devices: liste (nom, puissance PoE W); 0 W pour équipements non PoE.
    """
    if switch_count < 1 or ports_per_switch < 2:
        raise ValueError("Il faut au moins un switch et deux ports par switch.")
    if uplink_ports < 0 or uplink_ports >= ports_per_switch:
        raise ValueError("Nombre de ports uplink réservé invalide.")
    capacity = ports_per_switch - uplink_ports
    loads = [[] for _ in range(switch_count)]
    watts = [0.0] * switch_count
    warnings = [[] for _ in range(switch_count)]
    # Place higher-power devices first to reduce the risk of PoE overload.
    for name, power in sorted(devices, key=lambda x: x[1], reverse=True):
        candidates = [i for i in range(switch_count) if len(loads[i]) < capacity]
        if not candidates:
            raise ValueError(f"Capacité de ports dépassée : impossible de placer {name} sur {switch_count} switch(s).")
        if poe_budget_per_switch_w is not None:
            feasible = [i for i in candidates if watts[i] + power <= poe_budget_per_switch_w]
            if feasible:
                candidates = feasible
            else:
                warnings[candidates[0]].append(f"Budget PoE dépassé en ajoutant {name} ({power:g} W).")
        target = min(candidates, key=lambda i: (watts[i], len(loads[i])))
        loads[target].append(name); watts[target] += power
    return [SwitchLoad(i+1, len(loads[i]), capacity-len(loads[i]), watts[i], poe_budget_per_switch_w,
                       loads[i], warnings[i]) for i in range(switch_count)]
