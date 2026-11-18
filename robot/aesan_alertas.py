#!/usr/bin/env python3
"""
Robot de alertas AESAN para Gestaluna.

Una vez al día (lo lanza GitHub Actions):
  1. Lee las últimas alertas publicadas por AESAN.
  2. Las guarda TODAS (sin filtrar) y les pone una etiqueta según el motivo
     (Listeria, Salmonella, alérgenos...).
  3. Guarda el resultado en alertas.json, que la app lee al abrirse.

Solo usa la librería estándar de Python: no hay nada que instalar.
"""

import datetime as dt
import html
import json
import os
import re
import sys
import unicodedata
import urllib.request
from html.parser import HTMLParser

BASE = "https://www.aesan.gob.es"
PAGINAS_LISTADO = [
    BASE + "/es/alertas",
    BASE + "/alertas/alertas-alimentarias",
]
ARCHIVO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "alertas.json")

DIAS_A_CONSERVAR = 180     # alertas más antiguas se borran del archivo
MAX_ALERTAS = 50
VERSION_ARCHIVO = 2        # subir este número obliga a releer todas las alertas
MAX_REVISADAS = 400        # memoria de alertas ya leídas (relevantes o no)

# Patrón de las direcciones de cada alerta: /alertas/2026_81 o /alertas/2026_81_amp
RE_ENLACE = re.compile(r"/alertas/(\d{4}_\d+(?:_amp\d*)?)/?$", re.I)

# ---------------------------------------------------------------------------
# Etiquetas según el peligro. Se busca en el TÍTULO de la alerta
# (AESAN siempre nombra el peligro en el título). Orden = prioridad.
# No filtra: las alertas que no encajan reciben la etiqueta "Alérgenos" u "Otros".
# ---------------------------------------------------------------------------
PELIGROS = [
    {
        "motivo": "Listeria",
        "claves": ["listeria"],
        "gravedad": "alta",
    },
    {
        "motivo": "Toxoplasma",
        "claves": ["toxoplasma"],
        "gravedad": "alta",
    },
    {
        "motivo": "Botulismo",
        "claves": ["botul", "clostridium botulinum"],
        "gravedad": "alta",
    },
    {
        "motivo": "Salmonella",
        "claves": ["salmonel"],
        "gravedad": "media",
    },
    {
        "motivo": "E. coli",
        "claves": ["e. coli", "e.coli", "escherichia", "stec", "verotoxig", "shiga"],
        "gravedad": "media",
    },
    {
        "motivo": "Virus (hepatitis A / norovirus)",
        "claves": ["hepatitis", "norovirus"],
        "gravedad": "media",
    },
    {
        "motivo": "Otras bacterias",
        "claves": ["campylobacter", "brucel", "bacillus cereus", "cereulid", "estafiloc",
                   "staphylococ", "vibrio", "yersinia", "cronobacter", "microbiol"],
        "gravedad": "media",
    },
    {
        "motivo": "Contaminante químico",
        "claves": ["mercurio", "plomo", "cadmio", "arsenico", "dioxina", "pcb", "aflatoxin",
                   "ocratoxin", "micotoxin", "alcaloide", "oxido de etileno", "histamina",
                   "plaguicida", "acido cianhidrico", "patulina", "zearalenona"],
        "gravedad": "baja",
    },
]

# Alertas para personas alérgicas o intolerantes (etiqueta "Alérgenos")
CLAVES_SOLO_ALERGIA = ["alergi", "intoleranc", "alergeno", "no declarad", "sulfito", "gluten"]


def normalizar(texto):
    """minúsculas y sin tildes, para comparar palabras clave."""
    t = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def descargar(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (GestalunaAlertas; +https://app.ginecologacristinagarcia.com)",
        "Accept-Language": "es-ES,es;q=0.9",
    })
    with urllib.request.urlopen(req, timeout=40) as r:
        return r.read().decode(r.headers.get_content_charset() or "utf-8", errors="replace")


