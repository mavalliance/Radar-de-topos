#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
merge.py — junta os resultados no dashboard "Radar de Topos", sem precisar
de internet nem de IA. Entende dois formatos de arquivo em resultados/:

  - resultado_topos_*.json  -> varredura completa de uma guilda (substitui
    tudo que já existia dela no banco). Gerado rodando o radar_de_topos.py
    manualmente numa guilda.
  - novo_topos_*.json       -> só contas NOVAS de uma guilda (soma no que já
    existia, sem apagar nada). Gerado automaticamente pelo atualizar.py.

Como usar:
  1. Rode o radar_de_topos.py (varredura completa) ou o atualizar.py
     (só contas novas, 1 comando) — ver README.md.
  2. Se usou o radar_de_topos.py na mão, copie o resultado_topos_*.json
     gerado pra dentro da pasta "resultados/" (o atualizar.py já faz isso
     sozinho pros novo_topos_*.json).
  3. Rode:  python3 merge.py   (o atualizar.py e o eliminar.py já chamam
     isso sozinhos no final, não precisa rodar de novo depois deles).
  4. Ele gera (ou atualiza) o arquivo index.html nessa mesma pasta.
  5. Publique com o GitHub Desktop (commit + push) — ver README.md.

O que ele faz:
  - Lê o "banco" local (guilds_db.json), que guarda todas as guildas já
    processadas até hoje.
  - Para cada arquivo novo em resultados/, monta (ou soma) a entrada da
    guilda no formato certo e atualiza o banco.
  - Contas marcadas como vetadas em eliminados_historico.json (via
    eliminar.py) nunca aparecem como topo aqui, mesmo que ainda estejam
    nos arquivos processados antes.
  - Marca com isNovo=true as contas que vieram do arquivo mais recente
    processado nessa guilda (pro dashboard mostrar o selo "NOVO"), e tira
    esse selo de quem já estava lá antes.
  - Gera o index.html final juntando o banco com o template.html.
  - Move os JSONs já processados pra resultados/processados/, pra não
    processar duas vezes sem querer.

