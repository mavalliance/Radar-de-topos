# Radar de Topos — pipeline local (sem Claude)

Esses arquivos deixam você atualizar o dashboard sozinho, no seu computador,
sem precisar de mim (Claude) nem gastar nada de token na maioria das vezes.

## Arquivos

- **`index.html`** — o dashboard pronto, já publicado (esse é o arquivo que o
  GitHub Pages mostra no site). **Não edite ele na mão** — ele é sempre
  regerado pelos scripts abaixo.
- **`template.html`** — o "molde" do dashboard (visual, textos, JS) sem os
  dados das guildas. Só mexe aqui se quiser mudar alguma coisa visual (cor,
  layout etc.) — nesse caso, me chama numa conversa nova que eu ajusto e te
  devolvo o `template.html` atualizado.
- **`guilds_db.json`** — o "banco de dados" com todas as guildas já
  processadas até agora. Não precisa mexer nele na mão.
- **`guild_id_map.json`** — de/para entre o `guildId` de cada guilda da MAV
  (o número que vem no roster) e o nome dela no dashboard. Tem as 43 guildas
  da MAV. Se um dia entrar uma guilda nova na aliança, adicione aqui o
  `"guildId": "Nome Certo"` antes de rodar o `atualizar.py`.
- **`eliminados_historico.json`** — registro permanente de toda conta que
  você já vetou (rodando `eliminar.py`). Nunca é apagado sozinho — serve pra
  você não perder o histórico e pra essas contas não voltarem a ser
  acusadas de topo à toa se aparecerem de novo num roster.
- **`name_map.json`** — de/para entre o nome que sai no campo `"guilda"` do
  JSON do `radar_de_topos.py` (varredura manual, por nome) e o nome que
  aparece no dashboard.
- **`icons.json`** — o brasão (ícone) de cada guilda, em base64. Se aparecer
  uma guilda nova que eu nunca processei, você vai precisar me pedir o
  ícone dela numa conversa.
- **`exceptions.json`** — contas que sempre contam como limpas mesmo se o
  script encontrar vínculo.
- **`radar_de_topos.py`** — o seu script original de varredura (sem
  mudanças), usado tanto sozinho quanto por dentro do `atualizar.py`.
- **`atualizar.py`** — o comando do dia a dia (ver abaixo).
- **`eliminar.py`** — o comando pra marcar uma conta como vetada (ver
  abaixo).
- **`merge.py`** — o script interno que junta tudo e gera o `index.html`. Os
  dois comandos acima já chamam ele sozinhos no final — você raramente
  precisa rodar ele direto.
- **`resultados/`** — pasta de trabalho onde os scripts guardam os arquivos
  processados (`resultados/processados/`), e onde ficam salvas, à parte,
  as linhas de roster com `guildId` desconhecido
  (`linhas_sem_guildId.txt`), se acontecer.

## Rotina do dia a dia: `atualizar.py` (1 comando só)

Quando tiver um roster novo (`.txt`, no formato de sempre, com jogadores
misturados de várias guildas da aliança), não precisa separar por guilda
nem digitar nome nenhum. É só:

```
cd ~/Desktop/GitHub
python3 atualizar.py caminho/do/roster_novo.txt
```

Isso sozinho:

1. Lê o roster inteiro e descobre a guilda de cada personagem pelo
   `guildId` (usando o `guild_id_map.json`).
2. Pula quem você já conhece (contas já verificadas antes, ou já vetadas) —
   só gasta tempo checando quem é realmente novo.
3. Cruza cada conta nova contra as guildas rivais, igual o
   `radar_de_topos.py` sempre fez.
4. Já atualiza o `index.html` sozinho, somando as contas novas nas guildas
   certas (sem apagar quem já estava lá).
5. Marca com o selo **NOVO** quem foi flagrado como topo nessa rodada, até
   você rodar o `atualizar.py` de novo.

Se aparecer um `guildId` que não está no `guild_id_map.json` (por exemplo,
uma guilda nova entrando na aliança), o script avisa no terminal, não
inventa nada, e salva essas linhas à parte em
`resultados/linhas_sem_guildId.txt` pra você conferir.

Depois de rodar, é só publicar (ver "Como publicar" abaixo).

## Marcar uma conta como vetada: `eliminar.py`

Quando você decidir expulsar/vetar uma conta que apareceu como topo:

```
python3 eliminar.py "Apelido#1234"
```

Dá pra passar mais de um apelido de uma vez:

```
python3 eliminar.py "Apelido#1234" "Outro#5678"
```

Isso:

1. Tira a conta da lista de topos ativos do Radar de Topos.
2. Guarda um registro permanente em `eliminados_historico.json` (com a
   data), pra você não perder o histórico e pra ela não voltar a ser
   acusada de novo se reaparecer num roster futuro.
3. Já atualiza o `index.html` sozinho.

**Importante:** isso não mexe no seu outro dashboard, o "Vetados MAV" — são
dois artifacts separados. Depois de rodar o `eliminar.py`, é você quem
adiciona a conta lá no Vetados MAV manualmente (ou numa conversa comigo, se
preferir).

## Varredura manual de uma guilda só (jeito antigo, ainda funciona)

Se preferir rodar o `radar_de_topos.py` direto numa guilda específica (modo
de sempre, com o nome digitado na mão):

1. Rode o `radar_de_topos.py` normalmente.
2. Copie o `resultado_topos_*.json` gerado pra dentro da pasta
   `resultados/`.
3. Rode `python3 merge.py`.

Esse formato faz uma **substituição completa** da guilda (usa pra
revarredura total). Já o `atualizar.py` faz uma **soma incremental** (só
contas novas).

## Como publicar

1. Depois de rodar `atualizar.py` ou `eliminar.py`, dá uma conferida no
   `index.html` (clique duplo, abre no navegador).
2. Abra o **GitHub Desktop** — ele vai mostrar os arquivos alterados
   (`index.html`, `guilds_db.json` e, se for o caso,
   `eliminados_historico.json`).
3. Escreve uma mensagem curta tipo "Atualiza guildas X, Y" no campo de
   commit, embaixo à esquerda.
4. Clica em **Commit to main**, depois em **Push origin**.
5. Espera 1-2 minutinhos e o site já atualiza sozinho em
   `https://SEU-USUARIO.github.io/Radar-de-topos/`.

Nenhum desses passos usa Claude.

## Quando você PRECISA falar comigo de novo

- Uma guilda nova da aliança nunca processada antes (preciso te passar o
  ícone/nome certo pra colocar em `icons.json`, `name_map.json` e você
  adiciona o `guildId` dela em `guild_id_map.json`).
- Quiser mudar alguma coisa visual do dashboard (cor, layout, textos, uma
  seção nova).
- Algum script der erro que você não entenda.

Fora isso, é `atualizar.py` / `eliminar.py` + GitHub Desktop e pronto.
