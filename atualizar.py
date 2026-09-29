#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
atualizar.py — comando único: pega um roster com jogadores NOVOS de
QUALQUER guilda da aliança misturados (não precisa separar por guilda nem
digitar nome nenhum), cruza cada conta contra as guildas rivais e já
atualiza o dashboard (index.html) sozinho.

Uso:
    python3 atualizar.py novos_jogadores.txt

O arquivo pode ter linhas soltas de cabeçalho/resumo no início e no fim
(o script ignora qualquer linha que não comece com "NOVO_MEMBRO"), e uma
linha por personagem novo, assim:
    NOVO_MEMBRO|nome|guildId|nome da guilda (texto, pode vir bagunçado)|apelido|accountId|nível-ou-"-"

O script só processa linhas que comecem com "NOVO_MEMBRO" e tenham
exatamente 7 campos; qualquer outra linha (cabeçalho, resumo, linha em
branco) é ignorada silenciosamente.

A guilda de cada linha é resolvida SEMPRE pelo guildId (campo numérico),
usando o guild_id_map.json (guildId -> nome da guilda no dashboard) — nunca
pelo nome de guilda em texto que vem no próprio arquivo, porque esse campo
vem com espaçamento inconsistente (ex. "- P A R A B E L L U M -") e não é
confiável. Se aparecer um guildId que não está no guild_id_map.json, o
script AVISA e pula essas linhas (não inventa nome de guilda) — elas ficam
salvas à parte pra você conferir e completar o guild_id_map.json.

O que ele faz, na ordem:
  1. Lê o roster e agrupa os personagens por conta E por guildId.
  2. Pra cada guilda reconhecida, verifica cada conta nova contra as
     guildas rivais (mesma lógica e mesmo ritmo do radar_de_topos.py).
  3. Salva um novo_topos_<guilda>.json por guilda dentro de resultados/.
  4. Chama o merge.py automaticamente — adiciona essas contas novas nas
     guildas certas (sem apagar quem já estava lá) e regera o index.html.
  5. Marca quem for topo nessa rodada como "novo" no dashboard, até a
     próxima vez que você rodar esse script.