class LectorEnlaces(HTMLParser):
    """Recoge todos los enlaces <a> con su texto."""

    def __init__(self):
        super().__init__()
        self.enlaces = []
        self._href = None
        self._texto = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self._href = dict(attrs).get("href")
            self._texto = []

    def handle_data(self, data):
        if self._href is not None:
            self._texto.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._href is not None:
            texto = " ".join(" ".join(self._texto).split())
            self.enlaces.append((self._href, texto))
            self._href = None


def alertas_del_listado(html_pagina):
    """Devuelve {id: {"url", "titulo"}} con las alertas enlazadas en una página."""
    lector = LectorEnlaces()
    lector.feed(html_pagina)
    encontradas = {}
    for href, texto in lector.enlaces:
        if not href:
            continue
        ruta = href.split("?")[0].split("#")[0]
        if ruta.startswith(BASE):
            ruta = ruta[len(BASE):]
        m = RE_ENLACE.search(ruta)
        if not m:
            continue
        ident = m.group(1).lower()
        url = BASE + "/alertas/" + ident
        # Nos quedamos con el texto más largo (a veces hay un enlace "Leer más")
        if ident not in encontradas or len(texto) > len(encontradas[ident]["titulo"]):
            encontradas[ident] = {"url": url, "titulo": texto}
    return encontradas


