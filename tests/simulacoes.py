#!/usr/bin/env python3
"""Simulações de Varinhas e Segredos (Monte Carlo com semente fixa, sem dependências).

Execute: python build.py && python tests/simulacoes.py [poções|quadribol|combate|bruxos|evolução]
Confere poções (três abordagens), duração do Quadribol, duração e risco dos combates e os sete anos de PE.
Os modelos simplificam o que só a mesa decide (táticas, poderes, cenário): servem para achar
números fora do lugar, não para provar equilíbrio.
"""
import pathlib, random, re, sys
from collections import Counter

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import dados as banco  # o banco: dados/*.json

HTML = (pathlib.Path(__file__).resolve().parent.parent / "index.html").read_text(encoding="utf-8")
rnd = random.Random(1504)
DADOS = (4, 6, 8, 10, 12)
N = 20000


def passo(d, k):
    """Sobe ou desce k passos. Retorna (dado, ajuste de DT) pelo piso do d4."""
    i = DADOS.index(d) + k
    if i < 0:
        return 4, -2 * i
    return DADOS[min(i, 4)], 0


def rola(dados, dt):
    """Teste normal: soma os 3 maiores; crítico só se a DT é alcançável. Retorna (total, ok, crit, desastre, faces)."""
    f = sorted((rnd.randint(1, d) for d in dados), reverse=True)
    top = f[:3]
    total = sum(top)
    altos = [x for x in top if x >= 4]
    crit = sum(sorted(dados, reverse=True)[:3]) >= dt and (len(set(altos)) < len(altos) or total >= dt + 6)
    desastre = all(x == 1 for x in f)
    return total, (not desastre) and (crit or total >= dt), crit and not desastre, desastre, top


# ---------------------------------------------------------------- poções
def receitas():
    i = HTML.index("<h3>Receitas</h3>")
    j = HTML.index("</table>", i)
    out = []
    for l in re.findall(r"<tr>(.*?)</tr>", HTML[i:j], re.S)[1:]:
        c = [re.sub(r"<[^>]+>", "", x).strip() for x in re.findall(r"<td[^>]*>(.*?)</td>", l, re.S)]
        try:
            out.append((c[0].replace(" J", "").strip(), int(c[1]), int(c[2]), int(c[3])))
        except (ValueError, IndexError):
            pass
    return out


VOLATEIS = ("Polissuco", "Felix", "Mata-Cão", "Morto-Vivo")


def pocao(mente, pocoes, dt, preparo, etapas, volatil, estilo, mao_firme=False, excelentes=0):
    limite = 4 if volatil else 5
    prep = inst = 0
    primeira = True
    for e in range(etapas):
        est = estilo
        if estilo == "adaptativa":  # arrisca só quando precisa e pode
            falta = preparo - prep
            restam = etapas - e
            est = "arriscada" if (falta > restam * (pocoes + 1) / 2 and inst <= limite - 3) else ("cuidadosa" if inst >= limite - 2 else "normal")
        k = {"cuidadosa": -1, "normal": 0, "arriscada": 1}[est]
        d, extra = passo(pocoes, k)
        total, ok, crit, desastre, top = rola((mente, d), dt + extra)
        if desastre:
            inst += 3
        elif crit:
            prep += sum(top[:2]); inst = max(0, inst - 1)
        elif ok:
            prep += top[0]
        else:
            prep += top[-1]
            ganho = 0 if est == "cuidadosa" else (2 if est == "arriscada" else 1)
            if mao_firme and primeira:
                ganho = 0
            primeira = False
            inst += ganho
        if inst >= limite:
            return "explodiu"
        if prep >= preparo:
            inst = max(0, inst - excelentes)
            return "Excelente" if inst == 0 else ("Boa" if inst <= 2 else "Instável")
    return "estragou"


