"""O banco de dados do livro: uma fonte só para as regras que aparecem em mais de um lugar.

dados/*.json guarda o que é escolha de design (a Tábua, os Papéis, cada feitiço, cada criatura,
cada bruxo, cada item, cada condição). Este módulo deriva o resto (PV, Defesa, Ataque, Dano,
Protego, Ameaça, o tipo de resolução) e desenha as tabelas e os cartões do livro.

O build.py troca cada marcador <!--dados:...--> dos capítulos pelo HTML gerado aqui;
tests/auditoria.py e tests/simulacoes.py leem as mesmas funções. Mudou um número? Mude no JSON.
"""
import json, pathlib, re
from fractions import Fraction

RAIZ = pathlib.Path(__file__).parent
PASTA = RAIZ / "dados"
_cache = {}


def carrega(nome):
    if nome not in _cache:
        _cache[nome] = json.loads((PASTA / (nome + ".json")).read_text(encoding="utf-8"))
    return _cache[nome]


# ------------------------------------------------------------------ regras de derivação
PASSOS = [4, 6, 8, 10, 12]


def passo_ataque(dados, n):
    """Sobe ou desce o Ataque da Tábua n passos (0, +1 ou –1), como a Forja manda."""
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


def arredonda(x):
    """Meio para cima, como o livro arredonda."""
    return int(x + Fraction(1, 2))


def tabua():
    return {l["perigo"]: l for l in carrega("tabua")}


def graus():
    return {l["grau"]: l for l in carrega("graus")}


def papeis():
    return {l["nome"]: l for l in carrega("papeis")}


def arquetipos():
    return {l["nome"]: l for l in carrega("arquetipos")}


def criatura(c):
    """Ficha completa de uma criatura: Tábua do Perigo + ajuste do arquétipo."""
    T = tabua()[c["perigo"]]; A = arquetipos()[c["arq"]]
    return dict(c, pv=arredonda(T["pv"] * Fraction(A["pv"])), defesa=T["defesa"] + A["defesa"],
                ataque=passo_ataque(T["ataque"], A["ataque"]), dano=T["dano"] + A["dano"], dt=T["dt"], fases=T["fases"], ministerio=T["ministerio"],
                ameaca=c["perigo"] + c["pes"] + c["inc"])


def criaturas():
    return [criatura(c) for c in carrega("criaturas")]


def protego(grau, papel):
    if papel == "Duelista" and grau >= 3:
        return "1 por rodada <em>(Papel Duelista)</em>"
    return graus()[grau]["protego"]


def bruxo(b):
    """Ficha completa de um bruxo: Tábua do Grau + ajuste do Papel + o que o Grau sabe."""
    T = tabua()[b["grau"]]; P = papeis()[b["papel"]]; G = graus()[b["grau"]]
    return dict(b, pv=arredonda(T["pv"] * Fraction(P["pv"])), defesa=T["defesa"] + P["defesa"],
                ataque=passo_ataque(T["ataque"], P["ataque"]), dano=T["dano"] + P["dano"], dt=T["dt"],
                det=G["det"], circ=G["circulo"], protego=protego(b["grau"], b["papel"]),
                ameaca=b["grau"] + b["pes"] + b["inc"] + b["duplo"])


def bruxos():
    return [bruxo(b) for b in carrega("bruxos")]


CIRCULOS = {1: "Círculo 1", 2: "Círculo 2", 3: "Círculo 3", 4: "Círculo 4", 5: "Proibido"}
FUNCOES = ["Ofensiva", "Controle", "Defesa", "Exploração e ofício", "Cura", "Fenômeno e lenda"]


def tipo_pela_regra(f):
    """Capítulo IV, 'Como saber o tipo': dano é Ataque; sem dano e com resistência, Efeito; o resto, Utilidade.
    Cura e Imperdoáveis seguem as regras delas."""
    if f["funcao"] == "Cura": return "Utilidade"
    if re.search(r"\bRA\b", f["efeito"]) and not re.search(r"cura RA|recupera", f["efeito"]): return "Ataque"
    if f["resiste"] not in ("—", ""): return "Efeito"
    return "Utilidade"


def feiticos():
    return carrega("feiticos")


# ------------------------------------------------------------------ desenho das tabelas
def _td(attr, v):
    return "<td%s>%s</td>" % (attr, v)


def _tabela(thead, linhas, classe="compacta"):
    return ('<div class="rolagem"><table class="%s">\n  <thead><tr>%s</tr></thead>\n  <tbody>\n%s\n  </tbody></table></div>'
            % (classe, thead, "\n".join("  <tr>%s</tr>" % "".join(l) for l in linhas)))


