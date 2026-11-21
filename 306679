"""Kit IP Planner 2.0: projet JSON, rapport PDF et schéma réseau SVG."""
from __future__ import annotations
import json
from pathlib import Path
from xml.sax.saxutils import escape
import ipaddress

from advanced import validate_vlans

DEFAULT_VLANS = [
    {"id": 10, "name": "Administration", "subnet": "192.168.10.0/24", "purpose": "Routeur, switchs, NVR"},
    {"id": 20, "name": "CCTV", "subnet": "192.168.20.0/24", "purpose": "Caméras IP"},
    {"id": 30, "name": "Wi-Fi", "subnet": "192.168.30.0/24", "purpose": "Bornes et clients Wi-Fi"},
    {"id": 40, "name": "Accès", "subnet": "192.168.40.0/24", "purpose": "Interphones et contrôle d'accès"},
]


def save_project(path, project):
    if not isinstance(project, dict):
        raise ValueError("Le projet doit être un objet JSON.")
    project = dict(project)
    project["vlans"] = validate_vlans(project.get("vlans", DEFAULT_VLANS))
    project["format"] = "kit-ip-planner-project"
    project["version"] = 3
    Path(path).write_text(json.dumps(project, ensure_ascii=False, indent=2), encoding="utf-8")


def load_project(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("format") != "kit-ip-planner-project" or data.get("version") not in (1, 2, 3):
        raise ValueError("Ce fichier n'est pas un projet Kit IP Planner reconnu.")
    data["vlans"] = validate_vlans(data.get("vlans", DEFAULT_VLANS))
    data["version"] = 3
    settings = data.get("settings", {})
    if not isinstance(settings, dict):
        raise ValueError("Les paramètres du projet sont invalides.")
    project = data.get("project", {})
    if not isinstance(project, dict):
        raise ValueError("Les informations du projet sont invalides.")
    return data


def generate_svg(plan, project_name="Projet réseau"):
    rows = plan.rows
    width, height = 1000, max(480, 150 + len(rows) * 28)
    # Diagramme conceptuel, sans prétendre représenter le câblage exact.
    boxes = [("Routeur / Passerelle", plan.gateway, 50, 40, 220, 80),
             ("Switch(s)", f"{plan.stats.get('switches_recommended', 0)} recommandé(s)", 390, 40, 220, 80),
             ("NVR", next((r.ip for r in rows if r.type_label.startswith("Enregistreur")), "Non prévu"), 730, 40, 220, 80)]
    cam_rows = [r for r in rows if r.type_label == "Caméra IP"]
    ap_rows = [r for r in rows if r.type_label == "Borne Wi-Fi"]
    other_rows = [r for r in rows if r.type_label not in ("Caméra IP", "Borne Wi-Fi", "Routeur / Passerelle", "Switch", "Enregistreur NVR/DVR")]
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
             '<rect width="100%" height="100%" fill="#f8fafc"/>',
             f'<text x="30" y="25" font-family="Arial" font-size="20" font-weight="bold" fill="#0f172a">{escape(project_name)}</text>']
    for label, detail, x, y, w, h in boxes:
        parts += [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="#e0f2fe" stroke="#0284c7" stroke-width="2"/>',
                  f'<text x="{x+w/2}" y="{y+30}" text-anchor="middle" font-family="Arial" font-size="16" font-weight="bold">{escape(label)}</text>',
                  f'<text x="{x+w/2}" y="{y+55}" text-anchor="middle" font-family="Arial" font-size="13">{escape(detail)}</text>']
    parts.append('<path d="M270 80 H390 M610 80 H730" stroke="#475569" stroke-width="3"/>')
    groups = [("Caméras", cam_rows), ("Bornes Wi-Fi", ap_rows), ("Autres équipements", other_rows)]
    y = 170
    for title, group in groups:
        if not group: continue
        parts.append(f'<text x="40" y="{y}" font-family="Arial" font-size="16" font-weight="bold" fill="#334155">{escape(title)} ({len(group)})</text>')
        y += 18
        for i, row in enumerate(group):
            x = 40 + (i % 4) * 230
            yy = y + (i // 4) * 65
            parts += [f'<rect x="{x}" y="{yy}" width="205" height="48" rx="8" fill="#fff" stroke="#94a3b8"/>',
                      f'<text x="{x+10}" y="{yy+19}" font-family="Arial" font-size="13" font-weight="bold">{escape(row.name)}</text>',
                      f'<text x="{x+10}" y="{yy+36}" font-family="Arial" font-size="12">{escape(row.ip)}</text>']
        y += ((len(group)+3)//4)*65 + 25
    parts.append('</svg>')
    return "\n".join(parts)


def export_pdf(plan, path, project_name="Projet réseau", client="", site="", vlans=None, vlan_assignments=None):
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
    except ImportError as exc:
        raise RuntimeError("Pour exporter en PDF, installe reportlab : pip install reportlab") from exc
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="Small", parent=styles["Normal"], fontSize=8, leading=10))
    doc = SimpleDocTemplate(str(path), pagesize=landscape(A4), rightMargin=15*mm, leftMargin=15*mm, topMargin=15*mm, bottomMargin=15*mm)
    story = [Paragraph("KIT IP PLANNER — RAPPORT D'INSTALLATION", styles["Title"]),
             Paragraph(f"Projet : {escape(str(project_name))} | Client : {escape(str(client or '—'))} | Site : {escape(str(site or '—'))}", styles["Normal"]), Spacer(1, 8)]
    story += [Paragraph("Résumé réseau", styles["Heading2"]), Paragraph(escape(plan.summary_text()).replace("\n", "<br/>"), styles["Normal"]), Spacer(1, 8)]
    data = [["Nom", "Type", "Adresse IP", "Masque", "Passerelle"]] + [[r.name, r.type_label, r.ip, r.netmask, r.gateway] for r in plan.rows]
    table = Table(data, repeatRows=1, colWidths=[35*mm, 55*mm, 35*mm, 35*mm, 35*mm])
    table.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), colors.HexColor("#0f4c81")), ("TEXTCOLOR", (0,0), (-1,0), colors.white), ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"), ("FONTSIZE", (0,0), (-1,-1), 8), ("GRID", (0,0), (-1,-1), .35, colors.grey), ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#eef5fb")]), ("VALIGN", (0,0), (-1,-1), "MIDDLE")]))
    story += [Paragraph("Plan d'adressage", styles["Heading2"]), table, Spacer(1, 10)]
    story += [Paragraph("Plan VLAN (à adapter à l'équipement)", styles["Heading2"])]
    validated_vlans = validate_vlans(vlans or DEFAULT_VLANS)
    vlan_data = [["ID", "Nom", "Sous-réseau", "Usage"]] + [[str(v.get("id", "")), v.get("name", ""), v.get("subnet", ""), v.get("purpose", "")] for v in validated_vlans]
    vt = Table(vlan_data, colWidths=[18*mm, 40*mm, 45*mm, 95*mm])
    vt.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), colors.HexColor("#166534")), ("TEXTCOLOR", (0,0), (-1,0), colors.white), ("GRID", (0,0), (-1,-1), .35, colors.grey), ("FONTSIZE", (0,0), (-1,-1), 8)]))
    story.append(vt)
    if vlan_assignments:
        story += [Spacer(1, 8), Paragraph("Adressage IP par VLAN", styles["Heading2"])]
        assignment_data = [["Équipement", "VLAN", "Sous-réseau", "IP", "Passerelle"]]
        assignment_data += [[a.device, f"{a.vlan_id} - {a.vlan_name}", a.subnet, a.ip, a.gateway] for a in vlan_assignments]
        at = Table(assignment_data, repeatRows=1, colWidths=[35*mm, 40*mm, 40*mm, 35*mm, 35*mm])
        at.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), colors.HexColor("#334155")), ("TEXTCOLOR", (0,0), (-1,0), colors.white), ("GRID", (0,0), (-1,-1), .35, colors.grey), ("FONTSIZE", (0,0), (-1,-1), 7), ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#eef5fb")])]))
        story.append(at)
    story += [Spacer(1, 8), Paragraph("Notes : estimations PoE et stockage à confirmer avec les fiches techniques. Prévoir une marge de capacité, vérifier les VLAN, les règles de pare-feu et la configuration réelle avant mise en service.", styles["Small"])]
    doc.build(story)