MESES = {"enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6, "julio": 7,
         "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12}


def leer_detalle(html_pagina):
    """Saca título y fecha de la página de una alerta."""
    titulo = None
    m = re.search(r"<h1[^>]*>(.*?)</h1>", html_pagina, re.S | re.I)
    if m:
        titulo = " ".join(html.unescape(re.sub(r"<[^>]+>", " ", m.group(1))).split())
    if not titulo:
        m = re.search(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)', html_pagina, re.I)
        if m:
            titulo = html.unescape(m.group(1)).strip()

    fecha = None
    # 1) metadatos de publicación (formato ISO). Se pasa a hora de Madrid aprox. (+1 h)
    m = re.search(r'(?:published_time|datePublished|dcterms\.date|"date")["\']?\s*[:=]?\s*'
                  r'(?:content=)?["\'](\d{4}-\d{2}-\d{2})(?:T(\d{2}))?', html_pagina, re.I)
    if m:
        d = dt.date.fromisoformat(m.group(1))
        if m.group(2) and int(m.group(2)) >= 22:   # 23:00Z del día anterior = día siguiente en España
            d += dt.timedelta(days=1)
        fecha = d
    texto = normalizar(html.unescape(re.sub(r"<[^>]+>", " ", html_pagina)))
    # 2) fecha en texto "10/11/2026"
    if not fecha:
        m = re.search(r"\b(\d{1,2})/(\d{1,2})/(20\d{2})\b", texto)
        if m:
            fecha = dt.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    # 3) fecha en texto "10 noviembre 2026" / "10 de noviembre de 2026"
    if not fecha:
        m = re.search(r"\b(\d{1,2})\s+(?:de\s+)?(" + "|".join(MESES) + r")\s+(?:de\s+)?(20\d{2})\b", texto)
        if m:
            fecha = dt.date(int(m.group(3)), MESES[m.group(2)], int(m.group(1)))
    return titulo, fecha


def clasificar(titulo):
    """Devuelve la etiqueta de la alerta. Nunca descarta ninguna."""
    t = normalizar(titulo)
    for peligro in PELIGROS:
        if any(clave in t for clave in peligro["claves"]):
            return peligro
    if any(clave in t for clave in CLAVES_SOLO_ALERGIA):
        return {"motivo": "Alérgenos", "gravedad": "baja"}
    return {"motivo": "Otros", "gravedad": "baja"}


def referencia(titulo):
    m = re.search(r"Ref\.?\s*(ES\s?\d{4}/\d+)", titulo, re.I)
    return m.group(1).replace(" ", "") if m else None


def limpiar_texto_listado(texto):
    """El enlace del listado incluye icono, fecha y "Ver más": se quitan."""
    t = re.sub(r"\b(error_outline|warning|info|campaign|notifications?)\b", " ", texto)
    t = re.sub(r"^\s*\d{1,2}\s+(?:de\s+)?[A-Za-zÁÉÍÓÚáéíóú]+\s+(?:de\s+)?20\d{2}\s*", "", t.strip())
    t = re.sub(r"\s*(Ver más|Leer más)\s*$", "", t, flags=re.I)
    return " ".join(t.split())


def titulo_limpio(titulo):
    """Quita la referencia del final y el punto sobrante para mostrarlo en la app."""
    titulo = limpiar_texto_listado(titulo)
    t = re.sub(r"\s*\(?\s*Ref\.?\s*ES\s?\d{4}/\d+\s*\)?\s*\.?\s*$", "", titulo, flags=re.I)
    return t.rstrip(" .")


def cargar_archivo():
    try:
        with open(ARCHIVO, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"alertas": [], "revisadas": []}


def main():
    hoy = dt.date.today()
    datos = cargar_archivo()
    if datos.get("version") != VERSION_ARCHIVO:   # cambio de formato: se empieza de cero
        datos = {"alertas": [], "revisadas": []}
    alertas = {a["id"]: a for a in datos.get("alertas", [])}
    revisadas = list(datos.get("revisadas", []))

    # 1. Leer listados
    listado = {}
    for url in PAGINAS_LISTADO:
        try:
            listado.update(alertas_del_listado(descargar(url)))
        except Exception as e:  # una página caída no detiene al robot
            print(f"Aviso: no se pudo leer {url}: {e}")

    if not listado:
        # Si no encuentra NINGUNA alerta, probablemente AESAN ha cambiado su web.
        # Fallar hace que GitHub te avise por correo; alertas.json no se toca.
        print("ERROR: no se ha encontrado ninguna alerta en la web de AESAN. "
              "Puede que hayan cambiado el diseño de la página.")
        sys.exit(1)

    # 2. Revisar solo las alertas nuevas
    nuevas = 0
    for ident, info in listado.items():
        if ident in revisadas or ident in alertas:
            continue
        titulo, fecha = info["titulo"], None
        try:
            t2, fecha = leer_detalle(descargar(info["url"]))
            # Se elige el título más completo (preferiblemente el que lleva la referencia ES20xx/...)
            candidatos = [limpiar_texto_listado(x) for x in (t2, titulo) if x]
            candidatos.sort(key=lambda x: (referencia(x) is not None, len(x)), reverse=True)
            titulo = candidatos[0] if candidatos else titulo
        except Exception as e:
            print(f"Aviso: no se pudo abrir {info['url']}: {e}")
            continue   # se reintentará mañana
        if not titulo:
            continue
        revisadas.append(ident)
        peligro = clasificar(titulo)
        alertas[ident] = {
            "id": ident,
            "ref": referencia(titulo),
            "titulo": titulo_limpio(titulo),
            "fecha": (fecha or hoy).isoformat(),
            "motivo": peligro["motivo"],
            "gravedad": peligro["gravedad"],
            "url": info["url"],
        }
        nuevas += 1
        print(f"  NUEVA ({peligro['motivo']}): {titulo}")

    # 3. Ordenar, recortar y guardar
    limite = (hoy - dt.timedelta(days=DIAS_A_CONSERVAR)).isoformat()
    lista = sorted((a for a in alertas.values() if a["fecha"] >= limite),
                   key=lambda a: (a["fecha"], a["id"]), reverse=True)[:MAX_ALERTAS]
    salida = {
        "version": VERSION_ARCHIVO,
        "actualizado": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        "fuente": "AESAN - Red de alerta alimentaria (https://www.aesan.gob.es/es/alertas)",
        "alertas": lista,
        "revisadas": revisadas[-MAX_REVISADAS:],
    }
    with open(ARCHIVO, "w", encoding="utf-8") as f:
        json.dump(salida, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"Listo: {len(listado)} alertas en AESAN, {nuevas} nuevas, {len(lista)} en el archivo.")


if __name__ == "__main__":
    main()
