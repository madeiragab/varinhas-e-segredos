#!/usr/bin/env python3
"""Simulações de Varinhas e Segredos (Monte Carlo com semente fixa, sem dependências).

Execute: python build.py && python tests/simulacoes.py [poções|quadribol|combate|evolução]
Confere poções (três abordagens), duração do Quadribol, duração e risco dos combates e os sete anos de PE.
Os modelos simplificam o que só a mesa decide (táticas, poderes, cenário): servem para achar
números fora do lugar, não para provar equilíbrio.
"""
import pathlib, random, re, sys
from collections import Counter

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
def sim_quadribol(n=N):
    dur = []
    pomo_decide = 0
    for _ in range(n):
        pistas = [0, 0]
        apanhador = [(8, 8), (8, 6)]  # jogador Corpo/Mente d8 + perícia d8; time do Mestre Médio
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
                    pi = rola(apanhador[i], 9)[0]
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
        sem_pomo = [placar[k] - (150 if placar[k] >= 150 else 0) for k in (0, 1)]
        if (sem_pomo[0] > sem_pomo[1]) != (venc == 0) and sem_pomo[0] != sem_pomo[1]:
            pomo_decide += 1
    dur.sort()
    faixa = sum(6 <= x <= 15 for x in dur) / n
    print(f"QUADRIBOL — lances por partida: mediana {dur[n//2]}, 10% {dur[n//10]}, 90% {dur[9*n//10]}; "
          f"entre 6 e 15 lances: {faixa*100:.0f}%; o pomo vira o resultado em {pomo_decide/n*100:.0f}% das partidas")
    return dur[n // 2], faixa


# ---------------------------------------------------------------- combate
TABUA = {1: (6, 6, (6, 4), 1), 2: (12, 7, (6, 6), 2), 3: (20, 7, (8, 6), 3), 4: (30, 8, (8, 8), 4), 5: (42, 9, (10, 8), 5),
         6: (56, 9, (10, 10), 6), 7: (72, 10, (12, 10), 7), 8: (90, 11, (12, 12), 8), 9: (110, 12, (12, 12, 8), 9),
         10: (135, 13, (12, 12, 10), 11), 11: (165, 14, (12, 12, 12), 13)}
# aluno típico ao longo do ano (Mente, Feitiços, Corpo, Reflexos); ataque: (Círculo, mod de dano)
ALUNO = {1: (8, 6, 6, 6, (1, 0)), 2: (8, 6, 6, 6, (2, 2)), 3: (8, 8, 6, 8, (2, 2)), 4: (8, 8, 8, 8, (2, 2)),
         5: (10, 10, 8, 8, (2, 2)), 6: (10, 10, 8, 10, (3, 3)), 7: (10, 12, 10, 10, (3, 3))}


def combate(ano, inimigos, n_alunos=4, chefe_pv=1.0, chefe_acoes=1):
    m, f, c, r, (circ, mod) = ALUNO[ano]
    pv_max = 8 + c + 3 * (ano - 1)
    defesa = 5 + r // 2
    reacao = (m, f) if ano >= 5 else (c, r)  # Protego chega no 5º ano
    alunos = [pv_max] * n_alunos
    # o primeiro inimigo é o chefe: Fases da Tábua; o golpe que quebra uma Fase para no piso dela
    fases = {1: 1, 2: 2, 3: 3, 4: 3, 5: 3, 6: 3, 7: 3, 8: 4, 9: 4, 10: 4, 11: 4}
    inim = [[TABUA[p][0] * (chefe_pv if k == 0 else 1), p, k == 0] for k, p in enumerate(inimigos)]
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
            dt = max(5 + 2 * circ, TABUA[alvo[1]][1])
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
        for x in [y for y in inim for _ in range(chefe_acoes if y[2] else 1)]:
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


def sim_combate(n=1500, chefe_pv=1.5, chefe_acoes=2):
    print("COMBATE — 4 alunos típicos, focando o inimigo mais fraco; sem poderes, poções nem Ímpeto")
    print("  (rodadas medianas | % de lutas com alguém caído | % de grupo inteiro caído)")
    res = {}
    for ano in range(1, 8):
        casos = {
            "comum (Perigo = ano)": [ano],
            "chefe (ano + 1)": [ano + 1],
            "difícil (chefe + 2 capangas)": [ano + 1, max(1, ano - 2), max(1, ano - 2)],
        }
        if ano >= 3:
            casos["muito acima (ano + 4)"] = [min(11, ano + 4)]
        for nome, ins in casos.items():
            rs = [combate(ano, ins, 4, chefe_pv, chefe_acoes) for _ in range(n)]
            rods = sorted(x[0] for x in rs)
            caiu = sum(x[1] > 0 for x in rs) / n
            tpk = sum(x[1] == 4 for x in rs) / n
            res[(ano, nome)] = (rods[n // 2], caiu, tpk)
            print(f"  {ano}º ano, {nome:30}: {rods[n//2]:2} rodadas | {caiu*100:3.0f}% | {tpk*100:3.0f}%")
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
    if qual in ("tudo", "quadribol"): sim_quadribol(); print()
    if qual in ("tudo", "combate"): sim_combate(); print()
    if qual in ("tudo", "poções"): sim_pocoes()