Nada aqui inventa dado: nome exibido e ícone vêm sempre de name_map.json e
icons.json; se uma guilda nova aparecer sem estar nesses arquivos, o script
avisa e pede pra você completar antes de publicar.
"""

import json
import os
import re
import glob
import shutil
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(ROOT, "guilds_db.json")
NAME_MAP_PATH = os.path.join(ROOT, "name_map.json")
ICONS_PATH = os.path.join(ROOT, "icons.json")
EXC_PATH = os.path.join(ROOT, "exceptions.json")
ELIM_PATH = os.path.join(ROOT, "eliminados_historico.json")
TEMPLATE_PATH = os.path.join(ROOT, "template.html")
OUTPUT_PATH = os.path.join(ROOT, "index.html")
RESULTADOS_DIR = os.path.join(ROOT, "resultados")
PROCESSADOS_DIR = os.path.join(RESULTADOS_DIR, "processados")


def slugify(name):
    s = name.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def load_json(path, default):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return default


def conta_personagens(checked):
    """soma quantos personagens (mavChar) as contas verificadas cobrem"""
    return sum(len(str(c.get("mavChar", "")).split(" / ")) for c in checked)


def main():
    db = load_json(DB_PATH, {})
    name_map = load_json(NAME_MAP_PATH, {})
    icons = load_json(ICONS_PATH, {})
    exceptions = load_json(EXC_PATH, {"global_clean_apelidos": [], "guild_specific_clean": {}})
    eliminados = load_json(ELIM_PATH, {})
    global_clean = set(exceptions.get("global_clean_apelidos", []))
    guild_specific = exceptions.get("guild_specific_clean", {})

    os.makedirs(RESULTADOS_DIR, exist_ok=True)
    os.makedirs(PROCESSADOS_DIR, exist_ok=True)

    full_files = sorted(glob.glob(os.path.join(RESULTADOS_DIR, "resultado_topos_*.json")))
    incr_files = sorted(glob.glob(os.path.join(RESULTADOS_DIR, "novo_topos_*.json")))
    files = [(p, "full") for p in full_files] + [(p, "incr") for p in incr_files]

    if not files:
        print("Nenhum arquivo novo em resultados/ — só vou regerar o index.html com o banco atual.")
    else:
        print(f"Encontrei {len(files)} arquivo(s) novo(s) em resultados/. Processando...")
        print()

    errors = []

    for path, kind in files:
        fname = os.path.basename(path)
        try:
            data = load_json(path, None)
            if data is None:
                errors.append(f"{fname}: arquivo vazio ou inválido")
                continue

            source_name = data.get("guilda")
            if not source_name:
                errors.append(f"{fname}: campo 'guilda' ausente no JSON")
                continue

            # resultado_topos_*.json (radar_de_topos.py) usa nomes que às vezes
            # precisam de name_map.json; novo_topos_*.json (atualizar.py) já vem
            # com o nome certo do guild_id_map.json, então costuma bater direto.
            display_name = name_map.get(source_name, source_name if kind == "incr" else None)
            if not display_name:
                print(f"AVISO: guilda '{source_name}' não está no name_map.json — usando o nome tal como veio.")
                print(f"       Se o nome exibido deveria ser outro, adicione \"{source_name}\": \"Nome Certo\" em name_map.json e rode de novo.")
                display_name = source_name

            icon = icons.get(display_name)
            if not icon:
                errors.append(
                    f"{fname}: sem ícone em icons.json pra '{display_name}' — adicione o brasão base64 antes "
                    f"de continuar. Essa guilda NÃO foi incluída dessa vez."
                )
                continue

            specific_clean = set(guild_specific.get(display_name, []))

            if kind == "full":
                checados = data.get("checados", [])
                topos = data.get("topos", [])
                total_roster = data.get("totalPersonagensRoster")
                total_contas = data.get("totalContas")
                total_topos = data.get("totalTopos")

                # checagem de fechamento — igual à que sempre foi feita manualmente
                problems = []
                if total_contas is not None and len(checados) != total_contas:
                    problems.append(f"checados ({len(checados)}) != totalContas ({total_contas})")
                if total_topos is not None and len(topos) != total_topos:
                    problems.append(f"topos ({len(topos)}) != totalTopos ({total_topos})")
                if total_roster is not None:
                    soma = conta_personagens(checados)
                    if soma != total_roster:
                        problems.append(f"soma de personagens ({soma}) != totalPersonagensRoster ({total_roster})")

                if problems:
                    errors.append(
                        f"{fname} ('{display_name}'): checagem de fechamento falhou -> " + "; ".join(problems) +
                        " -- guilda NÃO foi incluída, confira o JSON de origem."
                    )
                    continue

                checked = []
                for c in checados:
                    apelido = c.get("apelido")
                    flagged = bool(c.get("flagged", False))
                    if apelido in global_clean or apelido in specific_clean or apelido in eliminados:
                        flagged = False
                    checked.append({
                        "apelido": apelido,
                        "mavChar": c.get("mavChar"),
                        "mavGuild": c.get("mavGuild"),
                        "flagged": flagged,
                        "isNovo": False,
                    })

                flagged_cards = []
                for t in topos:
                    apelido = t.get("apelido")
                    if apelido in global_clean or apelido in specific_clean or apelido in eliminados:
                        continue
                    for v in t.get("vinculos", []):
                        flagged_cards.append({
                            "apelido": apelido,
                            "mavChar": t.get("mavChar"),
                            "mavGuild": t.get("mavGuild"),
                            "rivalChar": v.get("rivalChar"),
                            "rivalGuild": v.get("rivalGuild"),
                            "rivalAlliance": v.get("rivalAlliance"),
                            "isNovo": False,
                        })

                entry = {
                    "id": slugify(display_name) + "-talok",
                    "icon": icon,
                    "name": display_name,
                    "server": "Talok",
                    "alliance": "Manus Vindictae",
                    "totalMembers": total_roster,
                    "status": "done",
                    "checked": checked,
                    "flagged": flagged_cards,
                }

                db[display_name] = entry
                print(f"OK: {display_name} -> {len(checked)} contas, {len(topos)} topos ({fname})")

            else:  # incr — novo_topos_*.json, soma contas novas na guilda existente
                checados_novos = data.get("checados", [])
                topos_novos = data.get("topos", [])

                existing = db.get(display_name)
                if existing is None:
                    existing = {
                        "id": slugify(display_name) + "-talok",
                        "icon": icon,
                        "name": display_name,
                        "server": "Talok",
                        "alliance": "Manus Vindictae",
                        "totalMembers": 0,
                        "status": "done",
                        "checked": [],
                        "flagged": [],
                    }

                # tira o selo "NOVO" de quem já estava no banco antes dessa rodada
                for c in existing["checked"]:
                    c["isNovo"] = False
                for f in existing["flagged"]:
                    f["isNovo"] = False

                ja_conhecidos = set(c.get("apelido") for c in existing["checked"])
                puladas_por_ja_vetadas = []

                for c in checados_novos:
                    apelido = c.get("apelido")
                    if apelido in ja_conhecidos:
                        continue  # já processada antes, não duplica
                    if apelido in eliminados:
                        puladas_por_ja_vetadas.append(apelido)
                        continue  # já foi vetada antes — não volta a aparecer sozinha
                    flagged = bool(c.get("flagged", False))
                    if apelido in global_clean or apelido in specific_clean:
                        flagged = False
                    existing["checked"].append({
                        "apelido": apelido,
                        "mavChar": c.get("mavChar"),
                        "mavGuild": c.get("mavGuild"),
                        "flagged": flagged,
                        "isNovo": True,
                    })
                    ja_conhecidos.add(apelido)

                for t in topos_novos:
                    apelido = t.get("apelido")
                    if apelido in eliminados or apelido in global_clean or apelido in specific_clean:
                        continue
                    for v in t.get("vinculos", []):
                        existing["flagged"].append({
                            "apelido": apelido,
                            "mavChar": t.get("mavChar"),
                            "mavGuild": t.get("mavGuild"),
                            "rivalChar": v.get("rivalChar"),
                            "rivalGuild": v.get("rivalGuild"),
                            "rivalAlliance": v.get("rivalAlliance"),
                            "isNovo": True,
                        })

                existing["totalMembers"] = conta_personagens(existing["checked"])
                db[display_name] = existing

                if puladas_por_ja_vetadas:
                    print(f"AVISO: {fname} — {len(puladas_por_ja_vetadas)} conta(s) já tinha(m) sido vetada(s) antes, não voltei a marcar: {', '.join(puladas_por_ja_vetadas)}")

                print(f"OK: {display_name} -> +{len(checados_novos)} conta(s) nova(s), +{len(topos_novos)} topo(s) novo(s) ({fname})")

            shutil.move(path, os.path.join(PROCESSADOS_DIR, fname))

        except Exception as e:
            errors.append(f"{fname}: erro inesperado -> {e}")

    # rede de segurança: garante que nenhuma conta vetada fique ativa no banco,
    # mesmo que tenha sido eliminada depois de já estar salva
    for display_name, entry in db.items():
        antes = len(entry.get("flagged", []))
        entry["flagged"] = [f for f in entry.get("flagged", []) if f.get("apelido") not in eliminados]
        if len(entry["flagged"]) != antes:
            print(f"AVISO: limpei {antes - len(entry['flagged'])} card(s) de topo já vetado(s) que ainda estavam em '{display_name}'.")
        for c in entry.get("checked", []):
            if c.get("apelido") in eliminados:
                c["flagged"] = False

    # salva o banco atualizado
    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)

    # monta o index.html final
    guilds_list = list(db.values())
    guilds_json = json.dumps(guilds_list, ensure_ascii=False)

    if not os.path.exists(TEMPLATE_PATH):
        print(f"ERRO: não encontrei {TEMPLATE_PATH} — o template.html precisa estar na mesma pasta.")
        sys.exit(1)

    with open(TEMPLATE_PATH, encoding="utf-8") as f:
        template = f.read()

    if "__GUILDS_ARRAY_JSON__" not in template:
        print("ERRO: template.html não tem o marcador __GUILDS_ARRAY_JSON__ — não dá pra gerar o index.html.")
        sys.exit(1)

    output = template.replace("__GUILDS_ARRAY_JSON__", guilds_json)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(output)

    total_guilds = len(guilds_list)
    total_contas = sum(len(g["checked"]) for g in guilds_list)
    total_topos_vinc = sum(len(g["flagged"]) for g in guilds_list)

    print()
    print(f"index.html gerado: {total_guilds} guildas, {total_contas} contas verificadas, {total_topos_vinc} vínculos de topo.")

    if errors:
        print()
        print("ATENÇÃO — os itens abaixo NÃO foram incluídos, corrija e rode de novo:")
        for e in errors:
            print(" - " + e)
        print()


if __name__ == "__main__":
    main()
