#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
reverificar.py — reescaneia contas que JÁ estão cadastradas no dashboard,
pra ver se o status de topo mudou desde a última checagem (não precisa de
roster novo nenhum, só reconsulta o Ankama).

Uso:
    python3 reverificar.py                  # reescaneia TODAS as contas cadastradas
    python3 reverificar.py "XEQUE-MATE"      # reescaneia só as contas dessa guilda

O que "topo" significa não mudou: a conta tem um personagem numa das 43
guildas da MAV E um personagem numa guilda rival, no servidor Talok, ao
mesmo tempo.

O que ele faz, pra cada conta reescaneada:
  - Já era topo e continua ligada a uma guilda rival em Talok -> continua topo.
  - Já era topo mas não tem mais vínculo nenhum -> deixa de ser topo.
  - Era limpa e agora tem vínculo novo -> vira topo (marcado com o selo NOVO).
  - Era limpa e continua limpa -> nada muda.
  - Saiu da MAV inteiramente (não tem mais personagem em nenhuma das 43
    guildas) -> sai do dashboard e vai pro histórico de saídas
    (saidas_mav_historico.json), contando como -1 topo se ela era topo.

Contas já vetadas (em eliminados_historico.json) NUNCA são reescaneadas —
ficam de fora pra sempre, como já era antes.

