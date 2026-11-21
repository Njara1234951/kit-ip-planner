"""Export d'un inventaire chantier prêt à compléter."""
from __future__ import annotations
import csv
import re
from pathlib import Path

HEADER = ["Nom", "Type", "Adresse IP", "Masque", "Passerelle", "VLAN", "Adresse MAC", "Fabricant", "Modèle", "N° série", "Emplacement", "Notes"]
_MAC = re.compile(r"^(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}$")


def validate_inventory(rows: list[dict]) -> list[str]:
    errors = []
    ips, macs = set(), set()
    for i, row in enumerate(rows, start=2):
        ip = str(row.get("Adresse IP", "")).strip()
        mac = str(row.get("Adresse MAC", "")).strip()
        if ip:
            if ip in ips: errors.append(f"Ligne {i} : IP dupliquée {ip}.")
            ips.add(ip)
        if mac:
            if not _MAC.fullmatch(mac): errors.append(f"Ligne {i} : format MAC invalide ({mac}).")
            norm = mac.replace("-", ":").upper()
            if norm in macs: errors.append(f"Ligne {i} : MAC dupliquée {mac}.")
            macs.add(norm)
    return errors


def export_inventory(plan, path, vlan_by_type: dict[str, int] | None = None) -> None:
    vlan_by_type = vlan_by_type or {}
    with Path(path).open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(HEADER)
        for row in plan.rows:
            key = row.name.split("-", 1)[0].lower()
            writer.writerow([row.name, row.type_label, row.ip, row.netmask, row.gateway,
                            vlan_by_type.get(key, ""), "", "", "", "", "", ""])
