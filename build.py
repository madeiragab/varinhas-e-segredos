"""Monta o livro: template/livro.html + livro.css + capítulos -> index.html."""
import datetime, pathlib
R = pathlib.Path(__file__).parent
T = R / "template"
VERSAO = "0.2"
caps = "\n".join(p.read_text(encoding="utf-8") for p in sorted((T / "capitulos").glob("*.html")))
html = (T / "livro.html").read_text(encoding="utf-8")
html = (html.replace("{{CSS}}", (T / "livro.css").read_text(encoding="utf-8"))
            .replace("{{CAPITULOS}}", caps)
            .replace("{{VERSAO}}", VERSAO)
            .replace("{{DATA}}", datetime.date.today().strftime("%d/%m/%Y")))
(R / "index.html").write_text("<!doctype html>\n<html lang=\"pt-BR\">\n<head>\n<meta charset=\"utf-8\">\n<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">\n" + html + "\n</html>\n", encoding="utf-8")
print("index.html gerado,", len(html) // 1024, "KB")
