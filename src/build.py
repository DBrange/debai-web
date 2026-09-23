"""Genera la landing de debai.app en cada idioma a partir de la plantilla.

    python src/build.py

Entrada:  src/landing.html (plantilla, textos en español) + src/strings.json (EN / DE).
Salida:   index.html (inglés, idioma por defecto), es/index.html, sitemap.xml y robots.txt.

Cada idioma es una página estática con su propia URL: es lo que Google necesita para
indexar los dos idiomas (una sola URL que cambia el texto con JavaScript solo se indexa
en el idioma que ve Googlebot, que es inglés).
"""

import datetime
import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = "https://debai.app/"

# Idiomas publicados, en orden. Para activar el alemán: agregar "de" (cuando haya
# capturas en alemán, ver `shots`). El primero es el idioma por defecto (x-default).
ENABLED = ["en", "es"]

LANGS = {
    # path: carpeta de salida y URL · shots: sufijo de las capturas localizadas
    "en": {"path": "", "shots": "en"},
    "es": {"path": "es/", "shots": "es"},
    "de": {"path": "de/", "shots": "en"},
}

APP_STORE = "https://apps.apple.com/app/id6796000118"
PLAY_STORE = "https://play.google.com/store/apps/details?id=com.debai.app"


def rel(from_lang: str, to_lang: str) -> str:
    """Link relativo de la página de un idioma a la de otro."""
    if from_lang == to_lang:
        return "./"
    up = "../" if LANGS[from_lang]["path"] else ""
    target = LANGS[to_lang]["path"]
    return (up + target) or "./"


def translate_body(src: str, lang: str, t: dict) -> str:
    if lang != "es":
        def text_node(m):
            key = m.group(3)
            if key not in t:
                raise KeyError(f"Falta '{key}' en strings.json[{lang}]")
            return m.group(1) + html.escape(t[key], quote=False) + m.group(5)

        def html_node(m):
            key = m.group(3)
            if key not in t:
                raise KeyError(f"Falta '{key}' en strings.json[{lang}]")
            return m.group(1) + t[key] + m.group(5)

        src = re.sub(r'(<([a-z0-9]+)\b[^>]*\sdata-i18n="([^"]+)"[^>]*>)(.*?)(</\2>)', text_node, src, flags=re.S)
        src = re.sub(r'(<([a-z0-9]+)\b[^>]*\sdata-i18n-html="([^"]+)"[^>]*>)(.*?)(</\2>)', html_node, src, flags=re.S)

    def alt(m):
        return f'alt="{html.escape(t[m.group(1)])}"'

    src = re.sub(r'alt="" data-i18n-alt="([^"]+)"', alt, src)
    src = re.sub(r'\sdata-i18n(?:-html)?="[^"]+"', "", src)

    shots = LANGS[lang]["shots"]
    src = re.sub(r'data-shot="[^"]+" src="(assets/screens/[a-z]+)-es\.webp"', rf'src="\1-{shots}.webp"', src)
    return src


def prefix_assets(src: str, lang: str) -> str:
    """Las páginas en subcarpeta (es/) apuntan a los assets de la raíz."""
    if not LANGS[lang]["path"]:
        return src
    src = re.sub(r'((?:src|href)=")(assets/|legal/|favicon|apple-touch)', r"\1../\2", src)
    return src.replace('url("assets/', 'url("../assets/')


def jsonld(lang: str, t: dict) -> str:
    org = SITE + "#organization"
    data = {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "Organization",
                "@id": org,
                "name": "DebAi",
                "url": SITE,
                "logo": SITE + "favicon-192.png",
                "sameAs": [APP_STORE, PLAY_STORE],
            },
            {
                "@type": "WebSite",
                "@id": SITE + "#website",
                "url": SITE,
                "name": "DebAi",
                "inLanguage": lang,
                "publisher": {"@id": org},
            },
            {
                "@type": "MobileApplication",
                "name": "DebAi",
                "description": t["meta.app_description"],
                "operatingSystem": "iOS, Android",
                "applicationCategory": "FinanceApplication",
                "inLanguage": ["es", "en", "de"],
                "image": f"{SITE}assets/og-{LANGS[lang]['shots']}.png",
                "installUrl": [APP_STORE, PLAY_STORE],
                # La descarga es gratis; la suscripción se contrata dentro de la app
                "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"},
                "publisher": {"@id": org},
            },
        ],
    }
    return json.dumps(data, ensure_ascii=False).replace("</", "<\\/")


