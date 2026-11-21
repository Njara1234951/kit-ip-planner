"""Kit IP Planner : interface Windows (tkinter) de calcul automatique des adresses IP."""
import tkinter as tk
import json
import csv
from tkinter import filedialog, messagebox, ttk, simpledialog

import ipplan
import project_tools
import advanced
import inventory

DEFAULT_COUNTS = {"switch": 1, "nvr": 1, "ap": 0, "intercom": 0, "printer": 0, "other": 0, "camera": 4}


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Kit IP Planner 3.0 - planification réseau")
        self.geometry("1050x680")
        self.minsize(920, 580)
        self.plan = None
        self._job = None
        self.project_name = "Nouveau projet"
        self.client = ""
        self.site = ""
        self.vlans = [dict(v) for v in project_tools.DEFAULT_VLANS]
        self._build()
        self._recalc()

    # ------------------------------------------------------------------ UI
    def _build(self):
        left = ttk.LabelFrame(self, text="Paramètres", padding=10)
        left.pack(side="left", fill="y", padx=10, pady=10)
        right = ttk.Frame(self)
        right.pack(side="left", fill="both", expand=True, padx=(0, 10), pady=10)

        self.vars = {}

        def add_row(parent, label, key, default, row, width=12):
            ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=2)
            var = tk.StringVar(value=str(default))
            ttk.Entry(parent, textvariable=var, width=width).grid(row=row, column=1, sticky="e", pady=2)
            var.trace_add("write", lambda *_: self._schedule())
            self.vars[key] = var

        r = 0
        add_row(left, "Réseau (CIDR)", "network", "192.168.1.0/24", r, 16)
        r += 1
        self.gateway_last = tk.BooleanVar(value=False)
        ttk.Checkbutton(left, text="Passerelle en dernière adresse", variable=self.gateway_last,
                        command=self._schedule).grid(row=r, column=0, columnspan=2, sticky="w")
        r += 1
        ttk.Separator(left).grid(row=r, column=0, columnspan=2, sticky="ew", pady=8)
        r += 1
        for t in ipplan.DEVICE_TYPES:
            if t.key == "gateway":
                continue
            add_row(left, t.label, "count_" + t.key, DEFAULT_COUNTS.get(t.key, 0), r, 6)
            r += 1
        ttk.Separator(left).grid(row=r, column=0, columnspan=2, sticky="ew", pady=8)
        r += 1
        ttk.Label(left, text="Ports par switch").grid(row=r, column=0, sticky="w", pady=2)
        self.vars["ports"] = tk.StringVar(value="24")
        combo = ttk.Combobox(left, textvariable=self.vars["ports"], values=["5", "8", "16", "24", "48"],
                             width=5)
        combo.grid(row=r, column=1, sticky="e")
        self.vars["ports"].trace_add("write", lambda *_: self._schedule())
        r += 1
        add_row(left, "Débit par caméra (Mb/s)", "bitrate", "4", r, 6)
        r += 1
        add_row(left, "Rétention (jours)", "retention", "30", r, 6)
        r += 1
        add_row(left, "Budget PoE total (W, 0 = désactivé)", "poe", "0", r, 6)

        cols = ("name", "type", "ip", "mask", "gw")
        titles = ("Nom", "Type", "Adresse IP", "Masque", "Passerelle")
        widths = (90, 210, 120, 120, 120)
        self.tree = ttk.Treeview(right, columns=cols, show="headings", height=14)
        for c, t, w in zip(cols, titles, widths):
            self.tree.heading(c, text=t)
            self.tree.column(c, width=w, anchor="w")
        scroll = ttk.Scrollbar(right, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")

        self.summary = tk.Text(right, height=9, wrap="word", state="disabled", relief="flat",
                               background=self.cget("background"))
        self.summary.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 4))

        buttons = ttk.Frame(right)
        buttons.grid(row=2, column=0, columnspan=2, sticky="e")
        ttk.Button(buttons, text="Copier les IP", command=self._copy).pack(side="left", padx=3)
        ttk.Button(buttons, text="CSV IP", command=self._export).pack(side="left", padx=3)
        ttk.Button(buttons, text="Inventaire", command=self._export_inventory).pack(side="left", padx=3)
        ttk.Button(buttons, text="PDF rapport", command=self._export_pdf).pack(side="left", padx=3)
        ttk.Button(buttons, text="Schéma SVG", command=self._export_svg).pack(side="left", padx=3)
        project_buttons = ttk.Frame(right)
        project_buttons.grid(row=3, column=0, columnspan=2, sticky="e", pady=(6, 0))
        ttk.Button(project_buttons, text="Nouveau projet", command=self._new_project).pack(side="left", padx=3)
        ttk.Button(project_buttons, text="Ouvrir...", command=self._open_project).pack(side="left", padx=3)
        ttk.Button(project_buttons, text="Enregistrer...", command=self._save_project).pack(side="left", padx=3)
        ttk.Button(project_buttons, text="Modifier VLAN", command=self._edit_vlans).pack(side="left", padx=3)
        ttk.Button(project_buttons, text="Plan IP VLAN", command=self._show_vlan_ips).pack(side="left", padx=3)
        ttk.Button(project_buttons, text="Répartition switch", command=self._show_switch_distribution).pack(side="left", padx=3)

        right.rowconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)

    # ------------------------------------------------------------ calcul
    def _schedule(self):
        if self._job:
            self.after_cancel(self._job)
        self._job = self.after(200, self._recalc)

    def _read_int(self, key, label):
        text = self.vars[key].get().strip() or "0"
        try:
            return int(text)
        except ValueError:
            raise ValueError(f"« {label} » doit être un nombre entier.")

    def _read_float(self, key, label):
        text = self.vars[key].get().strip().replace(",", ".") or "0"
        try:
            return float(text)
        except ValueError:
            raise ValueError(f"« {label} » doit être un nombre.")

    def _recalc(self):
        self._job = None
        try:
            counts = {}
            for t in ipplan.DEVICE_TYPES:
                if t.key != "gateway":
                    counts[t.key] = self._read_int("count_" + t.key, t.label)
            plan = ipplan.build_plan(
                self.vars["network"].get(),
                counts,
                gateway_last=self.gateway_last.get(),
                ports_per_switch=self._read_int("ports", "Ports par switch"),
                bitrate_mbps=self._read_float("bitrate", "Débit par caméra"),
                retention_days=self._read_int("retention", "Rétention"),
                poe_budget_w=self._read_float("poe", "Budget PoE"),
            )
        except ValueError as exc:
            self.plan = None
            self.tree.delete(*self.tree.get_children())
            self._set_summary(f"⚠ {exc}")
            return
        self.plan = plan
        self.tree.delete(*self.tree.get_children())
        for row in plan.rows:
            self.tree.insert("", "end", values=(row.name, row.type_label, row.ip, row.netmask, row.gateway))
        self._set_summary(plan.summary_text())

    def _set_summary(self, text):
        self.summary.configure(state="normal")
        self.summary.delete("1.0", "end")
        self.summary.insert("1.0", text)
        self.summary.configure(state="disabled")

    # ----------------------------------------------------------- actions
    def _copy(self):
        if not self.plan:
            return
        text = "\n".join(f"{r.name}\t{r.ip}" for r in self.plan.rows)
        self.clipboard_clear()
        self.clipboard_append(text)
        messagebox.showinfo("Copié", "Les noms et adresses IP sont dans le presse-papiers.")

    def _export(self):
        if not self.plan:
            messagebox.showwarning("Export impossible", "Corrige d'abord les paramètres.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv", initialfile="plan_adressage.csv",
            filetypes=[("CSV (Excel)", "*.csv")],
        )
        if path:
            try:
                ipplan.export_csv(self.plan, path)
            except OSError as exc:
                messagebox.showerror("Erreur d'export", f"Impossible d'enregistrer le fichier :\n{exc}")
                return
            messagebox.showinfo("Exporté", f"Fichier enregistré :\n{path}")


    def _export_inventory(self):
        if not self.plan:
            messagebox.showwarning("Inventaire", "Corrige d'abord les paramètres réseau.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv", initialfile="inventaire_installation.csv", filetypes=[("CSV Excel", "*.csv")])
        if not path: return
        try:
            inventory.export_inventory(self.plan, path)
            messagebox.showinfo("Inventaire", f"Modèle d'inventaire exporté :\n{path}\n\nComplète les champs MAC, fabricant, modèle, numéro de série et emplacement dans Excel.")
        except OSError as exc:
            messagebox.showerror("Inventaire", f"Impossible d'enregistrer :\n{exc}")

    def _project_data(self):
        return {"format": "kit-ip-planner-project", "version": 3,
                "project": {"name": self.project_name, "client": self.client, "site": self.site},
                "settings": {k: v.get() for k, v in self.vars.items()},
                "gateway_last": self.gateway_last.get(), "vlans": self.vlans}

    def _save_project(self):
        name = simpledialog.askstring("Projet", "Nom du projet :", initialvalue=self.project_name, parent=self)
        if name is None: return
        self.project_name = name.strip() or "Projet réseau"
        client = simpledialog.askstring("Projet", "Client (facultatif) :", initialvalue=self.client, parent=self)
        if client is not None: self.client = client.strip()
        site = simpledialog.askstring("Projet", "Site / adresse (facultatif) :", initialvalue=self.site, parent=self)
        if site is not None: self.site = site.strip()
        path = filedialog.asksaveasfilename(defaultextension=".json", initialfile="projet_kit_ip.json", filetypes=[("Projet Kit IP Planner", "*.json")])
        if not path: return
        try:
            project_tools.save_project(path, self._project_data())
            self.title(f"Kit IP Planner 3.0 — {self.project_name}")
            messagebox.showinfo("Projet enregistré", f"Projet sauvegardé :\n{path}")
        except OSError as exc:
            messagebox.showerror("Erreur", f"Enregistrement impossible :\n{exc}")

    def _open_project(self):
        path = filedialog.askopenfilename(filetypes=[("Projet Kit IP Planner", "*.json")])
        if not path: return
        try:
            data = project_tools.load_project(path)
            settings = data.get("settings", {})
            for key, value in settings.items():
                if key in self.vars: self.vars[key].set(str(value))
            self.gateway_last.set(bool(data.get("gateway_last", False)))
            meta = data.get("project", {})
            self.project_name = meta.get("name", "Projet réseau")
            self.client = meta.get("client", "")
            self.site = meta.get("site", "")
            self.vlans = data.get("vlans", [dict(v) for v in project_tools.DEFAULT_VLANS])
            self.title(f"Kit IP Planner 3.0 — {self.project_name}")
            self._recalc()
            messagebox.showinfo("Projet ouvert", f"Projet chargé : {self.project_name}")
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            messagebox.showerror("Ouverture impossible", str(exc))

    def _new_project(self):
        if not messagebox.askyesno("Nouveau projet", "Réinitialiser les paramètres pour un nouveau projet ?"):
            return
        defaults = {"network": "192.168.1.0/24", "ports": "24", "bitrate": "4", "retention": "30", "poe": "0"}
        defaults.update({"count_" + k: str(v) for k, v in DEFAULT_COUNTS.items()})
        for key, value in defaults.items():
            if key in self.vars: self.vars[key].set(value)
        self.gateway_last.set(False)
        self.project_name, self.client, self.site = "Nouveau projet", "", ""
        self.vlans = [dict(v) for v in project_tools.DEFAULT_VLANS]
        self.title("Kit IP Planner 3.0 — Nouveau projet")
        self._recalc()

    def _edit_vlans(self):
        lines = ["ID;Nom;Sous-réseau;Usage"] + [f'{v.get("id", "")};{v.get("name", "")};{v.get("subnet", "")};{v.get("purpose", "")}' for v in self.vlans]
        text = simpledialog.askstring("VLAN", "Une ligne par VLAN, format ID;Nom;Sous-réseau;Usage", initialvalue="\n".join(lines), parent=self)
        if text is None: return
        try:
            parsed = []
            for line in text.splitlines()[1:]:
                if not line.strip(): continue
                parts = line.split(";", 3)
                if len(parts) != 4: raise ValueError("Chaque ligne doit avoir 4 champs séparés par des ;")
                vid = int(parts[0])
                if not 1 <= vid <= 4094: raise ValueError("L'ID VLAN doit être entre 1 et 4094.")
                parsed.append({"id": vid, "name": parts[1].strip(), "subnet": parts[2].strip(), "purpose": parts[3].strip()})
            parsed = advanced.validate_vlans(parsed)
            self.vlans = parsed
            messagebox.showinfo("VLAN", f"{len(parsed)} VLAN enregistrés dans le projet.")
        except ValueError as exc:
            messagebox.showerror("VLAN invalide", str(exc))

    def _show_vlan_ips(self):
        if not self.plan:
            messagebox.showwarning("Plan VLAN", "Corrige d'abord les paramètres réseau.")
            return
        counts = {k: int(self.vars["count_" + k].get() or 0) for k in DEFAULT_COUNTS}
        mapping = {}
        for vlan in self.vlans:
            name = vlan["name"].casefold()
            purpose = vlan.get("purpose", "").casefold()
            if "cctv" in name or "camera" in name or "vidéo" in purpose or "camera" in purpose:
                mapping["camera"] = vlan["id"]
            elif "wi-fi" in name or "wifi" in name or "wireless" in purpose:
                mapping["ap"] = vlan["id"]
            elif "accès" in name or "access" in name or "interphone" in purpose:
                mapping["intercom"] = vlan["id"]
            elif "admin" in name or "network" in purpose or "réseau" in purpose:
                for key in ("switch", "nvr", "printer", "other"):
                    mapping[key] = vlan["id"]
        fallback = self.vlans[0]["id"] if self.vlans else 1
        for key in DEFAULT_COUNTS:
            mapping.setdefault(key, fallback)
        try:
            allocations = advanced.assign_vlan_ips(self.vlans, counts, mapping)
        except ValueError as exc:
            messagebox.showerror("Plan VLAN", str(exc))
            return
        win = tk.Toplevel(self)
        win.title("Plan d'adressage par VLAN")
        win.geometry("760x460")
        columns = ("name", "vlan", "subnet", "ip", "gateway")
        tree = ttk.Treeview(win, columns=columns, show="headings")
        labels = ("Équipement", "VLAN", "Sous-réseau", "Adresse IP", "Passerelle")
        for col, label in zip(columns, labels):
            tree.heading(col, text=label)
            tree.column(col, width=140, anchor="w")
        scroll = ttk.Scrollbar(win, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        for a in allocations:
            tree.insert("", "end", values=(a.device, f"{a.vlan_id} — {a.vlan_name}", a.subnet, a.ip, a.gateway))
        if not allocations:
            tree.insert("", "end", values=("Aucun appareil à attribuer", "", "", "", ""))
        ttk.Label(win, text="Attribution automatique selon le nom des VLAN; vérifie les affectations avant déploiement.").pack(side="bottom", fill="x", padx=8, pady=6)
        def export_vlan_csv():
            path = filedialog.asksaveasfilename(parent=win, defaultextension=".csv", initialfile="plan_ip_vlan.csv", filetypes=[("CSV", "*.csv")])
            if not path: return
            try:
                with open(path, "w", newline="", encoding="utf-8-sig") as f:
                    writer = csv.writer(f, delimiter=";")
                    writer.writerow(["Équipement", "VLAN ID", "VLAN", "Sous-réseau", "Adresse IP", "Passerelle"])
                    for a in allocations:
                        writer.writerow([a.device, a.vlan_id, a.vlan_name, a.subnet, a.ip, a.gateway])
                messagebox.showinfo("Export VLAN", f"Fichier créé :\n{path}", parent=win)
            except OSError as exc:
                messagebox.showerror("Export VLAN", str(exc), parent=win)
        ttk.Button(win, text="Exporter CSV", command=export_vlan_csv).pack(side="bottom", pady=6)

    def _show_switch_distribution(self):
        if not self.plan:
            messagebox.showwarning("Répartition switch", "Corrige d'abord les paramètres réseau.")
            return
        counts = {k: int(self.vars["count_" + k].get() or 0) for k in DEFAULT_COUNTS}
        devices = []
        power = {"camera": 8.0, "ap": 15.0, "intercom": 8.0, "switch": 0.0,
                "nvr": 0.0, "printer": 0.0, "other": 0.0}
        for key, count in counts.items():
            if key == "switch":
                continue  # ports uplink/inter-switch sont réservés séparément
            for i in range(count):
                devices.append((f"{key.upper()}-{i+1:02d}", power.get(key, 0.0)))
        switch_count = max(counts.get("switch", 0), self.plan.stats.get("switches_recommended", 0), 1)
        ports = self._read_int("ports", "Ports par switch")
        total_budget = self._read_float("poe", "Budget PoE")
        budget_each = total_budget / switch_count if total_budget > 0 else None
        try:
            loads = advanced.distribute_devices(devices, switch_count, ports,
                budget_each, uplink_ports=(1 if switch_count == 1 else 2))
        except ValueError as exc:
            messagebox.showerror("Répartition switch", str(exc))
            return
        lines = [f"Répartition estimée sur {switch_count} switch(s) de {ports} ports :", ""]
        for load in loads:
            lines.append(f"Switch {load.switch_number} : {load.ports_used} ports occupés, {load.ports_available} libres, {load.poe_used_w:.1f} W PoE")
            if load.poe_budget_w is not None:
                lines.append(f"  Budget estimé : {load.poe_budget_w:.1f} W")
            if load.warnings:
                lines.extend("  ⚠ " + w for w in load.warnings)
            if load.devices:
                lines.append("  Équipements : " + ", ".join(load.devices))
        messagebox.showinfo("Répartition switch", "\n".join(lines))

    def _export_pdf(self):
        if not self.plan:
            messagebox.showwarning("Export impossible", "Corrige d'abord les paramètres."); return
        path = filedialog.asksaveasfilename(defaultextension=".pdf", initialfile="rapport_installation.pdf", filetypes=[("PDF", "*.pdf")])
        if not path: return
        try:
            counts = {k: int(self.vars["count_" + k].get() or 0) for k in DEFAULT_COUNTS}
            mapping = {}
            for vlan in self.vlans:
                name = vlan["name"].casefold(); purpose = vlan.get("purpose", "").casefold()
                if "cctv" in name or "camera" in name or "vidéo" in purpose or "camera" in purpose: mapping["camera"] = vlan["id"]
                elif "wi-fi" in name or "wifi" in name or "wireless" in purpose: mapping["ap"] = vlan["id"]
                elif "accès" in name or "access" in name or "interphone" in purpose: mapping["intercom"] = vlan["id"]
                elif "admin" in name or "network" in purpose or "réseau" in purpose:
                    for key in ("switch", "nvr", "printer", "other"): mapping[key] = vlan["id"]
            fallback = self.vlans[0]["id"] if self.vlans else 1
            for key in counts: mapping.setdefault(key, fallback)
            vlan_ips = advanced.assign_vlan_ips(self.vlans, counts, mapping)
            project_tools.export_pdf(self.plan, path, self.project_name, self.client, self.site, self.vlans, vlan_ips)
            messagebox.showinfo("PDF créé", f"Rapport enregistré :\n{path}")
        except (OSError, RuntimeError, ValueError) as exc:
            messagebox.showerror("Export PDF", str(exc))

    def _export_svg(self):
        if not self.plan:
            messagebox.showwarning("Export impossible", "Corrige d'abord les paramètres."); return
        path = filedialog.asksaveasfilename(defaultextension=".svg", initialfile="schema_reseau.svg", filetypes=[("Schéma SVG", "*.svg")])
        if not path: return
        try:
            with open(path, "w", encoding="utf-8") as f: f.write(project_tools.generate_svg(self.plan, self.project_name))
            messagebox.showinfo("Schéma créé", f"Schéma enregistré :\n{path}")
        except OSError as exc:
            messagebox.showerror("Export SVG", str(exc))


if __name__ == "__main__":
    App().mainloop()