def _nome(r):
    return "<strong>%s</strong>%s" % (r["nome"], r.get("extra", ""))


def r_tabua(_):
    th = ('<th class="num">Perigo</th><th>Ministério</th><th class="num">PV</th><th class="num">Defesa</th><th>Ataque</th>'
          '<th>Dano</th><th class="num">DT</th><th class="num">Traços</th><th class="num">Poderes</th><th class="num">Fases</th>')
    n = ' class="num"'
    return _tabela(th, [[_td(n, l["perigo"]), _td("", l["ministerio"]), _td(n, l["pv"]), _td(n, l["defesa"]), _td("", l["ataque"]),
                         _td("", "RA+%d" % l["dano"]), _td(n, l["dt"]), _td(n, l["tracos"]), _td(n, l["poderes"]), _td(n, l["fases"])]
                        for l in carrega("tabua")])


def r_arquetipos(_):
    return _tabela("<th>d8</th><th>Arquétipo</th><th>Ajuste</th><th>Exemplos</th>",
                   [[_td(' class="d"', l["d"]), _td("", _nome(l)), _td("", l["ajuste"]), _td("", l["exemplos"])] for l in carrega("arquetipos")])


def r_graus(_):
    n = ' class="num"'
    return _tabela('<th class="num">Grau</th><th>Equivale a</th><th class="num">Círculo</th><th class="num">Feitiços</th><th class="num">DET</th><th>Protego</th>',
                   [[_td(n, l["grau"]), _td("", l["equivale"]), _td(n, l["circulo"]), _td(n, l["feiticos"]), _td(n, l["det"]), _td("", l["protego"])]
                    for l in carrega("graus")])


def r_papeis(_):
    return _tabela("<th>d12</th><th>Papel</th><th>Ajuste</th><th>Habilidade</th>",
                   [[_td(' class="d"', l["d"]), _td("", _nome(l)), _td("", l["ajuste"]), _td("", l["habilidade"])] for l in carrega("papeis")],
                   "compacta papeis")


def r_bestiario(_):
    n = ' class="num"'
    return _tabela('<th>Criatura</th><th class="num">Perigo</th><th>Arquétipo</th><th class="num">PV</th><th class="num">Def</th><th class="num">Ameaça</th>',
                   [[_td("", '<a href="#%s">%s</a>' % (c["id"], c["indice"])), _td(n, c["perigo"]), _td("", c["arq"]), _td(n, c["pv"]),
                     _td(n, c["defesa"]), _td(n, c["ameaca"])] for c in sorted(criaturas(), key=lambda c: c["ordem_indice"])])


def _linhas(c):
    return "".join("\n    <p><b>%s:</b> %s</p>" % (r, v) for r, v in c["linhas"])


def r_criatura(cid):
    c = next(criatura(x) for x in carrega("criaturas") if x["id"] == cid)
    return ('<div class="cartao ficha" id="%(id)s" data-perigo="%(perigo)d" data-arq="%(arq)s" data-pv="%(pv)d" data-def="%(defesa)d" '
            'data-atq="%(ataque)s" data-dano="%(dano)d" data-dt="%(dt)d" data-ntr="%(ntr)d" data-npo="%(npo)d" data-pes="%(pes)d" '
            'data-inc="%(inc)d" data-ameaca="%(ameaca)d">\n    <h5>%(nome)s%(nota)s</h5>\n'
            '    <p class="etiqueta">Perigo %(perigo)d · %(arq)s · Ministério %(ministerio)s · Ameaça %(ameaca)d</p>\n'
            '    <p><b>PV</b> %(pv)d · <b>Defesa</b> %(defesa)d · <b>Ataque</b> %(ataque)s · <b>Dano</b> RA+%(dano)d%(dano_em)s · <b>DT</b> %(dt)d' % dict(c, dano_em=" de " + c["dano_em"] if c.get("dano_em") else "")
            + (" · Fases como chefe: %d" % c["fases"] if isinstance(c["fases"], int) else "") + "</p>"
            + _linhas(c) + "\n  </div>")