def runtime_js(lang: str) -> str:
    homes = {l: rel(lang, l) for l in ENABLED}
    return f"""
    (function () {{
      var HERE = "{lang}", HOMES = {json.dumps(homes)};
      function go(l) {{ location.replace(HOMES[l] + location.hash); }}
      function saved() {{ try {{ return localStorage.getItem("debai.lang"); }} catch (e) {{ return null; }} }}
      document.querySelectorAll(".lang a").forEach(function (a) {{
        a.addEventListener("click", function () {{
          try {{ localStorage.setItem("debai.lang", a.getAttribute("hreflang")); }} catch (e) {{}}
        }});
      }});
      // Links viejos con ?lang=xx
      try {{
        var q = new URLSearchParams(location.search).get("lang");
        if (q && HOMES[q] && q !== HERE) {{ go(q); return; }}
      }} catch (e) {{}}
      // Solo la raíz detecta el idioma: quien entra a /es/ ya eligió
      if (HERE !== "{ENABLED[0]}") return;
      var s = saved();
      if (s) {{ if (HOMES[s] && s !== HERE) go(s); return; }}
      var prefs = navigator.languages && navigator.languages.length ? navigator.languages : [navigator.language || ""];
      for (var i = 0; i < prefs.length; i++) {{
        var l = String(prefs[i]).slice(0, 2).toLowerCase();
        if (HOMES[l]) {{ if (l !== HERE) go(l); return; }}
      }}
    }})();
  """


def build_page(template: str, strings: dict, lang: str) -> str:
    t = strings[lang]
    url = SITE + LANGS[lang]["path"]
    out = re.sub(r"<!--TEMPLATE.*?-->\n", "", template, flags=re.S)
    out = translate_body(out, lang, t)

    hreflang = "\n  ".join(
        [f'<link rel="alternate" hreflang="{l}" href="{SITE + LANGS[l]["path"]}" />' for l in ENABLED]
        + [f'<link rel="alternate" hreflang="x-default" href="{SITE}" />']
    )
    og_alts = "\n  ".join(
        f'<meta property="og:locale:alternate" content="{strings[l]["meta.og_locale"]}" />'
        for l in ENABLED if l != lang
    )
    lang_links = "".join(
        f'<a href="{rel(lang, l)}" hreflang="{l}" lang="{l}"'
        + (' aria-current="page"' if l == lang else "")
        + f">{l.upper()}</a>"
        for l in ENABLED
    )

    values = {
        "lang": lang,
        "url": url,
        "robots": "index, follow, max-image-preview:large",
        "hreflang": hreflang,
        "og_locale_alternates": og_alts,
        "shots": LANGS[lang]["shots"],
        "jsonld": jsonld(lang, t),
        "lang_links": lang_links,
        "runtime_js": runtime_js(lang),
    }

    def fill(m):
        key = m.group(1)
        if key in values:
            return values[key]
        if key in t:
            return html.escape(t[key])
        raise KeyError(f"Falta '{key}' en strings.json[{lang}]")

    out = re.sub(r"\{\{([a-z_.]+)\}\}", fill, out)
    return prefix_assets(out, lang)


def build_sitemap() -> str:
    today = datetime.date.today().isoformat()
    alts = "".join(
        f'\n    <xhtml:link rel="alternate" hreflang="{l}" href="{SITE + LANGS[l]["path"]}" />' for l in ENABLED
    ) + f'\n    <xhtml:link rel="alternate" hreflang="x-default" href="{SITE}" />'
    pages = "".join(
        f"\n  <url>\n    <loc>{SITE + LANGS[l]['path']}</loc>\n    <lastmod>{today}</lastmod>{alts}\n  </url>"
        for l in ENABLED
    )
    legal = "".join(
        f"\n  <url>\n    <loc>{SITE}legal/{p}</loc>\n  </url>" for p in ["index.html", "terminos.html"]
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
        'xmlns:xhtml="http://www.w3.org/1999/xhtml">'
        f"{pages}{legal}\n</urlset>\n"
    )


ROBOTS = f"""User-agent: *
Allow: /
Disallow: /src/

Sitemap: {SITE}sitemap.xml
"""


def main():
    template = (ROOT / "src/landing.html").read_text(encoding="utf-8")
    strings = json.loads((ROOT / "src/strings.json").read_text(encoding="utf-8"))
    for lang in ENABLED:
        dest = ROOT / LANGS[lang]["path"] / "index.html"
        dest.parent.mkdir(parents=True, exist_ok=True)
        page = build_page(template, strings, lang)
        if "{{" in page:
            raise ValueError(f"Quedó un placeholder sin reemplazar en {dest}")
        dest.write_text(page, encoding="utf-8", newline="\n")
        print("ok", dest.relative_to(ROOT))
    (ROOT / "sitemap.xml").write_text(build_sitemap(), encoding="utf-8", newline="\n")
    (ROOT / "robots.txt").write_text(ROBOTS, encoding="utf-8", newline="\n")
    print("ok sitemap.xml, robots.txt")


if __name__ == "__main__":
    main()
