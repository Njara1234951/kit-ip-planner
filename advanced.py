"""Moteur de calcul du plan d'adressage IP d'un kit d'installation.

Aucune dépendance externe : uniquement la bibliothèque standard Python.
Utilisé par l'interface (main.py) et par les tests.
"""
from __future__ import annotations

import csv
import ipaddress
import math
from dataclasses import dataclass, field


@dataclass(frozen=True)
class DeviceType:
    key: str
    label: str
    prefix: str
    classic_start: int      # première adresse du bloc dans un réseau « classique »
    poe_watts: float = 0.0  # consommation PoE moyenne par équipement


# L'ordre ici est l'ordre d'attribution des adresses.
DEVICE_TYPES: list[DeviceType] = [
    DeviceType("gateway", "Routeur / Passerelle", "GW", 1),
    DeviceType("switch", "Switch", "SW", 2),
    DeviceType("nvr", "Enregistreur NVR/DVR", "NVR", 10),
    DeviceType("ap", "Borne Wi-Fi", "AP", 20, 15.0),
    DeviceType("intercom", "Interphone / Contrôle d'accès", "ACC", 30, 8.0),
    DeviceType("printer", "Imprimante", "PRN", 40),
    DeviceType("other", "Autre équipement", "DEV", 50),
    DeviceType("camera", "Caméra IP", "CAM", 100, 8.0),
]
TYPES_BY_KEY = {t.key: t for t in DEVICE_TYPES}

# Équipements qui occupent un port de switch (tout sauf la passerelle et les switchs eux-mêmes).
_PORT_KEYS = [t.key for t in DEVICE_TYPES if t.key not in ("gateway", "switch")]


@dataclass
class Row:
    name: str
    type_label: str
    ip: str
    netmask: str
    gateway: str


@dataclass
class Plan:
    network: ipaddress.IPv4Network
    gateway: str
    rows: list[Row]
    layout: str                      # « classique » ou « compact »
    stats: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def summary_text(self) -> str:
        s = self.stats
        lines = [
            f"Réseau : {self.network}   Masque : {self.network.netmask}",
            f"Passerelle : {self.gateway}   Broadcast : {self.network.broadcast_address}",
            f"Adresses utilisées : {s['used']} / {s['hosts']} ({s['usage_pct']:.0f} %)   "
            f"Disposition : {self.layout}",
        ]
        if s["ports_needed"]:
            lines.append(
                f"Ports switch nécessaires : {s['ports_needed']}   "
                f"Switchs de {s['ports_per_switch']} ports recommandés : {s['switches_recommended']}"
            )
        if s["poe_watts"]:
            lines.append(f"Puissance PoE estimée : {s['poe_watts']:.0f} W (avec marge 25 % : {s['poe_with_margin_w']:.0f} W, moyenne estimée par switch : {s['poe_per_switch_w']:.0f} W)")
        if s["cameras"]:
            lines.append(
                f"Débit caméras : {s['bandwidth_mbps']:.0f} Mb/s   "
                f"Stockage : {s['storage_gb_day']:.0f} Go/jour, "
                f"{s['storage_tb']:.1f} To brut / {s['storage_tb_recommended']:.1f} To conseillé (+20 %) pour {s['retention_days']} jours (continu)"
            )
        for w in self.warnings:
            lines.append(f"⚠ {w}")
        return "\n".join(lines)


def parse_network(text: str) -> ipaddress.IPv4Network:
    text = (text or "").strip()
    if "/" not in text:
        raise ValueError("Ajoute le masque au réseau, par exemple 192.168.1.0/24.")
    try:
        net = ipaddress.ip_network(text, strict=False)
    except ValueError as exc:
        raise ValueError(f"Réseau invalide : « {text} ». Exemple : 192.168.1.0/24.") from exc
    if net.version != 4:
        raise ValueError("Seul l'IPv4 est géré.")
    if net.prefixlen > 30:
        raise ValueError("Le masque doit être /30 ou plus large (par exemple /24).")
    return net


def suggest_prefix(devices: int, spare: float = 0.25) -> int:
    """Plus petit préfixe pouvant contenir `devices` équipements + une marge."""
    needed = math.ceil(devices * (1 + spare))
    for prefix in range(30, 7, -1):
        if 2 ** (32 - prefix) - 2 >= needed:
            return prefix
    return 8


def _classic_layout(blocks, host_count: int, gateway_last: bool):
    starts = {}
    for t, n in blocks:
        starts[t.key] = host_count if (t.key == "gateway" and gateway_last) else t.classic_start
    prev_end = 0
    for start, end in sorted((starts[t.key], starts[t.key] + n - 1) for t, n in blocks):
        if start <= prev_end or end > host_count:
            return None
        prev_end = end
    return starts


def _compact_layout(blocks, host_count: int, gateway_last: bool):
    starts, cursor = {}, 1
    for t, n in blocks:
        if t.key == "gateway" and gateway_last:
            starts[t.key] = host_count
            continue
        starts[t.key] = cursor
        cursor += n
    return starts