def sim_pocoes():
    print("POÇÕES — % de poção utilizável (Boa ou Excelente) / % explosão, Mente d8")
    rs = receitas()
    grupos = {}
    for nome, dt, prep, et in rs:
        grupos.setdefault((dt, prep, et, any(v in nome for v in VOLATEIS)), []).append(nome)
    estilos = ("cuidadosa", "normal", "arriscada", "adaptativa")
    resumo = Counter()
    for (dt, prep, et, vol), nomes in sorted(grupos.items()):
        print(f"\n  DT {dt}, Preparo {prep}, {et} etapas{' (volátil)' if vol else ''}: {', '.join(nomes)[:70]}")
        for p in DADOS:
            linha = []
            melhor = None
            for est in estilos:
                c = Counter(pocao(8, p, dt, prep, et, vol, est) for _ in range(4000))
                boa = (c["Boa"] + c["Excelente"]) / 4000
                linha.append(f"{est[:4]} {boa*100:3.0f}/{c['explodiu']/40:2.0f}")
                if est != "adaptativa" and (melhor is None or boa > melhor[1] + 0.02):
                    melhor = (est, boa)
                elif est != "adaptativa" and melhor and abs(boa - melhor[1]) <= 0.02:
                    melhor = ("empate", boa)
            resumo[melhor[0]] += 1
            print(f"    Poções d{p:<2}: " + "  ".join(linha))
    print("\n  Qual abordagem fixa é a melhor em cada combinação (±2 pontos = empate):", dict(resumo))
    return resumo