"""

import sys
import os
import json
import time
import importlib.util

ROOT = os.path.dirname(os.path.abspath(__file__))
RESULTADOS_DIR = os.path.join(ROOT, "resultados")
GUILD_ID_MAP_PATH = os.path.join(ROOT, "guild_id_map.json")
DB_PATH = os.path.join(ROOT, "guilds_db.json")
ELIM_PATH = os.path.join(ROOT, "eliminados_historico.json")
SEM_ID_PATH = os.path.join(RESULTADOS_DIR, "linhas_sem_guildId.txt")

# importa as funcoes do radar_de_topos.py (mesma pasta) sem duplicar codigo
spec = importlib.util.spec_from_file_location("radar_de_topos", os.path.join(ROOT, "radar_de_topos.py"))
radar = importlib.util.module_from_spec(spec)
spec.loader.exec_module(radar)


def load_json(path, default):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return default


def slugify(name):
    import re
    s = name.lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    return s.strip("_")


def main():
    if len(sys.argv) < 2:
        print('Uso: python3 atualizar.py <arquivo_roster.txt>')
        sys.exit(1)

    caminho_roster = sys.argv[1]
    guild_id_map = load_json(GUILD_ID_MAP_PATH, {})
    db = load_json(DB_PATH, {})
    eliminados = load_json(ELIM_PATH, {})

    if not guild_id_map:
        print("AVISO: guild_id_map.json está vazio ou não existe — nenhuma guilda vai ser reconhecida.")

    # apelidos que a gente já conhece (já verificados antes ou já vetados) —
    # não faz sentido gastar tempo escaneando eles de novo no Ankama
    ja_conhecidos = set(eliminados.keys())
    for entry in db.values():
        for c in entry.get("checked", []):
            ja_conhecidos.add(c.get("apelido"))

    os.makedirs(RESULTADOS_DIR, exist_ok=True)

    # 1. le o roster e agrupa por guildId -> {(apelido, accountId): [nomes]},
    #    pulando quem já é conhecido (já verificado antes ou já vetado)
    por_guilda = {}
    sem_id = []
    linhas_invalidas = []
    ja_pulados = 0
    with open(caminho_roster, encoding="utf-8") as f:
        for linha in f:
            linha = linha.strip()
            if not linha or "|" not in linha:
                continue
            partes = linha.split("|")
            if partes[0] != "NOVO_MEMBRO":
                continue  # linha de cabeçalho/resumo/outra coisa, ignora silenciosamente
            if len(partes) != 7:
                linhas_invalidas.append(linha)
                continue
            _tag, nome, guild_id, _nome_guilda_bruto, apelido, account_id, _nivel = partes
            if apelido in ja_conhecidos:
                ja_pulados += 1
                continue
            nome_guilda = guild_id_map.get(guild_id)
            if not nome_guilda:
                sem_id.append(linha)
                continue
            contas = por_guilda.setdefault(nome_guilda, {})
            chave = (apelido, account_id)
            contas.setdefault(chave, []).append(nome)

    if linhas_invalidas:
        print(f"AVISO: {len(linhas_invalidas)} linha(s) num formato que eu não reconheço — ignorei elas, não inventei nada. Confira se o arquivo é mesmo do formato esperado:")
        for l in linhas_invalidas[:5]:
            print(f"       {l}")
        if len(linhas_invalidas) > 5:
            print(f"       ... e mais {len(linhas_invalidas) - 5}")
        print()

    if ja_pulados:
        print(f"{ja_pulados} conta(s) do roster já eram conhecidas (já verificadas ou já vetadas antes) — pulei elas.")
        print()

    if sem_id:
        with open(SEM_ID_PATH, "a", encoding="utf-8") as f:
            f.write("\n".join(sem_id) + "\n")
        guild_ids_desconhecidos = sorted(set(l.split("|")[2] for l in sem_id))
        print(f"AVISO: {len(sem_id)} linha(s) com guildId desconhecido (não estão em guild_id_map.json).")
        print(f"       guildId(s) desconhecido(s): {', '.join(guild_ids_desconhecidos)}")
        print(f"       Essas linhas foram salvas em {SEM_ID_PATH} pra você conferir depois.")
        print()

    if not por_guilda:
        print("Nenhuma conta com guildId reconhecido foi encontrada — nada pra processar.")
        return

    print(f"Encontrei contas novas em {len(por_guilda)} guilda(s): {', '.join(por_guilda.keys())}")
    print()

    arquivos_gerados = []

    for nome_guilda, contas in por_guilda.items():
        print(f"=== {nome_guilda} ({len(contas)} conta(s) nova(s)) ===")
        checados = []
        topos = []

        for i, ((apelido, account_id), chars_mav) in enumerate(sorted(contas.items()), start=1):
            print(f"  [{i}/{len(contas)}] {apelido} ...", end=" ", flush=True)
            try:
                personagens = radar.verificar_conta(apelido)
            except Exception as e:
                print(f"ERRO ({e}) — pulei essa conta, confira manualmente.")
                checados.append({
                    "apelido": apelido,
                    "mavChar": " / ".join(chars_mav),
                    "mavGuild": nome_guilda,
                    "flagged": False,
                    "erro": str(e),
                })
                time.sleep(radar.PAUSA_ENTRE_CONTAS)
                continue

            vinculos_rivais = []
            for p in personagens:
                guilda = p["guilda"]
                servidor = p["servidor"]
                if guilda and guilda in radar.RIVAL_LOOKUP and servidor == radar.SERVIDOR_VALIDO:
                    vinculos_rivais.append({
                        "rivalChar": p["nome"],
                        "rivalGuild": guilda,
                        "rivalAlliance": radar.RIVAL_LOOKUP[guilda],
                    })

            flagged = len(vinculos_rivais) > 0
            checados.append({
                "apelido": apelido,
                "mavChar": " / ".join(chars_mav),
                "mavGuild": nome_guilda,
                "flagged": flagged,
            })

            if flagged:
                print(f"TOPO! -> {vinculos_rivais}")
                topos.append({
                    "apelido": apelido,
                    "mavChar": " / ".join(chars_mav),
                    "mavGuild": nome_guilda,
                    "vinculos": vinculos_rivais,
                })
            else:
                print("limpo")

            time.sleep(radar.PAUSA_ENTRE_CONTAS)

        resultado = {
            "guilda": nome_guilda,
            "novasContas": len(checados),
            "novosTopos": len(topos),
            "checados": checados,
            "topos": topos,
        }

        nome_arquivo = f"novo_topos_{slugify(nome_guilda)}.json"
        caminho_saida = os.path.join(RESULTADOS_DIR, nome_arquivo)
        with open(caminho_saida, "w", encoding="utf-8") as f:
            json.dump(resultado, f, ensure_ascii=False, indent=2)
        arquivos_gerados.append(caminho_saida)
        print(f"  -> {len(topos)} topo(s) de {len(checados)} conta(s) novas. Salvo em resultados/{nome_arquivo}")
        print()

    # 2. chama o merge.py automaticamente
    print("Atualizando o dashboard...")
    merge_spec = importlib.util.spec_from_file_location("merge", os.path.join(ROOT, "merge.py"))
    merge_mod = importlib.util.module_from_spec(merge_spec)
    merge_spec.loader.exec_module(merge_mod)
    merge_mod.main()


if __name__ == "__main__":
    main()
