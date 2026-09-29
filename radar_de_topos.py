"""
radar_de_topos.py

Verifica as contas de uma guilda MAV (Manus Vindictae) contra a lista de
guildas rivais, sem precisar abrir cada perfil manualmente nem gastar
usage de IA por conta.

O QUE ELE FAZ
-------------
1. Le um arquivo de texto com o roster da guilda, no formato:
   nome|guildId|allianceId|apelido|accountId  (uma linha por personagem)
2. Agrupa as linhas por conta (apelido + accountId), porque uma conta pode
   ter varios personagens na mesma guilda MAV.
3. Para cada conta distinta, abre o perfil publico dela em
   account.ankama.com e le a lista de TODOS os personagens daquela conta
   (em qualquer servidor).
4. Confere se algum desses personagens esta numa guilda da lista de rivais
   E no servidor Talok (personagem rival em outro servidor, tipo
   TemporiX-2, NAO conta como topo).
5. Salva o resultado num arquivo JSON PROPRIO PRA CADA GUILDA (nome baseado
   no "Nome da Guilda" que voce digitar, ex: resultado_topos_Eternity.json)
   e imprime um resumo no terminal. Assim rodar uma guilda nao sobrescreve
   o resultado da guilda anterior — pode rodar varias e mandar todos os
   arquivos juntos de uma vez.

COMO USAR
---------
1. Instale as duas bibliotecas que faltam (uma vez so, no terminal):
       pip install requests beautifulsoup4

2. Salve o roster do jogo num arquivo de texto, um arquivo por
   guilda (ex: xeque.txt, eternity.txt), com uma linha por personagem.

3. Rode no terminal, na mesma pasta do script, um comando por guilda:
       python3 radar_de_topos.py <arquivo.txt> "Nome da Guilda"

   Exemplo:
       python3 radar_de_topos.py xeque.txt "Xeque-Mate"
       python3 radar_de_topos.py eternity.txt "Eternity"

4. Espera cada um terminar (ele mostra o progresso conta por conta) e
   confere o arquivo resultado_topos_<Nome da Guilda>.json que ele cria
   na mesma pasta. Pode rodar quantas guildas quiser em sequencia — cada
   uma gera o seu proprio arquivo, sem apagar as anteriores — e so depois
   mandar todos os arquivos JSON de uma vez.

Se o Ankama mudar o layout da pagina de perfil no futuro, a funcao
parse_characters() abaixo e a unica que precisa ser ajustada.
"""

import sys
import json
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Lista de guildas rivais monitoradas (nomes EXATOS, copiados do Yuri).
# Nao "arrumar" ortografia nem aproximar nomes parecidos aqui — o nome tem
# que bater literalmente com o que esta na pagina do Ankama.
# ---------------------------------------------------------------------------
RIVAL_GUILDS = {
    "Mythic Vanguard Pact": [
        "H a k a i", "A M B U", "-TRAUMA-", "Golden Dawn", "Akatsuki", "CHILEHUB",
        "-ANNUNAKI Z-", "-Dead End-", "XxpurgexX", "SUPREMACIA", "Disasters",
        "'-Sacreed Kingdoom-'", "Infracta", "K A R M A", "Pri-Pra", "-'G'otcha-",
        "'C A M B U M B O'", "Angeles Caidos", "Reaper of Souls", "Kame House",
        "Terrorcaos", "SAMORIANOS", "Artesanos y Mercantes", "VORTEX - PRIME", "KING'S",
    ],
    "Imperio Oculto": [
        "-U N K N O W N-", "Amnesia", "KAMIKAZE", "Anubis", "-C A N O P E E-",
        "OhMyGod", "-RAGNAROK-", "Clinica Davila", "Abstract", "Magna",
        "M I T T E R N A C T H", "U L T R A L U X U R Y",
    ],
    "MONARQUIA": [
        "I N M O R T A L S", "-P R I M E-", "Peccatori Notturni", "O'mega",
        "-Shambala-", "-SPECTRUM-", "Phantom Knights", "Stark", "R A I C E S",
        "H O R C R U X---------------", "ALMA BRASILEIRA", "ILUMINADOS",
        "-CLAN BUSHIDO-", "inglourious basterds", "Team America", "-DARK WARRIOS-",
        "-Apocalipse-", "--Night Hunters--", "Crown", "-EXILED-",
    ],
}