# ---------------------------------------------------------------- quadribol
def sim_quadribol(n=N, mano=0, vel=0, quieto=False):
    """mano: passo de Manobra da vassoura do apanhador 0 (todo teste de Voo dele);
    vel: +1 passo no pomo disputado se a Velocidade dele é 2+ maior. Tudo no limite de +2."""
    dur = []
    pomo_decide = 0
    vitorias = 0
    for _ in range(n):
        pistas = [0, 0]
        apanhador = [(8, passo(8, min(2, mano))[0]), (8, 6)]  # jogador Corpo/Mente d8 + perícia d8 (± vassoura); time do Mestre Médio
        disputa0 = (8, passo(8, min(2, mano + vel))[0])
        placar = [0, 0]
        lance = 0
        while True:
            lance += 1
            # goles: posse, oportunidade, finalização (time médio contra time médio)
            a = 0 if sum(rnd.randint(1, d) for d in (8, 6)) >= sum(rnd.randint(1, d) for d in (8, 6)) else 1
            if rola((8, 6), 7)[1]:
                acertou = rnd.random() < 1 / 3
                g, _ = passo(6, 1 if acertou else -1)
                if rola((8, 6), 0)[0] >= rola((8, g), 0)[0]:
                    placar[a] += 10
            # apanhadores
            mergulho = [i for i in (0, 1) if pistas[i] >= 4]
            if mergulho:
                i = mergulho[0]; o = 1 - i
                if pistas[o] >= 2:
                    pi = rola(disputa0 if i == 0 else apanhador[i], 9)[0]
                    d, _ = passo(apanhador[o][1], -1 if pistas[o] < pistas[i] else 0)
                    po = rola((apanhador[o][0], d), 9)[0]
                    if pi == po:
                        pistas = [2, 2]
                    elif max(pi, po) >= 9:
                        placar[i if pi > po else o] += 150; break
                    else:
                        pistas[i] = 1
                else:
                    if rola(apanhador[i], 9)[1]:
                        placar[i] += 150; break
                    pistas[i] = 1
            for i in (0, 1):
                if pistas[i] < 4 and not (mergulho and i in mergulho):
                    _, ok, crit, _, _ = rola(apanhador[i], 9)
                    pistas[i] = min(4, pistas[i] + (2 if crit else 1 if ok else 0))
            if lance > 60:
                break
        dur.append(lance)
        venc = 0 if placar[0] > placar[1] else 1
        vitorias += venc == 0
        sem_pomo = [placar[k] - (150 if placar[k] >= 150 else 0) for k in (0, 1)]
        if (sem_pomo[0] > sem_pomo[1]) != (venc == 0) and sem_pomo[0] != sem_pomo[1]:
            pomo_decide += 1
    dur.sort()
    faixa = sum(6 <= x <= 15 for x in dur) / n
    if quieto:
        return vitorias / n
    print(f"QUADRIBOL — lances por partida: mediana {dur[n//2]}, 10% {dur[n//10]}, 90% {dur[9*n//10]}; "
          f"entre 6 e 15 lances: {faixa*100:.0f}%; o pomo vira o resultado em {pomo_decide/n*100:.0f}% das partidas")
    return dur[n // 2], faixa


# ---------------------------------------------------------------- combate
# a Tábua de Perigo vem do banco (dados/tabua.json): (PV, Defesa, dados de Ataque, Dano)
TABUA = {p: (l["pv"], l["defesa"], tuple(int(x) for x in l["ataque"].replace("d", "").split("+")), l["dano"]) for p, l in banco.tabua().items()}
# aluno típico ao longo do ano (Mente, Feitiços, Corpo, Reflexos); ataque: (Círculo, mod de dano)
ALUNO = {1: (8, 6, 6, 6, (1, 0)), 2: (8, 6, 6, 6, (2, 2)), 3: (8, 8, 6, 8, (2, 2)), 4: (8, 8, 8, 8, (2, 2)),
         5: (10, 10, 8, 8, (2, 2)), 6: (10, 10, 8, 10, (3, 3)), 7: (10, 12, 10, 10, (3, 3))}


def combate(ano, inimigos, tipo="comum", n_alunos=4, chefe_pv=1.5, chefe_acoes=2):
    """tipo: comum (sem chefe), chefe_sozinho (Fases, PV x1,5, duas ações), chefe_acompanhado (só Fases)."""
    m, f, c, r, (circ, mod) = ALUNO[ano]
    pv_max = 8 + c + 3 * (ano - 1)
    defesa = 5 + r // 2
    reacao = (m, f) if ano >= 5 else (c, r)  # Protego chega no 5º ano
    alunos = [pv_max] * n_alunos
    # com chefe, ele é o primeiro inimigo: Fases da Tábua; o golpe que quebra uma Fase para no piso dela
    fases = {1: 1, 2: 2, 3: 3, 4: 3, 5: 3, 6: 3, 7: 3, 8: 4, 9: 4, 10: 4, 11: 4}
    sozinho = tipo == "chefe_sozinho" and len(inimigos) == 1 and n_alunos >= 3
    inim = [[TABUA[p][0] * (chefe_pv if (k == 0 and sozinho) else 1), p, k == 0 and tipo != "comum"] for k, p in enumerate(inimigos)]
    for x in inim:
        x[0] = int(x[0])
        x.append(x[0])
    rodada = 0
    while rodada < 30:
        rodada += 1
        for i in range(n_alunos):
            vivos = [x for x in inim if x[0] > 0]
            if alunos[i] <= 0 or not vivos:
                continue
            alvo = min(vivos, key=lambda x: x[0])
            dt = max(3 + 2 * circ, TABUA[alvo[1]][1])  # DT do Círculo: 5, 7, 9, 11
            total, ok, crit, _, top = rola((m, f), dt)
            if ok:
                dano = (sum(top[:2]) if crit else top[0]) + mod
                if alvo[2]:
                    bloco = alvo[3] / fases[alvo[1]]
                    piso = (int((alvo[0] - 1) // bloco)) * bloco
                    alvo[0] = max(alvo[0] - dano, piso if alvo[0] > piso else alvo[0] - dano)
                else:
                    alvo[0] -= dano
        if all(x[0] <= 0 for x in inim):
            return rodada, sum(a <= 0 for a in alunos)
        for x in [y for y in inim for _ in range(chefe_acoes if (y[2] and sozinho) else 1)]:
            if x[0] <= 0:
                continue
            de_pe = [i for i in range(n_alunos) if alunos[i] > 0]
            if not de_pe:
                break
            i = rnd.choice(de_pe)
            pv, dfx, dados, dmod = TABUA[x[1]]
            total, ok, crit, _, top = rola(dados, defesa)
            if not ok:
                continue
            dano = (sum(top[:2]) if crit else top[0]) + dmod
            rt = rola(reacao, 0)[0]
            if rt >= total:
                dano = 0
            elif rt >= total - 2:
                dano //= 2
            alunos[i] -= dano
        if all(a <= 0 for a in alunos):
            return rodada, n_alunos
    return rodada, sum(a <= 0 for a in alunos)


def sim_combate(n=1500):
    print("COMBATE — 4 alunos típicos, focando o inimigo mais fraco; sem poderes, poções nem Ímpeto")
    print("  (rodadas medianas | % de lutas com alguém caído | % de grupo inteiro caído)")
    res = {}
    for ano in range(1, 8):
        casos = {
            "comum (Perigo = ano)": ([ano], "comum"),
            "chefe sozinho (ano + 1)": ([ano + 1], "chefe_sozinho"),
            "difícil (chefe + 2 capangas)": ([ano + 1, max(1, ano - 2), max(1, ano - 2)], "chefe_acompanhado"),
        }
        if ano >= 3:
            casos["muito acima (ano + 4, sozinho)"] = ([min(11, ano + 4)], "chefe_sozinho")
        for nome, (ins, tipo) in casos.items():
            rs = [combate(ano, ins, tipo) for _ in range(n)]
            rods = sorted(x[0] for x in rs)
            caiu = sum(x[1] > 0 for x in rs) / n
            tpk = sum(x[1] == 4 for x in rs) / n
            res[(ano, nome)] = (rods[n // 2], caiu, tpk)
            print(f"  {ano}º ano, {nome:32}: {rods[n//2]:2} rodadas | {caiu*100:3.0f}% | {tpk*100:3.0f}%")
    return res



# ---------------------------------------------------------------- bruxos (Forja de Bruxos)
def fichas_bruxos():
    """As dez fichas prontas, derivadas do banco (dados/bruxos.json + Tábua + Papel), as mesmas do livro."""
    return [(b["nome"], b["grau"], b["papel"], b["pv"], b["defesa"], tuple(int(x) for x in b["ataque"].replace("d", "").split("+")),
             b["dano"], b["ameaca"], b["poderes"]) for b in banco.bruxos()]


def luta_bruxo(ano, bruxo, aliado=None, n_alunos=4, chefe=False):
    """4 alunos contra um bruxo da Forja; aliado opcional ataca uma vez por rodada com a Tábua dele.
    O ajuste de chefe sozinho (PV × 1,5 e duas ações) só vale com chefe=True, sem aliado e contra 3 ou mais."""
    m, f, c, r, (circ, mod) = ALUNO[ano]
    pv_max = 8 + c + 3 * (ano - 1); defesa = 5 + r // 2
    reacao = (m, f) if ano >= 5 else (c, r)
    alunos = [pv_max] * n_alunos
    _, grau, _, pv, dfx, dados, dmod, _, _ = bruxo
    chefe_sozinho = chefe and aliado is None and n_alunos >= 3
    if chefe_sozinho:
        pv = (pv * 3 + 1) // 2  # 1,5 ×, para cima
    acoes = 2 if chefe_sozinho else 1
    for rodada in range(1, 31):
        for i in range(n_alunos):
            if alunos[i] > 0 and pv > 0:
                total, ok, crit, _, top = rola((m, f), max(3 + 2 * circ, dfx))
                if ok: pv -= (sum(top[:2]) if crit else top[0]) + mod
        if aliado and pv > 0:
            total, ok, crit, _, top = rola(aliado[5], dfx)
            if ok: pv -= (sum(top[:2]) if crit else top[0]) + aliado[6]
        if pv <= 0:
            return rodada, sum(a <= 0 for a in alunos)
        for _ in range(acoes):  # chefe sozinho: a segunda é a ação extra
            de_pe = [i for i in range(n_alunos) if alunos[i] > 0]
            if not de_pe: break
            i = rnd.choice(de_pe)
            total, ok, crit, _, top = rola(dados, defesa)
            if not ok: continue
            dano = (sum(top[:2]) if crit else top[0]) + dmod
            rt = rola(reacao, 0)[0]
            dano = 0 if rt >= total else dano // 2 if rt >= total - 2 else dano
            alunos[i] -= dano
        if all(a <= 0 for a in alunos):
            return rodada, n_alunos
    return 30, sum(a <= 0 for a in alunos)


def sim_bruxos(n=1500):
    print("BRUXOS — cada ficha pronta sozinha contra 4 alunos do ano em que ela é 'Justa' (Grau = ano + 1), com e sem aliado")
    print("  (rodadas medianas | % com alguém caído | % grupo inteiro caído)")
    fichas = fichas_bruxos()
    aliado = next(x for x in fichas if x[0].startswith("Monitor"))
    res = {}
    for b in fichas:
        ano = max(1, min(7, b[1] - 1))
        for com in (None, aliado):
            if com is b: continue
            rs = [luta_bruxo(ano, b, com) for _ in range(n)]  # encontro comum: sem ajuste de chefe
            rods = sorted(x[0] for x in rs); caiu = sum(x[1] > 0 for x in rs) / n; tpk = sum(x[1] == 4 for x in rs) / n
            res[(b[0], com is not None)] = (rods[n // 2], caiu, tpk)
            print(f"  {b[0][:26]:26} G{b[1]} vs {ano}º ano{' + Monitor' if com else '          '}: {rods[n//2]:2} rodadas | {caiu*100:3.0f}% | {tpk*100:3.0f}%")
    print("  chefe sozinho (PV × 1,5, duas ações), só as fichas de Grau 6+ que o livro usa como chefe:")
    for b in fichas:
        if b[1] < 6: continue
        ano = max(1, min(7, b[1] - 1))
        rs = [luta_bruxo(ano, b, chefe=True) for _ in range(n)]
        rods = sorted(x[0] for x in rs); caiu = sum(x[1] > 0 for x in rs) / n; tpk = sum(x[1] == 4 for x in rs) / n
        res[(b[0], "chefe")] = (rods[n // 2], caiu, tpk)
        print(f"  {b[0][:26]:26} G{b[1]} vs {ano}º ano (chefe)  : {rods[n//2]:2} rodadas | {caiu*100:3.0f}% | {tpk*100:3.0f}%")
    return res



def luta_grupo(ano, inimigos, n=1500):
    """4 alunos contra um grupo da Forja. Papel 'cura': cura o mais ferido (Ataque da Tábua vs DT 7, RA + Grau),
    no máximo 3 curas por alvo; 'comanda': dá ataque extra ao mais forte, se ele ainda não tem ação extra.
    Ataque duplo = ação extra própria. Ninguém faz mais de uma ação extra por rodada."""
    m, f, c, r, (circ, mod) = ALUNO[ano]
    pv_max = 8 + c + 3 * (ano - 1); defesa = 5 + r // 2
    reacao = (m, f) if ano >= 5 else (c, r)
    out = []; extras_max = 0
    for _ in range(n):
        alunos = [pv_max] * 4
        ini = [dict(f=b, pv=b[3], max=b[3], papel=b[2], duplo=('Ataque duplo' in b[8]), curas=0) for b in inimigos]
        fim = None
        for rodada in range(1, 31):
            for i in range(4):
                vivos = [x for x in ini if x['pv'] > 0]
                if alunos[i] > 0 and vivos:
                    alvo = min(vivos, key=lambda x: x['pv'])
                    total, ok, crit, _, top = rola((m, f), max(3 + 2 * circ, alvo['f'][4]))
                    if ok: alvo['pv'] -= (sum(top[:2]) if crit else top[0]) + mod
            if all(x['pv'] <= 0 for x in ini): fim = (rodada, sum(a <= 0 for a in alunos)); break
            extra = {id(x): (1 if x['duplo'] else 0) for x in ini}
            for x in ini:
                if x['pv'] <= 0: continue
                if x['papel'] == 'Curandeiro':
                    feridos = [y for y in ini if 0 < y['pv'] < y['max'] / 2 and y['curas'] < 3]
                    if feridos:
                        y = min(feridos, key=lambda y: y['pv'])
                        total, ok, crit, _, top = rola(x['f'][5], 7)
                        if ok: y['pv'] = min(y['max'], y['pv'] + top[0] + x['f'][1]); y['curas'] += 1
                        continue
                if x['papel'] == 'Comandante':
                    cand = [y for y in ini if y is not x and y['pv'] > 0 and extra[id(y)] == 0]
                    if cand:
                        extra[id(max(cand, key=lambda y: y['f'][6]))] = 1
                        continue
            for x in ini:
                if x['pv'] <= 0 or (x['papel'] in ('Curandeiro', 'Comandante')): continue
                for _ in range(1 + extra[id(x)]):
                    de_pe = [i for i in range(4) if alunos[i] > 0]
                    if not de_pe: break
                    i = rnd.choice(de_pe)
                    total, ok, crit, _, top = rola(x['f'][5], defesa)
                    if not ok: continue
                    dano = (sum(top[:2]) if crit else top[0]) + x['f'][6]
                    rt = rola(reacao, 0)[0]
                    alunos[i] -= 0 if rt >= total else dano // 2 if rt >= total - 2 else dano
            extras_max = max(extras_max, max(extra.values()))
            if all(a <= 0 for a in alunos): fim = (rodada, 4); break
        out.append(fim or (30, sum(a <= 0 for a in alunos)))
    rods = sorted(x[0] for x in out)
    return rods[n // 2], sum(x[1] > 0 for x in out) / n, sum(x[1] == 4 for x in out) / n, extras_max


def sim_combinacoes():
    print("FORJA — combinações (rodadas medianas | % alguém caído | % grupo caído | ação extra máx. por inimigo)")
    F = {b[0]: b for b in fichas_bruxos()}
    cmd = lambda b: b[:2] + ("Comandante",) + b[3:]
    cur = F["Curandeira do St. Mungus"]
    casos = [
        ("5º: Comensal sozinho em grupo", 5, [F["Comensal da Morte"]]),
        ("5º: Comensal + Comandante (Grau 4)", 5, [F["Comensal da Morte"], cmd(F["Sequestrador"])]),
        ("5º: Comensal + 2 Curandeiras", 5, [F["Comensal da Morte"], cur, cur]),
        ("7º: Bruxo das Trevas + Comensal", 7, [F["Bruxo das Trevas"], F["Comensal da Morte"]]),
        ("7º: Bruxo das Trevas + Comandante", 7, [F["Bruxo das Trevas"], cmd(F["Comensal da Morte"])]),
        ("7º: Bruxo das Trevas + Curandeira", 7, [F["Bruxo das Trevas"], cur]),
    ]
    res = {}
    for nome, ano, ini in casos:
        r_ = luta_grupo(ano, ini)
        res[nome] = r_
        print(f"  {nome:38}: {r_[0]:2} rodadas | {r_[1]*100:3.0f}% | {r_[2]*100:3.0f}% | {r_[3]}")
    return res

def sim_vassouras(n=4000):
    """Vassoura melhor ajuda o apanhador sem garantir a vitória (partida igual nos dois times)."""
    print("VASSOURAS NO QUADRIBOL — % de vitórias do apanhador do jogador (Voo d8) contra o do time Médio (d6), só mudando a vassoura dele")
    res = {}
    for nome, mano, vel in (("vassoura igual", 0, 0), ("Manobra −1", -1, 0), ("Manobra +1", 1, 0), ("Manobra +1 e Velocidade 2+ maior", 1, 1)):
        v = sim_quadribol(n, mano, vel, quieto=True)
        res[nome] = v
        print(f"  {nome:34}: {v*100:3.0f}%")
    return res


# ---------------------------------------------------------------- evolução
def sim_evolucao():
    print("EVOLUÇÃO — 30 PE por ano, todos gastos; nível = 1 + PE gastos ÷ 12")
    patentes = [(17, "Mestre"), (13, "Perito"), (9, "Adepto"), (5, "Aprendiz"), (1, "Iniciante")]
    out = []
    for ano in range(1, 8):
        nivel = min(20, 1 + ano * 30 // 12)
        pat = next(p for lim, p in patentes if nivel >= lim)
        out.append((ano, nivel, pat))
        print(f"  fim do {ano}º ano: nível {nivel:2}, {pat}")
    return out


if __name__ == "__main__":
    qual = sys.argv[1] if len(sys.argv) > 1 else "tudo"
    if qual in ("tudo", "evolução"): sim_evolucao(); print()
    if qual in ("tudo", "quadribol"): sim_quadribol(); print(); sim_vassouras(); print()
    if qual in ("tudo", "combate"): sim_combate(); print()
    if qual in ("tudo", "bruxos"): sim_bruxos(); print(); sim_combinacoes(); print()
    if qual in ("tudo", "poções"): sim_pocoes()