Como isso reescaneia conta por conta no Ankama, é mais lento que o
atualizar.py — reescanear tudo (milhares de contas) pode levar bastante
tempo. Pode deixar rodando em segundo plano.
"""

import sys
import os
import json
import time
import datetime
import importlib.util

ROOT = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(ROOT, "guilds_db.json")
EXC_PATH = os.path.join(ROOT, "exceptions.json")
ELIM_PATH = os.path.join(ROOT, "eliminados_historico.json")
SAIDAS_PATH = os.path.join(ROOT, "saidas_mav_historico.json")

spec = importlib.util.spec_from_file_location("radar_de_topos", os.path.join(ROOT, "radar_de_topos.py"))
radar = importlib.util.module_from_spec(spec)
spec.loader.exec_module(radar)


def load_json(path, default):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return default


def main():
    filtro_guilda = sys.argv[1] if len(sys.argv) > 1 else None

    db = load_json(DB_PATH, {})
    exceptions = load_json(EXC_PATH, {"global_clean_apelidos": [], "guild_specific_clean": {}})
    global_clean = set(exceptions.get("global_clean_apelidos", []))
    guild_specific = exceptions.get("guild_specific_clean", {})
    eliminados = load_json(ELIM_PATH, {})
    saidas_mav = load_json(SAIDAS_PATH, {})
    hoje = datetime.date.today().isoformat()

    if filtro_guilda and filtro_guilda not in db:
        print(f"ERRO: guilda '{filtro_guilda}' não está no guilds_db.json. Confira o nome exato (igual aparece no dashboard).")
        sys.exit(1)

    guildas_alvo = [filtro_guilda] if filtro_guilda else list(db.keys())

    # 1. monta a lista de apelidos unicos a reescanear (uma conta pode estar
    #    em mais de uma guilda MAV — so escaneia ela uma vez)
    todos_apelidos = set()
    for guild_name in guildas_alvo:
        entry = db[guild_name]
        for c in entry.get("checked", []):
            todos_apelidos.add(c.get("apelido"))

    apelidos_pulados = [a for a in todos_apelidos if a in eliminados]
    apelidos_a_escanear = sorted(todos_apelidos - eliminados.keys())

    print(f"{len(apelidos_a_escanear)} conta(s) única(s) pra reescanear "
          f"({len(apelidos_pulados)} já vetada(s), pulando essas).")
    print()

    # 2. reescaneia cada conta unica uma vez so — checa tanto o lado rival
    #    quanto se ela ainda tem personagem numa das 43 guildas da MAV
    resultado_por_apelido = {}
    for i, apelido in enumerate(apelidos_a_escanear, start=1):
        print(f"[{i}/{len(apelidos_a_escanear)}] {apelido} ...", end=" ", flush=True)
        try:
            personagens = radar.verificar_conta(apelido)
        except Exception as e:
            print(f"ERRO ({e}) — mantendo status anterior dessa conta.")
            resultado_por_apelido[apelido] = None  # sinaliza erro, nao mexe
            time.sleep(radar.PAUSA_ENTRE_CONTAS)
            continue

        vinculos_rivais = []
        ainda_na_mav = False
        for p in personagens:
            guilda = p["guilda"]
            servidor = p["servidor"]
            if not guilda or servidor != radar.SERVIDOR_VALIDO:
                continue
            if guilda in radar.RIVAL_LOOKUP:
                vinculos_rivais.append({
                    "rivalChar": p["nome"],
                    "rivalGuild": guilda,
                    "rivalAlliance": radar.RIVAL_LOOKUP[guilda],
                })
            if radar.normalize_guild_name(guilda) in radar.MAV_GUILDS_NORM:
                ainda_na_mav = True

        resultado_por_apelido[apelido] = {"rivais": vinculos_rivais, "na_mav": ainda_na_mav}

        if not ainda_na_mav:
            status = "SAIU DA MAV"
        elif vinculos_rivais:
            status = f"{len(vinculos_rivais)} vínculo(s) rival(is)"
        else:
            status = "limpo"
        print(status)
        time.sleep(radar.PAUSA_ENTRE_CONTAS)

    # 3. aplica os resultados em cada guilda
    print()
    print("Atualizando o banco de dados...")
    resumo = []
    saidas_mav_novas = {}

    for guild_name in guildas_alvo:
        entry = db[guild_name]
        specific_clean = set(guild_specific.get(guild_name, []))

        novos_topos_flag = 0
        deixaram_de_ser_topo = 0
        continuam_topo = 0
        saiu_da_mav = 0
        saiu_da_mav_era_topo = 0

        novo_checked = []
        novo_flagged = []
        for c in entry.get("checked", []):
            apelido = c.get("apelido")
            resultado = resultado_por_apelido.get(apelido)

            if apelido in eliminados:
                c["flagged"] = False
                c["isNovo"] = False
                novo_checked.append(c)
                continue

            if resultado is None:
                # erro no reescaneio dessa conta — mantem o status anterior
                # e preserva os vinculos que ja estavam salvos pra essa conta
                novo_checked.append(c)
                if c.get("flagged"):
                    for f in entry.get("flagged", []):
                        if f.get("apelido") == apelido:
                            novo_flagged.append(f)
                continue

            if not resultado["na_mav"]:
                # saiu da MAV inteiramente — sai do dashboard, vai pro
                # histórico de saídas (permanente)
                era_flagged = bool(c.get("flagged"))
                saiu_da_mav += 1
                registro = dict(c)
                registro.pop("isNovo", None)
                registro["eraTopo"] = era_flagged
                registro["dataSaida"] = hoje
                if era_flagged:
                    saiu_da_mav_era_topo += 1
                    vinculos_antigos = [f for f in entry.get("flagged", []) if f.get("apelido") == apelido]
                    if vinculos_antigos:
                        registro["vinculosNaSaida"] = vinculos_antigos
                saidas_mav_novas[apelido] = registro
                continue  # nao entra em novo_checked nem novo_flagged

            vinculos = resultado["rivais"]
            era_flagged = bool(c.get("flagged"))
            flagged_agora = len(vinculos) > 0
            if apelido in global_clean or apelido in specific_clean:
                flagged_agora = False

            c["flagged"] = flagged_agora
            c["isNovo"] = flagged_agora and not era_flagged
            novo_checked.append(c)

            if flagged_agora and not era_flagged:
                novos_topos_flag += 1
            elif era_flagged and not flagged_agora:
                deixaram_de_ser_topo += 1
            elif era_flagged and flagged_agora:
                continuam_topo += 1

            if flagged_agora:
                for v in vinculos:
                    novo_flagged.append({
                        "apelido": apelido,
                        "mavChar": c.get("mavChar"),
                        "mavGuild": c.get("mavGuild"),
                        "rivalChar": v["rivalChar"],
                        "rivalGuild": v["rivalGuild"],
                        "rivalAlliance": v["rivalAlliance"],
                        "isNovo": not era_flagged,
                    })

        entry["checked"] = novo_checked
        entry["flagged"] = novo_flagged
        resumo.append((guild_name, novos_topos_flag, deixaram_de_ser_topo, continuam_topo, saiu_da_mav, saiu_da_mav_era_topo))

    if saidas_mav_novas:
        saidas_mav.update(saidas_mav_novas)
        with open(SAIDAS_PATH, "w", encoding="utf-8") as f:
            json.dump(saidas_mav, f, ensure_ascii=False, indent=2)

    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)

    print()
    print("Resumo por guilda (topo novo / deixou de ser topo / continua topo / saiu da MAV):")
    for guild_name, novos, saiu_topo, continua, saiu_mav, saiu_mav_topo in resumo:
        if novos or saiu_topo or continua or saiu_mav:
            extra = f", {saiu_mav} saiu(íram) da MAV ({saiu_mav_topo} era(m) topo)" if saiu_mav else ""
            print(f"  {guild_name}: +{novos} novo(s), -{saiu_topo} não é mais topo, {continua} continua(m){extra}")

    if saidas_mav_novas:
        print()
        print(f"{len(saidas_mav_novas)} conta(s) saíram da MAV nessa reconferência — arquivadas em saidas_mav_historico.json.")

    print()
    print("Atualizando o dashboard...")
    merge_spec = importlib.util.spec_from_file_location("merge", os.path.join(ROOT, "merge.py"))
    merge_mod = importlib.util.module_from_spec(merge_spec)
    merge_spec.loader.exec_module(merge_mod)
    merge_mod.main()


if __name__ == "__main__":
    main()