def r_bruxo(bid):
    b = next(bruxo(x) for x in carrega("bruxos") if x["id"] == bid)
    ass = ' data-assinatura="%s"' % b["assinatura"] if b.get("assinatura") else ""
    return ('<div class="cartao bruxo" id="%(id)s" data-nivel="%(grau)d" data-papel="%(papel)s" data-pv="%(pv)d" data-def="%(defesa)d" '
            'data-atq="%(ataque)s" data-dano="%(dano)d" data-dt="%(dt)d" data-det="%(det)d" data-circ="%(circ)d" data-ntr="%(ntr)d" '
            'data-npo="%(npo)d" data-pes="%(pes)d" data-inc="%(inc)d" data-duplo="%(duplo)d" data-ameaca="%(ameaca)d" ' % b
            + 'data-feiticos="%s"%s data-poderes="%s">\n' % ("|".join(b["feiticos"]), ass, "|".join(b["poderes"]))
            + '    <h5>%(nome)s%(nota)s</h5>\n    <p class="etiqueta">Grau %(grau)d · %(papel)s · %(lado)s · Ameaça %(ameaca)d</p>\n'
              '    <p><b>PV</b> %(pv)d · <b>Defesa</b> %(defesa)d · <b>Ataque</b> %(ataque)s · <b>Dano</b> RA+%(dano)d · <b>DT</b> %(dt)d · '
              '<b>DET</b> %(det)d · <b>Protego</b> %(protego)s</p>\n' % b
            + '    <p><b>Feitiços:</b> %s.</p>' % ", ".join(b["feiticos"]) + _linhas(b) + "\n  </div>")


def r_feiticos(circulo):
    c = int(circulo)
    return _tabela("<th>Feitiço</th><th>Perícia</th><th>Alcance</th><th>Resiste</th><th>Tipo</th><th>Efeito</th>",
                   [[_td("", _nome(f)), _td("", f["pericia"]), _td("", f["alcance"]), _td("", f["resiste"]), _td("", f["tipo"]), _td("", f["efeito"])]
                    for f in feiticos() if f["circulo"] == c])


def r_funcoes(_):
    """A tabela "Por função" do Capítulo V sai do campo funcao de cada feitiço."""
    return _tabela("<th>Função</th><th>Feitiços</th>",
                   [[_td("", "<strong>%s</strong>" % fn), _td("", ", ".join(f["nome"] for f in feiticos() if f["funcao"] == fn))] for fn in FUNCOES])


def r_itens(grupo):
    return _tabela("<th>Item</th><th>Cat.</th><th>Preço</th><th>Na mesa</th>",
                   [[_td("", _nome(i)), _td("", i["cat"]), _td("", i["preco"]), _td("", i["regra"])] for i in carrega("itens") if i["grupo"] == grupo])


def r_condicoes(_):
    return _tabela("<th>Condição</th><th>Efeito</th><th>Duração e saída</th>",
                   [[_td("", _nome(c)), _td("", c["efeito"]), _td("", c["duracao"])] for c in carrega("condicoes")])


def r_condicoes_rapida(_):
    cs = sorted((c for c in carrega("condicoes") if "rapida" in c), key=lambda c: c["rapida"]["ordem"])
    return _tabela("<th>Condição</th><th>Age</th><th>Move</th><th>Conjura</th><th>Reage</th><th>Sustenta</th>",
                   [[_td("", "<strong>%s</strong>%s" % (c["nome"], c["rapida"]["extra"]))] + [_td("", c["rapida"][k]) for k in ("age", "move", "conjura", "reage", "sustenta")] for c in cs])


def r_vassouras(_):
    n = ' class="num"'
    return _tabela('<th>Vassoura</th><th>Preço</th><th class="num">Vel.</th><th class="num">Man.</th><th class="num">Firm.</th><th>Vantagens</th><th>Desvantagens</th><th>Nota</th>',
                   [[_td("", _nome(v)), _td("", v["preco"]), _td(n, v["vel"]), _td(n, v["man"]), _td(n, v["firm"]),
                     _td("", v["vantagens"]), _td("", v["desvantagens"]), _td("", v["nota"])] for v in carrega("vassouras")])


DESENHOS = {"tabua": r_tabua, "arquetipos": r_arquetipos, "graus": r_graus, "papeis": r_papeis, "bestiario": r_bestiario,
            "criatura": r_criatura, "bruxo": r_bruxo, "feiticos": r_feiticos, "itens": r_itens, "condicoes": r_condicoes,
            "condicoes-rapida": r_condicoes_rapida, "vassouras": r_vassouras, "funcoes": r_funcoes}


def renderiza(html):
    """Troca cada <!--dados:nome--> ou <!--dados:nome:arg--> pelo HTML gerado."""
    def troca(m):
        return DESENHOS[m.group(1)](m.group(2))
    return re.sub(r"<!--dados:([a-z-]+)(?::([^>]*?))?-->", troca, html)