# Monta um dicionario nome-da-guilda -> alianca, pra achar rapido.
RIVAL_LOOKUP = {}
for alliance, guilds in RIVAL_GUILDS.items():
    for g in guilds:
        RIVAL_LOOKUP[g] = alliance

# ---------------------------------------------------------------------------
# As 43 guildas da propria alianca MAV (nomes oficiais, confirmados pelo Yuri
# em 2026-09-29, incluindo o espacamento/traços decorativos que cada guilda
# usa no nome). Usado so pra saber se uma conta ainda tem personagem em
# alguma delas (deteccao de saida da alianca) -- ver normalize_guild_name().
# ---------------------------------------------------------------------------
MAV_GUILDS = [
    "Eternity", "- M O N O P O L Y -", "- V I R U Z -", "Espiritus perdidos",
    "Redtube", "Tears Of Kingdom", "XEQUE-MATE", "letal-hunter", "- CAOS-",
    "- A B Y S S A L -", "- P A R A B E L L U M -", "Shinigami Daio", "J E F E S",
    "-Loyalty-", "Viciosos", "Nihil", "R Y O Z A N P A K U", "Madnes", "Onirico",
    "- Old School -", "- E V I L M A C H I N E -", "La Kravatt", "- A M A N E C E R -",
    "'G' O L D E N", "U Z U M A K I --------------", "R A V E N F A L L",
    "Fairy Tail", "B O F F", "--ELITE--", "N O C T U R N E", "- P E L I G R O -",
    "- F A L T O N E S -", "-Critical Failure-", "- A L M A -",
    "Ragnarok New Order", "Los-Perversos", "- B E R S E R K E R -",
    "V A N G U A R D", "-V I N D I C T A E-", "-A S U R A S-", "- Bohemian -",
    "Wu-Tang Clan", "H E A V E N",
]


def normalize_guild_name(nome):
    """Deixa so letras e numeros, minusculo -- pra comparar nome de guilda
    ignorando espaco/traco/aspas decorativos (que variam de formatacao entre
    guildas e sao dificeis de transcrever com 100% de fidelidade)."""
    if not nome:
        return ""
    return "".join(ch for ch in nome.lower() if ch.isalnum())


MAV_GUILDS_NORM = {normalize_guild_name(n) for n in MAV_GUILDS}

# So conta como topo se o personagem rival estiver neste servidor.
SERVIDOR_VALIDO = "Talok"

HEADERS = {"User-Agent": "Mozilla/5.0 (radar-de-topos script pessoal)"}
PAUSA_ENTRE_CONTAS = 0.6  # segundos — nao martelar o site


def parse_roster(caminho_arquivo):
    """Le o roster e agrupa por conta (apelido, accountId)."""
    contas = {}  # (apelido, accountId) -> lista de nomes de personagem MAV
    with open(caminho_arquivo, encoding="utf-8") as f:
        for linha in f:
            linha = linha.strip()
            if not linha or "|" not in linha:
                continue
            partes = linha.split("|")
            if len(partes) != 5:
                continue
            nome, guild_id, alliance_id, apelido, account_id = partes
            chave = (apelido, account_id)
            contas.setdefault(chave, []).append(nome)
    return contas


def profile_url(apelido):
    slug = apelido.replace("#", "-")
    return f"https://account.ankama.com/pt/perfil-ankama/{slug}"


