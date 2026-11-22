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
    "Maxima: falha sai o feitiço comum": "sai o feitiço comum, não o Maxima",
    "Tempestade de fogo não é fogo das trevas": "Não é fogo das trevas",
    "Fulgur Caeli: nome do jogo, só Mestre": "Só um bruxo Mestre",
    "materiais: achar não dá direito de ferir": "Achar uma criatura não dá direito de machucá-la",
    "materiais: fonte esgotada não rende": "Fonte esgotada não rende de novo",
    "materiais: preparados não se somam": "três doses não dão +3 passos",
    "objetos: três ativos": "no máximo três objetos encantados",
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

print(f"\n{len(falhas)} falha(s). Isto confere contas, não substitui teste de mesa.")
sys.exit(1 if falhas else 0)
