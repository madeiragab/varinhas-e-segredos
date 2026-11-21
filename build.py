"""Monta o livro: template/livro.html + livro.css + capítulos -> index.html."""
import datetime, pathlib
R = pathlib.Path(__file__).parent
T = R / "template"
VERSAO = "1.0 RC"
caps = "\n".join(p.read_text(encoding="utf-8") for p in sorted((T / "capitulos").glob("*.html")))
html = (T / "livro.html").read_text(encoding="utf-8")
html = (html.replace("{{CSS}}", (T / "livro.css").read_text(encoding="utf-8"))
            .replace("{{CAPITULOS}}", caps)
            .replace("{{VERSAO}}", VERSAO)
            .replace("{{DATA}}", datetime.date.today().strftime("%d/%m/%Y")))
(R / "index.html").write_text("<!doctype html>\n<html lang=\"pt-BR\">\n<head>\n<meta charset=\"utf-8\">\n<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">\n" + html + "\n</html>\n", encoding="utf-8")
# checagens: nada de placeholder sobrando, versão no HTML, toda âncora interna existe
erros = [p for p in ("{{CSS}}", "{{CAPITULOS}}", "{{VERSAO}}", "{{DATA}}") if p in html]
if "versão " + VERSAO not in html:
    erros.append("versão " + VERSAO + " não aparece no HTML")
import re
ids = set(re.findall(r'id="([^"]+)"', html))
erros += ["link para #" + a + " sem destino" for a in sorted(set(re.findall(r'href="#([^"]+)"', html)) - ids)]
if erros:
    raise SystemExit("ERRO no build:" + "".join("\n  " + e for e in erros))
print("index.html gerado,", len(html) // 1024, "KB")
