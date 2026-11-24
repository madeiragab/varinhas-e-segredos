#!/usr/bin/env python3
"""Confere as contas do livro contra o index.html gerado. Enumeração exata, sem dependências.

Execute: python build.py && python tests/auditoria.py
"""
import pathlib, re, sys
from itertools import product
from functools import lru_cache
from collections import defaultdict

HTML = (pathlib.Path(__file__).resolve().parent.parent / "index.html").read_text(encoding="utf-8")
OPERACOES_ANIMAGIA = (9, 11, 11, 13, 13)
falhas = []

def checa(nome, ok):
    print(("ok    " if ok else "FALHA ") + nome)
    if not ok: falhas.append(nome)

def resultado(sides, faces, dt):
    """Soma os 3 maiores; crítico (dois iguais >= 4 ou DT+6) só se a DT é alcançável; desastre = tudo 1."""
    pos = sorted(faces, reverse=True)[:3]
    maximo = sum(sorted(sides, reverse=True)[:3])
    total = sum(pos)
    desastre = all(x == 1 for x in faces)
    altos = [x for x in pos if x >= 4]
    critico = maximo >= dt and (len(set(altos)) < len(altos) or total >= dt + 6)
    return (not desastre and (critico or total >= dt)), critico, desastre

@lru_cache(None)
def dist(sides, dt):
    n = s = c = d = 0
    for fs in product(*(range(1, k + 1) for k in sides)):
        n += 1; a, b, e = resultado(sides, fs, dt); s += a; c += b; d += e
    return s / n, c / n, d / n

def animagia(a, b, corr):
    @lru_cache(None)
    def segue(etapa, sobra):
        if etapa == len(OPERACOES_ANIMAGIA): return 1.0
        s, _, d = dist((a, b), OPERACOES_ANIMAGIA[etapa])
        p = s * segue(etapa + 1, sobra)
        if sobra: p += (1 - s - d) * segue(etapa, sobra - 1)
        return p
    return segue(0, corr)