def parse_characters(html):
    """
    Le a tabela de personagens da pagina de perfil Ankama.
    Retorna uma lista de dicts: {nome, classe, nivel, servidor, guilda}
    (guilda vem como None se o personagem nao tiver guilda).
    """
    soup = BeautifulSoup(html, "html.parser")
    bloco = soup.select_one(".ak-block-persos")
    if bloco is None:
        return []

    personagens = []
    for linha in bloco.select("tbody tr"):
        celulas = linha.find_all("td")
        if len(celulas) < 4:
            continue
        link_nome = celulas[0].find("a")
        nome = link_nome.get_text(strip=True) if link_nome else celulas[0].get_text(strip=True)
        classe = celulas[1].get_text(strip=True)
        nivel = celulas[2].get_text(strip=True)
        servidor = celulas[3].get_text(strip=True)
        guilda = None
        if len(celulas) >= 5:
            link_guilda = celulas[4].find("a")
            if link_guilda:
                guilda = link_guilda.get_text(strip=True)
        personagens.append({
            "nome": nome,
            "classe": classe,
            "nivel": nivel,
            "servidor": servidor,
            "guilda": guilda,
        })
    return personagens


def verificar_conta(apelido):
    """Baixa o perfil e retorna a lista de personagens da conta."""
    url = profile_url(apelido)
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    return parse_characters(resp.text)


def main():
    if len(sys.argv) < 3:
        print("Uso: python radar_de_topos.py <arquivo_roster.txt> \"Nome da Guilda MAV\"")
        sys.exit(1)

    caminho_roster = sys.argv[1]
    nome_guilda_mav = sys.argv[2]

    contas = parse_roster(caminho_roster)
    total_personagens_mav = sum(len(v) for v in contas.values())
    print(f"Roster lido: {len(contas)} contas distintas, {total_personagens_mav} personagens na {nome_guilda_mav}.")
    print()

    checados = []
    topos = []

    for i, ((apelido, account_id), chars_mav) in enumerate(sorted(contas.items()), start=1):
        print(f"[{i}/{len(contas)}] {apelido} ...", end=" ", flush=True)
        try:
            personagens = verificar_conta(apelido)
        except Exception as e:
            print(f"ERRO ({e}) — pulei essa conta, confira manualmente.")
            checados.append({
                "apelido": apelido,
                "accountId": account_id,
                "mavChar": " / ".join(chars_mav),
                "erro": str(e),
            })
            time.sleep(PAUSA_ENTRE_CONTAS)
            continue

        vinculos_rivais = []
        for p in personagens:
            guilda = p["guilda"]
            servidor = p["servidor"]
            if guilda and guilda in RIVAL_LOOKUP and servidor == SERVIDOR_VALIDO:
                vinculos_rivais.append({
                    "rivalChar": p["nome"],
                    "rivalGuild": guilda,
                    "rivalAlliance": RIVAL_LOOKUP[guilda],
                    "servidor": servidor,
                })

        flagged = len(vinculos_rivais) > 0
        checados.append({
            "apelido": apelido,
            "accountId": account_id,
            "mavChar": " / ".join(chars_mav),
            "mavGuild": nome_guilda_mav,
            "flagged": flagged,
        })

        if flagged:
            print(f"TOPO! -> {vinculos_rivais}")
            topos.append({
                "apelido": apelido,
                "accountId": account_id,
                "mavChar": " / ".join(chars_mav),
                "mavGuild": nome_guilda_mav,
                "vinculos": vinculos_rivais,
            })
        else:
            print("limpo")

        time.sleep(PAUSA_ENTRE_CONTAS)

    resultado = {
        "guilda": nome_guilda_mav,
        "totalPersonagensRoster": total_personagens_mav,
        "totalContas": len(contas),
        "totalTopos": len(topos),
        "checados": checados,
        "topos": topos,
    }

    nome_arquivo_seguro = "".join(
        c if (c.isalnum() or c in "-_") else "_" for c in nome_guilda_mav
    )
    saida = Path(f"resultado_topos_{nome_arquivo_seguro}.json")
    saida.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")

    print()
    print(f"Pronto. {len(topos)} conta(s) topo de {len(contas)} verificadas.")
    print(f"Resultado completo salvo em: {saida.resolve()}")


if __name__ == "__main__":
    main()
