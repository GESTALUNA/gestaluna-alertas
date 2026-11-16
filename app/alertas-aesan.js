/*
 * Gestaluna · Alertas alimentarias AESAN
 * ---------------------------------------
 * Lee el archivo alertas.json que deja el robot en GitHub y muestra en la app
 * las alertas que afectan al embarazo, con un botón "Entendido" para ocultarlas.
 *
 * Uso:
 *   <div id="alertas-inicio"></div>        (pantalla de inicio: solo las no vistas)
 *   <div id="alertas-apartado"></div>      (apartado "Alertas": todas las recientes)
 *   <script src="alertas-aesan.js"></script>
 *   <script>
 *     GestalunaAlertas.mostrar("#alertas-inicio");
 *     GestalunaAlertas.mostrar("#alertas-apartado", { todas: true });
 *   </script>
 *
 * Todo se guarda solo en el móvil de la paciente (localStorage): qué alertas ha
 * marcado como entendidas y la última copia descargada, para verlas sin conexión.
 */
(function () {
  "use strict";

  var CONFIG = {
    // ⚠️ Cambiar USUARIO por tu nombre de usuario de GitHub al activarlo
    url: "https://raw.githubusercontent.com/USUARIO/gestaluna-alertas/main/alertas.json",
    diasInicio: 30,    // en el inicio se muestran alertas de los últimos 30 días
    diasApartado: 180  // en el apartado de alertas, las de los últimos 6 meses
  };

  var CLAVE_VISTAS = "gestaluna.alertas.entendidas";
  var CLAVE_COPIA = "gestaluna.alertas.copia";
  var contenedores = [];

  // ---------- almacenamiento local (con protección si no está disponible) ----------
  function leerLocal(clave, porDefecto) {
    try {
      var v = localStorage.getItem(clave);
      return v ? JSON.parse(v) : porDefecto;
    } catch (e) { return porDefecto; }
  }
  function guardarLocal(clave, valor) {
    try { localStorage.setItem(clave, JSON.stringify(valor)); } catch (e) { /* sin espacio o bloqueado */ }
  }

  function entendidas() { return leerLocal(CLAVE_VISTAS, []); }
  function marcarEntendida(id) {
    var lista = entendidas();
    if (lista.indexOf(id) === -1) lista.push(id);
    guardarLocal(CLAVE_VISTAS, lista.slice(-300));
  }

  // ---------- descarga ----------
  function descargar() {
    return fetch(CONFIG.url, { cache: "no-store" })
      .then(function (r) {
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.json();
      })
      .then(function (datos) {
        guardarLocal(CLAVE_COPIA, datos);
        return datos;
      })
      .catch(function () {
        // sin conexión: usamos la última copia guardada
        return leerLocal(CLAVE_COPIA, { alertas: [] });
      });
  }

  // ---------- utilidades ----------
  function esc(t) {
    return String(t == null ? "" : t).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function haceDias(n) {
    var d = new Date();
    d.setDate(d.getDate() - n);
    return d.toISOString().slice(0, 10);
  }
  function fechaBonita(iso) {
    var p = String(iso).split("-");
    var meses = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];
    return p.length === 3 ? parseInt(p[2], 10) + " " + meses[parseInt(p[1], 10) - 1] + " " + p[0] : iso;
  }

  // ---------- pintar ----------
  function pintar(c) {
    var datos = c.datos || { alertas: [] };
    var vistas = entendidas();
    var desde = haceDias(c.opciones.todas ? CONFIG.diasApartado : CONFIG.diasInicio);
    var lista = (datos.alertas || []).filter(function (a) {
      return a.fecha >= desde && (c.opciones.todas || vistas.indexOf(a.id) === -1);
    });

    if (!lista.length) {
      c.el.innerHTML = c.opciones.todas
        ? '<p class="gl-alertas-vacio">No hay alertas alimentarias recientes que afecten al embarazo.</p>'
        : "";
      return;
    }

    var html = '<section class="gl-alertas" aria-label="Alertas alimentarias">';
    if (!c.opciones.todas) {
      html += '<h2 class="gl-alertas-titulo">Alertas alimentarias</h2>';
    }
    lista.forEach(function (a) {
      var vista = vistas.indexOf(a.id) !== -1;
      html +=
        '<article class="gl-alerta gl-' + esc(a.gravedad || "media") + (vista ? " gl-vista" : "") + '">' +
          '<div class="gl-alerta-cab">' +
            '<span class="gl-alerta-motivo">' + esc(a.motivo) + "</span>" +
            '<time class="gl-alerta-fecha" datetime="' + esc(a.fecha) + '">' + esc(fechaBonita(a.fecha)) + "</time>" +
          "</div>" +
          '<h3 class="gl-alerta-texto">' + esc(a.titulo) + "</h3>" +
          '<div class="gl-alerta-botones">' +
            '<a class="gl-btn-sec" href="' + esc(a.url) + '" target="_blank" rel="noopener">Ver lotes en AESAN</a>' +
            (vista ? '<span class="gl-alerta-ok">✓ Entendido</span>'
                   : '<button type="button" class="gl-btn" data-id="' + esc(a.id) + '">Entendido</button>') +
          "</div>" +
        "</article>";
    });
    html += '<p class="gl-alertas-fuente">Fuente: AESAN. Comprueba siempre marca y lote en el enlace oficial.</p></section>';
    c.el.innerHTML = html;
  }

  function pintarTodos() { contenedores.forEach(pintar); }

  function actualizar() {
    return descargar().then(function (datos) {
      contenedores.forEach(function (c) { c.datos = datos; });
      pintarTodos();
    });
  }

  // ---------- estilos (usa los colores de marca si existen como variables CSS) ----------
  function estilos() {
    if (document.getElementById("gl-alertas-css")) return;
    var css =
      ".gl-alertas{display:flex;flex-direction:column;gap:12px;margin:16px 0}" +
      ".gl-alertas-titulo{font-size:1.05rem;margin:0;color:var(--gl-texto,#2b2b2b)}" +
      ".gl-alerta{background:var(--gl-fondo-tarjeta,#fff);border-radius:14px;padding:14px 16px;" +
        "box-shadow:0 1px 4px rgba(0,0,0,.08);border-left:5px solid var(--gl-aviso-media,#e0a33a)}" +
      ".gl-alerta.gl-alta{border-left-color:var(--gl-aviso-alta,#c8463d)}" +
      ".gl-alerta.gl-baja{border-left-color:var(--gl-aviso-baja,#7a9cc6)}" +
      ".gl-alerta.gl-vista{opacity:.7}" +
      ".gl-alerta-cab{display:flex;justify-content:space-between;align-items:center;gap:8px;margin-bottom:6px}" +
      ".gl-alerta-motivo{font-size:.75rem;font-weight:700;text-transform:uppercase;letter-spacing:.04em;" +
        "color:var(--gl-primario,#8a5a83)}" +
      ".gl-alerta-fecha{font-size:.8rem;color:#777}" +
      ".gl-alerta-texto{font-size:.95rem;line-height:1.35;margin:0 0 10px;color:var(--gl-texto,#2b2b2b)}" +
      ".gl-alerta-botones{display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap}" +
      ".gl-btn{background:var(--gl-primario,#8a5a83);color:#fff;border:0;border-radius:999px;" +
        "padding:9px 20px;font:inherit;font-size:.9rem;cursor:pointer}" +
      ".gl-btn-sec{color:var(--gl-primario,#8a5a83);font-size:.85rem}" +
      ".gl-alerta-ok{font-size:.85rem;color:#4c8a5a}" +
      ".gl-alertas-fuente,.gl-alertas-vacio{font-size:.78rem;color:#888;margin:0}";
    var s = document.createElement("style");
    s.id = "gl-alertas-css";
    s.textContent = css;
    document.head.appendChild(s);
  }

  // ---------- API pública ----------
  function mostrar(selector, opciones) {
    var el = typeof selector === "string" ? document.querySelector(selector) : selector;
    if (!el) return;
    estilos();
    var c = { el: el, opciones: opciones || {}, datos: leerLocal(CLAVE_COPIA, null) };
    contenedores.push(c);
    el.addEventListener("click", function (e) {
      var b = e.target.closest && e.target.closest("button[data-id]");
      if (!b) return;
      marcarEntendida(b.getAttribute("data-id"));
      pintarTodos();
    });
    pintar(c);           // primero, al instante, con la copia guardada
    if (!mostrar._enCurso) {
      mostrar._enCurso = true;
      actualizar();      // después, con lo último del robot
    }
  }

  // Al volver a la app desde segundo plano, se vuelve a consultar
  document.addEventListener("visibilitychange", function () {
    if (document.visibilityState === "visible" && contenedores.length) actualizar();
  });

  window.GestalunaAlertas = {
    config: CONFIG,
    mostrar: mostrar,
    actualizar: actualizar,
    pendientes: function () {   // nº de alertas sin ver (para un globo en el menú)
      var datos = leerLocal(CLAVE_COPIA, { alertas: [] }), vistas = entendidas(), desde = haceDias(CONFIG.diasInicio);
      return (datos.alertas || []).filter(function (a) { return a.fecha >= desde && vistas.indexOf(a.id) === -1; }).length;
    }
  };
})();