def build_plan(
    network: str,
    counts: dict[str, int],
    gateway_last: bool = False,
    ports_per_switch: int = 24,
    bitrate_mbps: float = 4.0,
    retention_days: int = 30,
    poe_budget_w: float = 0.0,
) -> Plan:
    net = parse_network(network)
    host_count = net.num_addresses - 2

    clean: dict[str, int] = {}
    for key, value in counts.items():
        if key not in TYPES_BY_KEY or key == "gateway":
            continue
        try:
            number = int(value)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(f"La quantité pour « {TYPES_BY_KEY[key].label} » doit être un entier.") from exc
        if isinstance(value, float) and not value.is_integer():
            raise ValueError(f"La quantité pour « {TYPES_BY_KEY[key].label} » doit être un entier.")
        if number < 0:
            raise ValueError("Les quantités ne peuvent pas être négatives.")
        clean[key] = number
    if isinstance(ports_per_switch, bool) or not isinstance(ports_per_switch, int) or ports_per_switch < 2:
        raise ValueError("Un switch doit avoir au moins 2 ports (valeur entière).")
    try:
        bitrate_mbps = float(bitrate_mbps)
        poe_budget_w = float(poe_budget_w)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("Débit et budget PoE doivent être des nombres valides.") from exc
    if not all(math.isfinite(v) for v in (bitrate_mbps, poe_budget_w)):
        raise ValueError("Débit et budget PoE doivent être des nombres valides (pas NaN ou infini).")
    if bitrate_mbps < 0 or retention_days < 0 or poe_budget_w < 0:
        raise ValueError("Débit, durée et budget PoE ne peuvent pas être négatifs.")
    if isinstance(retention_days, bool) or not isinstance(retention_days, int):
        raise ValueError("La durée de rétention doit être un nombre entier de jours.")

    clean["gateway"] = 1
    blocks = [(t, clean.get(t.key, 0)) for t in DEVICE_TYPES if clean.get(t.key, 0) > 0]
    total = sum(n for _, n in blocks)

    if total > host_count:
        raise ValueError(
            f"{total} équipements pour seulement {host_count} adresses dans {net}. "
            f"Utilise au moins un /{suggest_prefix(total)}."
        )

    starts = _classic_layout(blocks, host_count, gateway_last)
    layout = "classique"
    if starts is None:
        starts = _compact_layout(blocks, host_count, gateway_last)
        layout = "compact"

    rows: list[Row] = []
    gateway_ip = str(net.network_address + starts["gateway"])
    netmask = str(net.netmask)
    for t, n in blocks:
        for i in range(n):
            ip = str(net.network_address + starts[t.key] + i)
            name = t.prefix if t.key == "gateway" else f"{t.prefix}-{i + 1:02d}"
            rows.append(Row(name, t.label, ip, netmask, gateway_ip))

    # --- Statistiques et avertissements -----------------------------------
    warnings: list[str] = []
    usage_pct = total / host_count * 100
    if usage_pct >= 80:
        warnings.append(
            f"Réseau rempli à {usage_pct:.0f} %. Prévois plutôt un /{suggest_prefix(total)}."
        )
    if not net.is_private:
        warnings.append("Réseau en adresses publiques : préfère 192.168.x.x, 10.x.x.x ou 172.16-31.x.x.")

    ports_needed = sum(clean.get(k, 0) for k in _PORT_KEYS)
    switches_have = clean.get("switch", 0)
    switches_recommended = 0
    if ports_needed:
        n = 1
        while True:
            usable = n * ports_per_switch - (2 * (n - 1) if n > 1 else 0) - 1  # liaisons montantes
            if usable >= ports_needed:
                break
            n += 1
        switches_recommended = n
        if switches_have < switches_recommended:
            warnings.append(
                f"{switches_have} switch(s) prévu(s) mais {switches_recommended} nécessaire(s) "
                f"({ports_needed} ports + liaisons montantes, switchs de {ports_per_switch} ports)."
            )

    poe_watts = sum(TYPES_BY_KEY[k].poe_watts * clean.get(k, 0) for k in TYPES_BY_KEY)
    if poe_budget_w and poe_watts * 1.25 > poe_budget_w:
        warnings.append(
            f"PoE : consommation estimée {poe_watts:.0f} W, avec marge 25 % {poe_watts * 1.25:.0f} W, supérieure au budget saisi ({poe_budget_w:.0f} W)."
        )

    cameras = clean.get("camera", 0)
    bandwidth = cameras * bitrate_mbps
    storage_gb_day = bandwidth * 10.8          # 1 Mb/s = 10,8 Go par jour
    storage_tb = storage_gb_day * retention_days / 1000
    storage_tb_recommended = storage_tb * 1.20  # marge 20 % pour variations et réserve
    if cameras and bitrate_mbps == 0:
        warnings.append("Débit par caméra nul : l'estimation de bande passante et de stockage est nulle.")
    if cameras and not clean.get("nvr", 0):
        warnings.append("Aucun enregistreur : les caméras n'auront pas de stockage centralisé.")
    if bandwidth > 800:
        warnings.append(f"Débit caméras de {bandwidth:.0f} Mb/s : une liaison gigabit sera saturée.")

    stats = {
        "hosts": host_count, "used": total, "usage_pct": usage_pct, "cameras": cameras,
        "ports_needed": ports_needed, "ports_per_switch": ports_per_switch,
        "switches_recommended": switches_recommended, "poe_watts": poe_watts,
        "bandwidth_mbps": bandwidth, "storage_gb_day": storage_gb_day,
        "storage_tb": storage_tb, "storage_tb_recommended": storage_tb_recommended, "retention_days": retention_days,
        "poe_with_margin_w": poe_watts * 1.25,
        "poe_per_switch_w": poe_watts / max(switches_have or switches_recommended or 1, 1),
    }
    return Plan(net, gateway_ip, rows, layout, stats, warnings)


CSV_HEADER = ["Nom", "Type", "Adresse IP", "Masque", "Passerelle", "Adresse MAC", "Emplacement", "Notes"]


def export_csv(plan: Plan, path: str) -> None:
    """CSV avec point-virgule et BOM UTF-8 : s'ouvre directement dans Excel en français."""
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(CSV_HEADER)
        for r in plan.rows:
            writer.writerow([r.name, r.type_label, r.ip, r.netmask, r.gateway, "", "", ""])
