#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
eliminar.py — marca uma ou mais contas como vetadas.

O que faz:
  1. Tira a conta do Radar de Topos (some da lista de topos ativos).
  2. Guarda um registro permanente em eliminados_historico.json — esse
     arquivo NUNCA é apagado, só cresce. Serve pra:
       - você não perder o histórico de quem já foi pego, mesmo que ela
         saia do dashboard;
       - se essa mesma conta aparecer de novo num roster futuro, o
         atualizar.py NÃO volta a marcar ela como topo novo sem avisar.
  3. Já regera o index.html sozinho (não precisa rodar merge.py depois).

Isso NÃO mexe no dashboard "Vetados MAV" (o outro artifact, separado, que
você mantém à parte) — esse script só limpa o Radar de Topos e guarda o
histórico. Depois de rodar, é você quem adiciona a conta lá no Vetados.

Uso:
    python3 eliminar.py "Apelido#1234"
    python3 eliminar.py "Apelido#1234" "Outro#5678" "Mais#0000"
"""

import sys
import os
import json
import datetime
import importlib.util

ROOT = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(ROOT, "guilds_db.json")
ELIM_PATH = os.path.join(ROOT, "eliminados_historico.json")


def load_json(path, default):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return default


def main():
    if len(sys.argv) < 2:
        print('Uso: python3 eliminar.py "Apelido#1234" [outro "Apelido#5678" ...]')
        sys.exit(1)

    alvos = set(sys.argv[1:])
    db = load_json(DB_PATH, {})
    eliminados = load_json(ELIM_PATH, {})

    hoje = datetime.date.today().isoformat()
    encontrados = set()

    for guild_name, entry in db.items():
        flagged = entry.get("flagged", [])
        restantes = []
        for f in flagged:
            if f.get("apelido") in alvos:
                encontrados.add(f["apelido"])
                registro = dict(f)
                registro.pop("isNovo", None)
                registro["dataEliminacao"] = hoje
                # se a conta tinha mais de um vínculo, guarda sempre o mais recente processado
                eliminados[f["apelido"]] = registro
            else:
                restantes.append(f)
        entry["flagged"] = restantes

        for c in entry.get("checked", []):
            if c.get("apelido") in alvos:
                c["flagged"] = False

    nao_encontrados = alvos - encontrados
    if nao_encontrados:
        print("AVISO: não encontrei como topo ativo no Radar de Topos:")
        for a in sorted(nao_encontrados):
            print(f"  - {a}")
        print("  (talvez já tenha sido eliminada antes, ou o apelido está escrito diferente)")
        print()

    if not encontrados:
        print("Nada foi removido.")
        return

    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)
    with open(ELIM_PATH, "w", encoding="utf-8") as f:
        json.dump(eliminados, f, ensure_ascii=False, indent=2)

    print(f"Removido do Radar de Topos e guardado no histórico: {', '.join(sorted(encontrados))}")
    print("Lembre de adicionar essa(s) conta(s) no dashboard Vetados MAV também.")
    print()

    print("Atualizando o dashboard...")
    merge_spec = importlib.util.spec_from_file_location("merge", os.path.join(ROOT, "merge.py"))
    merge_mod = importlib.util.module_from_spec(merge_spec)
    merge_spec.loader.exec_module(merge_mod)
    merge_mod.main()


if __name__ == "__main__":
    main()
