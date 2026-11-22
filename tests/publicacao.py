"""Confere se o site no ar (GitHub Pages) é o mesmo build do index.html local.
Uso: python tests/publicacao.py   (rode depois do push; o Pages leva um ou dois minutos)"""
import re, sys, pathlib, urllib.request
URL = "https://madeiragab.github.io/varinhas-e-segredos/"
local = pathlib.Path(__file__).parent.parent.joinpath("index.html").read_text(encoding="utf-8")
no_ar = urllib.request.urlopen(urllib.request.Request(URL, headers={"Cache-Control": "no-cache"}), timeout=30).read().decode("utf-8")
pega = lambda h: (re.search(r'<meta name="build" content="([0-9a-f]+)"', h) or [None, None])[1]
a, b = pega(local), pega(no_ar)
print(f"local {a} | no ar {b}")
if a and a == b:
    print("ok: o site no ar é este build")
else:
    print("DIFERENTE: o Pages ainda não publicou este build (ou o navegador mostra cache)")
    sys.exit(1)