def ano(a, b, dt, aprov=2, destaque=0):
    s, c, _ = dist((a, b), dt)
    prova = {0: 1 - s, 1: s - c, 2: c}
    tri = defaultdict(float)
    for x, px in prova.items():
        for y, py in prova.items(): tri[min(6, aprov + x + y + destaque)] += px * py
    d = {0: 1.0}
    for _ in range(3):
        n = defaultdict(float)
        for k, pk in d.items():
            for v, pv in tri.items(): n[k + v] += pk * pv
        d = n
    nota = defaultdict(float)
    for k, pk in d.items(): nota[k // 3] += pk
    return nota

def pct(x):  # como o livro escreve: uma casa abaixo de 10%, inteiro acima
    v = x * 100
    return (f"{v:.1f}".replace(".", ",") if v < 10 else f"{v:.0f}") + "%"

def mesmo(livro, calc):
    """Aceita o número do livro se ele for o arredondamento (inteiro ou uma casa) do calculado."""
    v = calc * 100
    alvo = float(livro.rstrip("%").replace(",", "."))
    return abs(alvo - v) <= (0.05 if "," in livro else 0.5) + 1e-9

def tabela_depois(marca):
    i = HTML.index(marca); j = HTML.index("</table>", i)
    linhas = re.findall(r"<tr>(.*?)</tr>", HTML[i:j], re.S)
    return [[re.sub(r"<[^>]+>", "", c).strip() for c in re.findall(r"<td[^>]*>(.*?)</td>", l, re.S)] for l in linhas]

# 1. motor básico
checa("2d4 DT 9 impossível", dist((4, 4), 9)[0] == 0)
checa("2d8 DT 11 = 23/64", abs(dist((8, 8), 11)[0] - 23 / 64) < 1e-12)
checa("2d10 DT 11 crítico 15%", abs(dist((10, 10), 11)[1] - .15) < 1e-12)

# 2. tabela da Animagia, como publicada (0, 1 e 2 correções)
for linha in tabela_depois("<th>Dados no teste</th>"):
    if len(linha) < 4: continue
    a, b = map(int, re.findall(r"d(\d+)", linha[0]))
    for k, cel in enumerate(linha[1:4]):
        checa(f"Animagia d{a}+d{b} com {k} correção(ões): livro {cel}, conta {pct(animagia(a, b, k))}", mesmo(cel, animagia(a, b, k)))
checa("Animagia: no máximo 2 correções no texto", "No máximo 2." in HTML and "(máximo 2)" in HTML)

# 3. notas do ano, como publicadas
for linha in tabela_depois("<th class=\"num\">O com destaque nos três</th>"):
    a, b = map(int, re.findall(r"d(\d+)", linha[0]))
    dt = int(re.match(r"\d+", linha[1]).group())
    n0, n1 = ano(a, b, dt), ano(a, b, dt, destaque=1)
    calc = [sum(p for k, p in n0.items() if k >= 3), sum(p for k, p in n0.items() if k >= 4),
            sum(p for k, p in n0.items() if k >= 5), sum(p for k, p in n1.items() if k >= 5)]
    for nome, cel, v in zip(("A+", "E+", "O", "O c/ destaque"), linha[2:6], calc):
        checa(f"Nota d{a}+d{b} DT {dt} {nome}: livro {cel}, conta {pct(v)}", mesmo(cel, v))

# 4. orçamento curricular
checa("currículo: 84 bruto, 82 efetivo, 128 de sobra", all(s in HTML for s in ("84 PE", "82 PE efetivos", "128 de sobra")))
checa("teto anual de 30 PE", "Teto do ano: 30 PE" in HTML)

# 5. regras de magia (regressão: frases que fixam a regra)
FRASES = {
    "Fogomaldito: controle perdido não volta": "Não se recupera o controle",
    "Fogomaldito: contenção 3 sucessos antes de 2 falhas": "3 sucessos antes de 2 falhas",
    "Protego Diabolica: Ruptura ignora lealdade": "A lealdade não conta mais",
    "Protego Diabolica: anel, centro não queima": "O centro não queima",
    "Sectumsempra: Lesão antes do ferimento": "role a Lesão primeiro",
    "Gemino: Saturação para em 6": "A Saturação para em 6",
    "RA fixo em efeito persistente": "RA fixo:",
    "sem varinha: metade dos números": "Metade dos números",
    "sem varinha: efeito sem número": "Efeito sem número",
    "Voto Perpétuo: cláusulas por escrito": "palavra por palavra",
    "Maxima: não serve para tudo": "Não é um sufixo que serve para tudo",
    "Maxima: abaixo das duas DTs não sai nada": "alcançou só a DT do feitiço comum, sai o comum; abaixo das duas, falha",
    "sem varinha: Círculo 4 pede o 3": "Tudo o que o Círculo 3 pediu, dois de Círculo 3 em Domínio excepcional",
    "marcas: uma chance por feitiço por cena": "No máximo uma chance por feitiço por cena",
    "condições: a mesma não acumula": "A mesma condição não acumula consigo mesma",
    "poções: kit não se desmonta": "que não se desmonta",
    "poções: RA da poção no d8": "quem bebe rola <span class=\"dado\">d8</span> na hora",
    "poções: Excelente conserva como a Boa": "Conserva pelo menos tanto quanto a Boa",
    "fraqueza: DT arredonda para cima": "arredondada para cima (Perigo 3: DT 7)",
    "objeto Excelente não falha": "o de Acabamento excelente não falha",
    "Petisco: só quem quer comer": "Uma criatura que possa e queira comer",
    "hora extra: só com emprego": "Só com emprego, uma vez por semana",
    "clube: PE dentro do teto": "dentro do teto de 4 PE da sessão e de 30 PE do ano",
    "aliados morrem como personagens": "Ninguém tem imunidade de roteiro",
    "NPC: Grau não é Nível": "Grau não é o Nível dos personagens",
    "Imperdoáveis numa tabela": 'id="imperdoaveis-ficha"',
    "apêndice: crítico rende duas marcas": "duas marcas de prática em Flipendo",
    "apêndice: Estudar usa DT do Círculo": "DT 5 do Círculo 1",
    "introdução cita o XVI": "Os capítulos <strong>XIII a XVI</strong>",
    "Mestre de Poções: feitiço assinatura escrito": "Feitiço assinatura: <strong>Vapor Acerbus</strong>",
    "Fanático: um quarto do PV, não Fase": "Fanático: com um quarto do PV ou menos",
    "material Excelente dura como a Boa": "Tudo o que a Boa tem, inclusive durar o dobro do prazo",

    "Tempestade de fogo não é fogo das trevas": "Não é fogo das trevas",
    "Fulgur Caeli: nome do jogo, só Mestre": "Só um bruxo Mestre",
    "materiais: achar não dá direito de ferir": "Achar uma criatura não dá direito de machucá-la",
    "materiais: fonte esgotada não rende": "Fonte esgotada não rende de novo",
    "materiais: preparados não se somam": "três doses não dão +3 passos",
    "objetos: três ativos": "no máximo três objetos encantados",
    # auditoria consolidada
    "tipo do feitiço sai do efeito, não de uma palavra": "Não depende de uma palavra na descrição",
    "função separada da resolução": "A função diz para que o feitiço serve e não muda como ele se resolve",
    "área: um lançamento contra a DT, uma defesa por alvo": "Nunca as duas coisas. Sem resistência indicada, só a reação salva.",
    "fase: dano e condições valem no fim dela": "Dano e condições de uma fase valem no fim dela",
    "não letal só no que dá para segurar": "nunca são não letais",
    "queda soma os dados": "<strong>somados</strong> (não é RA)",
    "lesão sem resultado novo piora a pior": "o tempo de cura dobra",
    "trauma sem resultado novo vira longo": "passa a sair só com tratamento longo",
    "marcas: no máximo duas por desafio": "no máximo duas marcas de prática por personagem",
    "sem varinha: Incompleto ou Indisponível": "Pergunte se meio efeito existe",
    "NPC: efeito em duas etapas": "Duas etapas, como para os personagens",
    "NPC desarmado: exceção sem varinha": "continua lançando só esses",
    "assinatura lança com Feitiços": "Lança com Feitiços ou Transfiguração e se resolve pelo tipo",
    "Vapor Acerbus com Mente + Feitiços": "Mente + Feitiços como todo feitiço criado",
    "PE: ano vivido completa as sessões": "a diferença até 18 como <em>ano vivido</em>",
    "PE: 30 é teto, não garantia": "30 é o <em>máximo</em>, não a garantia",
    "projetos param nas férias": "o relógio do projeto para",
    "minigames: regras comuns": "Regras comuns dos minigames",
    "uso criativo: Natural, Esticada, Ousada": "Ousada</strong></td><td>Pede mira",
    "uso criativo: física aberta, até 8 dados": "Nada passa de <strong>8 dados</strong>",
    "uso criativo: perfurante fora da vista trespassa": "<strong>trespassa</strong>",
    "ambiente: aguenta e rachado": "<strong>Rachado:</strong>",
    "doenças: PV máximo menor": "<h4>PV máximo menor</h4>",
    "doenças: estágios e teste": "abaixo do leve você sarou",
    "criar criatura: poder sob medida conferido com a Forja": "Conferido com a Forja: o Sopro",
    "criar objeto: função por categoria": "A função, em cada categoria",
    "bruxos sob medida: truque com vantagem e custo": "Todo truque tem uma vantagem e um custo",
    "bruxos usam o lugar": "Eles também usam o lugar",
    "usando o ambiente: cobertura leva o golpe": "A cobertura leva o golpe.",
    "usando o ambiente: armas improvisadas": "<h4>Armas improvisadas</h4>",
    "combinar feitiços: num lance só com Ímpeto, não é ação extra": "Não é ação extra e não junta dois ataques",
    "combinar feitiços: em coro": "Em coro: o mesmo feitiço",
    "combinar feitiços: desastre por tipo": "Cada tipo dá errado do seu jeito",
    "combinar feitiços: simultânea não sai sozinho": "Simultânea não sai sozinho com dois feitiços",
    "combinar feitiços: item faz uma parte": "Itens que fazem uma parte",
    "ambiente: tabela de queda por massa e altura": "O que cai em cima: massa e altura",
    "variante: nível custa 5 + nível atual": "5 + o nível atual",
    "variante: teto de 4 PE por sessão continua": "Teto por sessão continua: 4 PE",
    "feitiço além do alcance: até 2 Círculos, com mentor": "Até 2 Círculos acima",
    "xadrez de bruxo: online, dicas no limite de +2": "duas dicas por partida, no máximo",
    "minigames: passos e dado extra com limites separados": "têm limites separados, os do Capítulo II",
    "vassoura ajuda, não ganha (simulação)": "A vassoura ajuda, não ganha o jogo",
}
for nome, frase in FRASES.items():
    checa(nome, frase in HTML)
texto = re.sub(r"<[^>]+>", "", HTML)
for a, b, p1, p3 in ((10, 10, "39%", "6%"), (12, 12, "56%", "18%")):
    s = dist((a, b), 13)[0]
    checa(f"Fogomaldito d{a}+d{b} DT 13: livro {p1} e {p3} em três, conta {pct(s)} e {pct(s ** 3)}",
          mesmo(p1, s) and mesmo(p3, s ** 3) and p1 in texto and p3 in texto)

# 6. fabricação: DT = Círculo + 2, Preparo 8 × Círculo, estabilizar 10 × Círculo, Preparo alcançável
i = HTML.index('id="tabela-fabricacao"')
corpo = HTML[i:HTML.index("</table>", i)]
linhas = [l for l in (re.findall(r"<td[^>]*>([^<]*)</td>", x) for x in re.findall(r"<tr>(.*?)</tr>", corpo)) if l]
checa("fabricação: quatro Círculos", len(linhas) == 4)
for c, dt, prep, et, _, est in linhas:
    c, dt, prep, et, est = int(c), int(dt), int(prep), int(et), int(est)
    checa(f"fabricação Círculo {c}: DT {dt}, Preparo {prep}, {et} etapas, {est} G",
          dt == 3 + 2 * c + 2 and prep == 8 * c and est == 10 * c and prep <= et * 12)

# 7. Grimório: nenhum feitiço repetido entre os Círculos
i = HTML.index("Círculo 1 · "); j = HTML.index("<h3", HTML.index("Círculo 4 · ") + 5)
nomes = re.findall(r"<tr><td><strong>([^<]+)</strong>", HTML[i:j])
rep = sorted({n for n in nomes if nomes.count(n) > 1})
checa(f"Grimório: {len(nomes)} feitiços, nenhum repetido {rep if rep else ''}", not rep)

# 8. Bestiário: cada ficha sai da Tábua de Perigo e do arquétipo
from fractions import Fraction
i = HTML.index("<h3>A Tábua de Perigo</h3>"); j = HTML.index("</table>", i)
TAB = {}
for row in re.findall(r"<tr>(.*?)</tr>", HTML[i:j])[1:]:
    c = re.findall(r"<td[^>]*>(.*?)</td>", row)
    TAB[int(c[0])] = (int(c[2]), int(c[3]), c[4], int(c[5][3:]), int(c[6]), int(c[7]), int(c[8]))
ARQ = {"Padrão": (Fraction(1), 0, 0, 0), "Bruto": (Fraction(13, 10), -1, -1, 0), "Ágil": (Fraction(8, 10), 2, 0, 0),
       "Predador": (Fraction(9, 10), 0, 1, 2), "Conjurador": (Fraction(8, 10), 0, 0, 0), "Enxame": (Fraction(1), 0, 0, 0),
       "Espectral": (Fraction(7, 10), 0, 0, 0), "Guardião": (Fraction(12, 10), 1, 0, 0)}
PASSOS = [4, 6, 8, 10, 12]
def passo(dados, n):
    d = [int(x) for x in dados.replace("d", "").split("+")]
    if n > 0:
        if len(d) == 3: d[2] = PASSOS[min(4, PASSOS.index(d[2]) + 1)]
        elif d[0] < 12: d[0] = PASSOS[PASSOS.index(d[0]) + 1]
        elif d[1] < 12: d[1] = PASSOS[PASSOS.index(d[1]) + 1]
        else: d.append(4)
    elif n < 0:
        if len(d) == 3: d = d[:2]
        else: d[0] = PASSOS[max(0, PASSOS.index(d[0]) - 1)]
    return "+".join("d%d" % x for x in sorted(d[:2], reverse=True) + d[2:])
erradas = []
fichas = re.findall(r'<div class="cartao ficha" id="([^"]+)" ([^>]+)>', HTML)
for fid, attrs in fichas:
    a = dict(re.findall(r'data-([a-z]+)="([^"]+)"', attrs))
    p = int(a["perigo"]); pv, df, atq, dano, dt, ntr, npo = TAB[p]; mult, ddf, dat, ddn = ARQ[a["arq"]]
    pes = int(a["pes"])
    ok = (int(a["pv"]) == int(pv * mult + Fraction(1, 2)) and int(a["def"]) == df + ddf and a["atq"] == passo(atq, dat)
          and int(a["dano"]) == dano + ddn and int(a["dt"]) == dt and int(a["ntr"]) <= ntr
          and int(a["npo"]) <= npo + (a["arq"] == "Conjurador") and pes <= (1 if p < 6 else 2)
          and int(a["ameaca"]) == p + pes + int(a["inc"]))
    if not ok: erradas.append(fid)
checa(f"Bestiário: {len(fichas)} fichas, todas pela Tábua e pelo arquétipo {erradas if erradas else ''}", fichas and not erradas)

# 9. Poções: toda receita cabe numa linha do "Criar uma poção"
FAIXAS = [(5, 7, 8, 10, 3, 3), (7, 9, 12, 14, 4, 4), (11, 11, 16, 20, 5, 6), (13, 15, 24, 32, 6, 8)]
i = HTML.index("<h3>Receitas</h3>"); j = HTML.index("<h3>Tempo, preço e limites</h3>")
rec, fora = 0, []
for l in re.findall(r"<tr>(.*?)</tr>", HTML[i:j], re.S):
    c = [re.sub(r"<[^>]+>", "", x).strip() for x in re.findall(r"<td[^>]*>(.*?)</td>", l, re.S)]
    if len(c) < 4 or not (c[1].isdigit() and c[2].isdigit() and c[3].isdigit()): continue
    dt, p, e = int(c[1]), int(c[2]), int(c[3]); rec += 1
    if not (any(a <= dt <= b and lo <= p <= hi and f <= e <= g for a, b, lo, hi, f, g in FAIXAS) and p <= e * 12): fora.append(c[0])
checa(f"Poções: {rec} receitas, todas dentro do Criar uma poção {fora if fora else ''}", rec and not fora)

# 10. Toda poção tem ingredientes e um passo de preparo por etapa; DT 9 tem ★, DT 11 tem ◆, DT 13+ tem os dois
k = HTML.index('id="modo-de-preparo"'); m = HTML.index("</table>", HTML.index("<th>Modo de preparo</th>", k))
prep = {}
for l in re.findall(r"<tr>(.*?)</tr>", HTML[k:m], re.S):
    c = re.findall(r"<td[^>]*>(.*?)</td>", l, re.S)
    if len(c) == 2: prep[re.sub(r"<[^>]+>", "", c[0]).strip()] = c[1].split("<br>")
ruins = []
for l in re.findall(r"<tr>(.*?)</tr>", HTML[i:k], re.S):
    c = [re.sub(r"<[^>]+>", "", x).strip() for x in re.findall(r"<td[^>]*>(.*?)</td>", l, re.S)]
    if len(c) != 6: continue
    ps = prep.get(re.search(r"<strong>(.*?)</strong>", l).group(1))
    if not ps or len(c[4]) < 8: ruins.append(c[0]); continue
    if not c[1].isdigit(): continue
    dt, st, lo = int(c[1]), sum("★" in p for p in ps), sum("◆" in p for p in ps)
    ok = len(ps) == int(c[3]) and ((dt <= 7 and not st and not lo) or (dt == 9 and st == 1 and not lo) or (dt == 11 and lo) or (dt >= 13 and lo and st))
    if not ok: ruins.append(c[0])
checa(f"Poções: {len(prep)} com modo de preparo, passos = etapas, minigame onde a DT pede {ruins if ruins else ''}", len(prep) > rec and not ruins)

# 11. Itens mágicos: todo item tem categoria válida, preço e regra na mesa
k = HTML.index('class="indice"', HTML.index('id="itens"')); m = HTML.index("<h3>Preços</h3>", k)
itens, ruins = 0, []
for l in re.findall(r"<tr>(.*?)</tr>", HTML[k:m], re.S):
    c = [re.sub(r"<[^>]+>", "", x).strip() for x in re.findall(r"<td[^>]*>(.*?)</td>", l, re.S)]
    if not c: continue
    itens += 1
    if len(c) != 4 or c[1] not in ("I", "II", "III", "IV", "Único") or not c[2] or len(c[3]) < 15: ruins.append(c[0])
checa(f"Itens: {itens} com categoria, preço e regra {ruins if ruins else ''}", itens >= 100 and not ruins)

# 12. Itens deste jogo: preço dentro da categoria, limite de uso, nada de ação extra nem +2 passos
NOVOS = ("roupas", "estudo", "consumiveis", "duelo", "exploracao", "casa", "poder")
FAIXA = {"I": (0, 5), "II": (5, 100), "III": (100, 500), "IV": (500, 10**6)}
LIMITE = re.compile(r"por cena|por sessão|por dia|por semana|por (um )?mês|por poção|por duelo|uso único|uma carga|uma vez", re.I)
def galeoes(p):
    m = re.search(r"([\d.]+)\s*(galeões|galeão|sicles|sicle|nuques|nuque)", p)
    if not m: return None
    return float(m.group(1).replace(".", "")) / {"galeõ": 1, "galeã": 1, "sicle": 17, "nuque": 493}[m.group(2)[:5]]
nov, uni, ruins = 0, 0, []
for g in NOVOS:
    a = HTML.index(f'id="itens-{g}"'); b = HTML.index("</table>", a)
    for l in re.findall(r"<tr>(.*?)</tr>", HTML[a:b], re.S):
        c = [re.sub(r"<[^>]+>", "", x).strip() for x in re.findall(r"<td[^>]*>(.*?)</td>", l, re.S)]
        if not c: continue
        nov += 1; uni += "✦" in c[0]
        cat, preco, ef = c[1], c[2], c[3]
        v = galeoes(preco); lo, hi = FAIXA[cat]
        ok = (v is None and cat == "IV" and "não se vende" in preco) or (v is not None and lo <= v <= hi)
        mexe = re.search(r"PV|DET|Preso|Atordoad|Amedrontad|Desesperad|Silenciad", ef)
        if ("+1 passo" in ef or cat in ("III", "IV") or (mexe and cat == "I")) and not LIMITE.search(ef): ok = False
        if "+2 passos" in ef or "ação extra" in ef or ("dado extra" in ef and cat != "IV") or (cat == "IV" and "Preço:" not in ef): ok = False
        if not ok: ruins.append(c[0])
checa(f"Itens deste jogo: {nov} pela Tábua de valor, {uni} com mecânica própria {ruins if ruins else ''}", nov == 100 and uni >= 60 and not ruins)

# 13. Varinhas: toda madeira com afinidade; comprimento e flexibilidade cobrem o d6
a = HTML.index('id="a-varinha"'); b = HTML.index('id="cuidar-varinha"')
V = HTML[a:b]
def cobre(tit):
    s = V[V.index(tit):]; s = s[:s.index("</table>")]
    n = set()
    for d in re.findall(r'<td class="d">([\d–]+)</td>', s):
        x = d.split("–"); n |= set(range(int(x[0]), int(x[-1]) + 1))
    return n == set(range(1, 7))
s = V[V.index('id="madeiras"'):]; s = s[:s.index("</table>")]
rows = [re.findall(r"<td[^>]*>(.*?)</td>", l, re.S) for l in re.findall(r"<tr>(.*?)</tr>", s, re.S)]
rows = [c for c in rows if len(c) == 3 and re.sub(r"<[^>]+>", "", c[1]).strip()]
d12 = len(re.findall(r'<td class="d">\d+</td><td>[^<]+</td><td>', V[:V.index("Núcleo")]))
checa(f"Varinhas: {d12 + len(rows)} madeiras com afinidade, comprimento e flexibilidade cobrem o d6", d12 == 12 and len(rows) == 29 and cobre("<th>Comprimento</th>") and cobre("<th>Flexibilidade</th>"))

# 14. Núcleos: todo núcleo tem efeito e lealdade; o d6 cobre 1 a 6
nuc, ruins = 0, []
for tit in ("<th>d6</th><th>Núcleo</th>", "<th>Outro núcleo</th>"):
    s = V[V.index(tit):]; s = s[:s.index("</table>")]
    for l in re.findall(r"<tr>(.*?)</tr>", s, re.S):
        c = [re.sub(r"<[^>]+>", "", x).strip() for x in re.findall(r"<td[^>]*>(.*?)</td>", l, re.S)]
        if not c: continue
        nuc += 1
        if len(c) != 4 or not c[2] or not c[3]: ruins.append(c[1] if len(c) > 1 else c[0])
nuc -= 1  # a linha "Outro núcleo" do d6 só manda para a tabela
checa(f"Núcleos: {nuc}, todos com efeito e lealdade {ruins if ruins else ''}", nuc >= 20 and not ruins and cobre("<th>d6</th><th>Núcleo</th>"))

# 15. Vassouras: ficha válida e todo traço definido
a = HTML.index('id="vassouras"'); b = HTML.index("<h3>Fabricar um objeto encantado</h3>", a)
S = HTML[a:b]
def nomes(tit):
    s = S[S.index(tit):]; s = s[:s.index("</table>")]
    return set(re.findall(r"<tr><td><strong>([^<]+)</strong>", s))
tracos = nomes("<th>Vantagem</th>") | nomes("<th>Desvantagem</th>")
s = S[S.index('id="modelos-vassoura"'):]; s = s[:s.index("</table>")]
vas, ruins = 0, []
for l in re.findall(r"<tr><td>(.*?)</tr>", s, re.S):
    c = [re.sub(r"<[^>]+>", "", x).strip() for x in re.findall(r"<td[^>]*>(.*?)</td>", "<td>" + l, re.S)]
    vas += 1
    ok = len(c) == 8 and c[2].isdigit() and 0 <= int(c[2]) <= 5 and c[3] in ("–1", "0", "+1") and c[4] in ("–1", "0", "+1")
    for tr in (c[5].split(", ") + c[6].split(", ")) if ok else []:
        if tr != "—" and tr not in tracos: ok = False
    if not ok: ruins.append(c[0])
checa(f"Vassouras: {vas} modelos, ficha válida e traços definidos {ruins if ruins else ''}", vas >= 30 and not ruins)

# 16. Animais de estimação: os três da carta são Permitidos; toda habilidade tem limite
a = HTML.index('id="animais"'); b = HTML.index('id="cuidados"', a)
S = HTML[a:b]; s = S[S.index("<th>Laço 2</th>"):]; s = s[:s.index("</table>")]
ani, ruins, perm = 0, [], set()
for l in re.findall(r"<tr><td>(.*?)</tr>", s, re.S):
    c = [re.sub(r"<[^>]+>", "", x).strip() for x in re.findall(r"<td[^>]*>(.*?)</td>", "<td>" + l, re.S)]
    ani += 1
    if c[2] == "Permitido": perm.add(c[0])
    lim = r"por cena|por sessão|por dia|por noite|por semana|por perseguição|por campanha|uma rodada|nunca|ninguém|volta para casa"
    if len(c) != 6 or c[2] not in ("Permitido", "Tolerado", "Proibido") or not re.search(lim, c[3]) or not c[4] or not c[5]: ruins.append(c[0])
cor = S.count("<tr><td><strong>") - ani - 3
checa(f"Animais: {ani} e {cor} corujas, habilidade com limite e Laço 2 {ruins if ruins else ''}", ani >= 15 and cor >= 5 and {"Gato", "Sapo"} <= perm and not ruins)

# 17. Forja de Bruxos: toda ficha sai da Tábua + Papel; feitiços existem e cabem no Círculo do Nível
a = HTML.index("<h3>A Tábua de Perigo</h3>"); b = HTML.index("</table>", a)
TABUA = {}
for l in re.findall(r"<tr>(.*?)</tr>", HTML[a:b], re.S)[1:]:
    c = re.findall(r"<td[^>]*>(.*?)</td>", l)
    TABUA[int(c[0])] = dict(pv=int(c[2]), df=int(c[3]), atq=c[4], dano=int(c[5][3:]), dt=int(c[6]), ntr=int(c[7]), npo=int(c[8]))
CIRC = {}
for k, (ini, fim) in enumerate([("Círculo 1 ·", "Círculo 2 ·"), ("Círculo 2 ·", "Círculo 3 ·"), ("Círculo 3 ·", "Círculo 4 ·"), ("Círculo 4 ·", "<h3>Proibidos</h3>"), ("<h3>Proibidos</h3>", "</section>")], 1):
    a = HTML.index(ini); b = HTML.index(fim, a + 1)
    for n in re.findall(r"<tr><td><strong>(.*?)</strong>", HTML[a:b]): CIRC.setdefault(n, k)
CMAX = {1: 1, 2: 1, 3: 2, 4: 2, 5: 3, 6: 3, 7: 3, 8: 4, 9: 4, 10: 4, 11: 4}
DETN = {n: 3 + n for n in range(1, 12)}
PAP = {"Duelista": (1, 0, 1, 0), "Curandeiro": (1, 0, 0, -3), "Erudito": (.8, 0, 0, 0), "Batedor": (1, 2, 0, 0), "Protetor": (1.3, 0, -1, 0),
       "Trapaceiro": (1, 1, 0, 0), "Domador": (1, 0, 0, -2), "Comandante": (1, 0, 0, 0), "Trevoso": (.9, 0, 0, 2), "Caçador": (1.1, 1, 0, 0),
       "Brutamontes": (1.2, -1, 0, 1), "Mentor": (1, 0, 0, -2)}
def passo_atq(dados, n):
    d = [int(x) for x in dados.replace("d", "").split("+")]; P = [4, 6, 8, 10, 12]
    if n > 0:
        if len(d) == 3: d[2] = P[min(4, P.index(d[2]) + 1)]
        elif d[0] < 12: d[0] = P[P.index(d[0]) + 1]
        elif d[1] < 12: d[1] = P[P.index(d[1]) + 1]
        else: d.append(4)
    elif n < 0:
        if len(d) == 3: d = d[:2]
        else: d[0] = P[max(0, P.index(d[0]) - 1)]
    return "+".join("d%d" % x for x in sorted(d[:2], reverse=True) + d[2:])
bx, ruins = 0, []
for attrs in re.findall(r'<div class="cartao bruxo"([^>]*)>', HTML):
    bx += 1; A = dict(re.findall(r'data-([a-z]+)="([^"]*)"', attrs)); n = int(A["nivel"]); T = TABUA[n]; m, ddf, dat, ddn = PAP[A["papel"]]
    fe = A["feiticos"].split("|"); fora = [x for x in fe if CIRC.get(x, 99) > CMAX[n]]
    ok = (int(A["pv"]) == int(T["pv"] * m + .5) and int(A["def"]) == T["df"] + ddf and A["atq"] == passo_atq(T["atq"], dat)
          and int(A["dano"]) == T["dano"] + ddn and int(A["dt"]) == T["dt"] and int(A["det"]) == DETN[n]
          and int(A["ntr"]) <= T["ntr"] and int(A["npo"]) <= T["npo"] and int(A["pes"]) <= (1 if n < 6 else 2)
          and int(A["ameaca"]) == n + int(A["pes"]) + int(A["inc"]) + int(A["duplo"])
          and all(x in CIRC for x in fe) and len(fora) <= (1 if A["papel"] == "Trevoso" else 0)
          and all(CIRC[x] == 5 or x in ("Crucio", "Imperio") for x in fora))
    po = A.get("poderes", "").split("|")
    # regressão: Protego só do Grau 3; Imperdoável de Poder só Grau 8+ ou Trevoso 6+; reforço Grau 4+; Domador Grau 3+
    ok = ok and ("Protego" not in fe or n >= 3)
    ok = ok and all(n >= 8 or (A["papel"] == "Trevoso" and n >= 6) for x in po if x in ("Crucio", "Imperio"))
    ok = ok and all(x in fe for x in po if x in ("Crucio", "Imperio"))
    ok = ok and ("Chamar reforço" not in po or n >= 4) and (A["papel"] != "Domador" or n >= 3)
    ok = ok and ("Ataque duplo" not in po or n >= 8)
    ok = ok and ("Vulnera Sanentur" not in fe or A["papel"] in ("Mentor", "Erudito"))  # inventado por Snape: só quem teve a fonte
    if not ok: ruins.append(A["papel"] + str(n))
# fichas por inteiro: Protego do texto bate com o Grau e o Papel; feitiço assinatura nos dados e fora da contagem
prot, assin = [], 0
for attrs, corpo in re.findall(r'<div class="cartao bruxo"([^>]*)>(.*?)\n  </div>', HTML, re.S):
    A = dict(re.findall(r'data-([a-z]+)="([^"]*)"', attrs)); n = int(A["nivel"]); fe = A["feiticos"].split("|")
    if "Protego" in fe:
        quer = "1 por rodada" if n >= 5 or (A["papel"] == "Duelista" and n >= 3) else "1 por cena"
        if "<b>Protego</b> " + quer not in corpo: prot.append(A["papel"] + str(n))
    if "Feitiço assinatura" in A.get("poderes", ""):
        nome = A.get("assinatura", "")
        if not nome or nome in fe or "<strong>" + nome + "</strong>" not in corpo: prot.append("assinatura " + A["papel"])
        else: assin += 1
checa(f"Forja de Bruxos: Protego da ficha = Grau + Papel; {assin} feitiço(s) assinatura em data-assinatura {prot if prot else ''}", not prot and assin >= 1)

# queda: 1d6 a cada 3 m, somados (médias do livro)
from itertools import product
med = lambda k: sum(sum(r) for r in product(range(1, 7), repeat=k)) / 6 ** k
checa("queda: médias 3,5 / 10,5 / 21 (1, 3 e 6 dados somados)", (med(1), med(3), med(6)) == (3.5, 10.5, 21.0) and "3 m, 3,5; 9 m, 10,5; 18 m, 21" in HTML)

a = HTML.index('id="forja-bruxos"'); b = HTML.index('id="aliados"', a); S = HTML[a:b]
checa("Forja de Bruxos: Protego só do Grau 3, reforço Grau 4+, Domador Grau 3+, nada abaixo de 1",
      "— (só Desviar)" in S and "Grau 4+. Patrono" in S and "Só Grau 3+. Tem uma criatura" in S and "(mínimo 1)" in S and "Nível" not in re.sub(r"Nível dos personagens|o Nível \(1|um aluno de Nível 6", "", S))
checa(f"Forja de Bruxos: {bx} fichas batem com Tábua + Papel, feitiços no Círculo {ruins if ruins else ''}", bx >= 10 and not ruins)

# 18. Banco de dados: dados/*.json é a fonte; o livro gerado tem de estar em dia com ele
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import dados as banco
TB, GR, PA, AR = banco.tabua(), banco.graus(), banco.papeis(), banco.arquetipos()
FE = banco.feiticos(); NOMES_FE = {x["nome"]: x for x in FE}
ruins = [x["nome"] for x in FE if x["tipo"] not in ("Utilidade", "Ataque", "Efeito") or x["funcao"] not in banco.FUNCOES
         or x["circulo"] not in banco.CIRCULOS or (x["tipo"] != banco.tipo_pela_regra(x) and not x.get("tipo_motivo"))]
rep = sorted({x["nome"] for x in FE if [y["nome"] for y in FE].count(x["nome"]) > 1})
checa(f"Banco: {len(FE)} feitiços com Tipo e Função válidos; o tipo só foge da regra com motivo escrito {ruins + rep if ruins or rep else ''}", not ruins and not rep)
lin = [x for x in FE if '<td>%s</td><td>%s</td>' % (x["tipo"], x["efeito"]) not in HTML]
checa(f"Banco: Grimório do livro em dia com dados/feiticos.json {[x['nome'] for x in lin][:5] if lin else ''}", not lin)
CR = banco.criaturas()
ruins = [c["id"] for c in CR if c["perigo"] not in TB or c["arq"] not in AR or c["ntr"] > TB[c["perigo"]]["tracos"]
         or c["npo"] > TB[c["perigo"]]["poderes"] + AR[c["arq"]]["poderes_extra"] or c["pes"] > (1 if c["perigo"] < 6 else 2)
         or 'id="%s" data-perigo="%d" data-arq="%s" data-pv="%d" data-def="%d"' % (c["id"], c["perigo"], c["arq"], c["pv"], c["defesa"]) not in HTML]
checa(f"Banco: {len(CR)} criaturas pela Tábua e pelo arquétipo, e o livro em dia {ruins if ruins else ''}", len(CR) >= 90 and not ruins)
BX = banco.bruxos(); ruins = []
for b in BX:
    fora = [x for x in b["feiticos"] if x not in NOMES_FE]
    acima = [x for x in b["feiticos"] if x in NOMES_FE and NOMES_FE[x]["circulo"] > GR[b["grau"]]["circulo"]]
    ok = (not fora and len(acima) <= (1 if b["papel"] == "Trevoso" else 0) and b["papel"] in PA
          and b.get("assinatura", "") not in NOMES_FE and b.get("assinatura", "") not in b["feiticos"]
          and ("Feitiço assinatura" in b["poderes"]) == bool(b.get("assinatura"))
          and 'id="%s" data-nivel="%d" data-papel="%s" data-pv="%d"' % (b["id"], b["grau"], b["papel"], b["pv"]) in HTML)
    if not ok: ruins.append(b["id"] + str(fora + acima))
checa(f"Banco: {len(BX)} bruxos com feitiços do Grimório no Círculo do Grau, assinatura fora da lista, livro em dia {ruins if ruins else ''}", len(BX) >= 10 and not ruins)
IT = banco.carrega("itens")
ruins = [i["nome"] for i in IT if i["cat"] not in ("I", "II", "III", "IV", "V", "Único") or not i["regra"]
         or (i["preco"] in ("", "—") and i["cat"] not in ("IV", "Único")) or (i["cat"] == "Único" and i["preco"] != "—")]
checa(f"Banco: {len(IT)} itens com categoria e regra; sem preço só Artefato (IV) e Único {ruins[:5] if ruins else ''}", len(IT) >= 200 and not ruins)
CO = banco.carrega("condicoes")
checa(f"Banco: {len(CO)} condições, {sum('rapida' in c for c in CO)} na referência rápida, todas com efeito e saída",
      all(c["efeito"] and c["duracao"] for c in CO) and sum("rapida" in c for c in CO) >= 8)
checa("Banco: nenhum marcador <!--dados:...--> sobrando no livro", "<!--dados:" not in HTML)
checa("Nenhum pedaço de código do build vazou para o texto", "' + d(" not in HTML and "'''" not in HTML)

print(f"\n{len(falhas)} falha(s). Isto confere contas, não substitui teste de mesa.")
sys.exit(1 if falhas else 0)
