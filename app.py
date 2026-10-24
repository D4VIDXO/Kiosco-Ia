import streamlit as st
import pandas as pd
import os
import hmac
import time
import gspread
from gspread.utils import rowcol_to_a1
from google.oauth2.service_account import Credentials
import requests
import json
from datetime import datetime
import streamlit.components.v1 as components
import base64

# Configuración de la página web
st.set_page_config(
    page_title="Kiosco",
    page_icon="favicon.png" if os.path.exists("favicon.png") else None,
    layout="wide"
)

CARPETA_IMAGENES = "imagenes_productos"
CARPETA_REPORTES = "reportes_cierre"

# Cargar estilos desde archivo externo
with open("estilos.css", encoding="utf-8") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# ==========================================
# CONEXIÓN GOOGLE SHEETS
# ==========================================
# ==========================================
# ICONOS HECHOS A MANO (SVG) Y COMPONENTES
# ==========================================
_SVG = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" '
        'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{}</svg>')

ICONOS = {
    "tienda": '<path d="M4 9l1.5-4.5h13L20 9"/><path d="M4 9a2.67 2.67 0 0 0 5.33 0 2.67 2.67 0 0 0 5.34 0A2.67 2.67 0 0 0 20 9"/><path d="M5.5 11.5V20h13v-8.5M10 20v-5h4v5"/>',
    "carrito": '<path d="M3 4h2.2l2.1 10.2a1.5 1.5 0 0 0 1.5 1.2h7.7a1.5 1.5 0 0 0 1.5-1.1L19.5 8H6.1"/><circle cx="9.5" cy="19.5" r="1.2"/><circle cx="17" cy="19.5" r="1.2"/>',
    "caja": '<path d="M12 3 4 7.2v9.6L12 21l8-4.2V7.2L12 3Z"/><path d="M4 7.2 12 11.5 20 7.2M12 11.5V21"/>',
    "mas": '<rect x="4" y="4" width="16" height="16" rx="3"/><path d="M12 8.5v7M8.5 12h7"/>',
    "campana": '<path d="M6 16.5V11a6 6 0 0 1 12 0v5.5l1.5 1.5h-15L6 16.5Z"/><path d="M10 20.5a2 2 0 0 0 4 0"/>',
    "chat": '<path d="M5 5h14a1.5 1.5 0 0 1 1.5 1.5v8A1.5 1.5 0 0 1 19 16H11l-4.5 3.5V16H5a1.5 1.5 0 0 1-1.5-1.5v-8A1.5 1.5 0 0 1 5 5Z"/><path d="M8.5 10.5h.01M12 10.5h.01M15.5 10.5h.01"/>',
    "sliders": '<path d="M4 7h9M17 7h3M4 17h3M11 17h9"/><circle cx="15" cy="7" r="2"/><circle cx="9" cy="17" r="2"/>',
    "corona": '<path d="M4 18h16M5 18 4 8l4.5 4L12 6l3.5 6L20 8l-1 10"/>',
    "llave": '<circle cx="8" cy="15" r="3.5"/><path d="M10.5 12.5 19 4M16 7l2.5 2.5M13.5 9.5l2 2"/>',
    "reloj": '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
    "baja": '<path d="M4 7l6 6 3.5-3.5L20 16"/><path d="M20 11v5h-5"/>',
    "calendario_x": '<rect x="4" y="5.5" width="16" height="14.5" rx="2.5"/><path d="M4 10h16M8 3.5v4M16 3.5v4M10 13.5l4 4M14 13.5l-4 4"/>',
    "ticket": '<path d="M6 3.5h12v17l-2.5-1.5-2 1.5-1.5-1.5-1.5 1.5-2-1.5L6 20.5v-17Z"/><path d="M9 8h6M9 12h6"/>',
    "imagen": '<rect x="3.5" y="5" width="17" height="14" rx="2.5"/><circle cx="9" cy="10" r="1.6"/><path d="M4 17l5-4.5 3.5 3 3-2.5 4.5 4"/>',
    "escaner": '<path d="M4 8V5.5A1.5 1.5 0 0 1 5.5 4H8M16 4h2.5A1.5 1.5 0 0 1 20 5.5V8M20 16v2.5a1.5 1.5 0 0 1-1.5 1.5H16M8 20H5.5A1.5 1.5 0 0 1 4 18.5V16"/><path d="M7.5 12h9"/>',
}


def svg(nombre):
    return _SVG.format(ICONOS[nombre])


def md_html(html):
    """Muestra HTML compacto (sin saltos que Markdown pueda tomar como código)."""
    st.markdown(" ".join(html.split()), unsafe_allow_html=True)


def encabezado(nombre, titulo, sub=""):
    sub_html = f'<div class="seccion-sub">{sub}</div>' if sub else ""
    md_html(f'<div class="seccion"><div class="seccion-ico">{svg(nombre)}</div>'
            f'<div><div class="seccion-titulo">{titulo}</div>{sub_html}</div></div>')


def vacio(nombre, titulo, sub=""):
    md_html(f'<div class="vacio"><span class="ico">{svg(nombre)}</span><div>'
            f'<div style="color:var(--text-2);font-weight:500">{titulo}</div>'
            f'<div style="font-size:0.88rem">{sub}</div></div></div>')


def kpi_html(nombre, etiqueta, valor, color):
    return (f'<div class="kpi" style="--acento:{color}"><div class="kpi-ico">{svg(nombre)}</div>'
            f'<div><div class="kpi-label">{etiqueta}</div><div class="kpi-valor">{valor}</div></div></div>')



SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

COLUMNAS_INV = ["Código", "Producto", "Precio Venta", "Stock Actual", "Stock Mínimo", "Fecha Vencimiento"]
HOJA_INVENTARIO = "Inventario"
HOJA_VENTAS = "Ventas_Turno"
COLS_VENTAS = ["Ticket", "Hora Ticket", "Código", "Producto", "Precio", "Cantidad", "Total"]


def limpiar_codigo(valor):
    """Normaliza un código de barras: texto, sin espacios y sin '.0' final."""
    c = str(valor).strip()
    if c.endswith(".0"):
        c = c[:-2]
    if c.lower() in ["nan", "none", "<na>"]:
        return ""
    return c


@st.cache_resource
def _abrir_libro():
    """Abre el libro. Si falla lanza la excepción, así Streamlit NO guarda el error en caché."""
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=SCOPES
    )
    cliente = gspread.authorize(creds)
    return cliente.open_by_key(st.secrets["SHEET_ID"])


def conectar_sheets():
    """Conecta con Google Sheets usando las credenciales de Streamlit Secrets."""
    try:
        return _abrir_libro()
    except Exception as e:
        st.error(f"Error conectando con Google Sheets: {e}")
        return None


def obtener_hoja(libro, nombre=HOJA_INVENTARIO):
    """Obtiene o crea la hoja de inventario."""
    try:
        try:
            return libro.worksheet(nombre)
        except gspread.WorksheetNotFound:
            hoja = libro.add_worksheet(title=nombre, rows=1000, cols=10)
            hoja.append_row(COLUMNAS_INV)
            return hoja
    except Exception as e:
        st.error(f"Error obteniendo hoja: {e}")
        return None


def cargar_inventario():
    """Carga el inventario desde Google Sheets."""
    try:
        libro = conectar_sheets()
        if not libro:
            return pd.DataFrame(columns=COLUMNAS_INV)
        hoja = obtener_hoja(libro)
        if not hoja:
            return pd.DataFrame(columns=COLUMNAS_INV)
        datos = hoja.get_all_records()
        if not datos:
            return pd.DataFrame(columns=COLUMNAS_INV)
        df = pd.DataFrame(datos)
        for col in COLUMNAS_INV:
            if col not in df.columns:
                df[col] = ""
        df["Código"] = df["Código"].fillna("").astype(str).str.strip()
        df["Precio Venta"] = pd.to_numeric(df["Precio Venta"], errors='coerce').fillna(0.0)
        df["Stock Actual"] = pd.to_numeric(df["Stock Actual"], errors='coerce').fillna(0).astype(int)
        df["Stock Mínimo"] = pd.to_numeric(df["Stock Mínimo"], errors='coerce').fillna(5).astype(int)
        df["Fecha Vencimiento"] = df["Fecha Vencimiento"].fillna("").astype(str)
        return df
    except Exception as e:
        st.error(f"Error cargando inventario: {e}")
        return pd.DataFrame(columns=COLUMNAS_INV)


def guardar_inventario(df):
    """
    Guarda el inventario completo en Google Sheets.
    Primero escribe los datos nuevos y recién después limpia las filas sobrantes,
    así nunca queda la hoja vacía si algo falla a mitad de camino.
    """
    try:
        libro = conectar_sheets()
        if not libro:
            return False
        hoja = obtener_hoja(libro)
        if not hoja:
            return False
        datos = [COLUMNAS_INV]
        for _, fila in df.iterrows():
            datos.append([
                str(fila.get("Código", "")),
                str(fila.get("Producto", "")),
                float(fila.get("Precio Venta", 0)),
                int(fila.get("Stock Actual", 0)),
                int(fila.get("Stock Mínimo", 5)),
                str(fila.get("Fecha Vencimiento", ""))
            ])
        hoja.update(datos)
        if hoja.row_count > len(datos):
            hoja.batch_clear([f"A{len(datos) + 1}:F{hoja.row_count}"])
        return True
    except Exception as e:
        st.error(f"Error guardando inventario: {e}")
        return False


def descontar_stock_sheets(items):
    """
    Descuenta stock directamente en Google Sheets, celda por celda, leyendo
    primero el stock REAL de la hoja. Así, si dos puestos cobran a la vez,
    ninguno pisa los cambios del otro.
    Devuelve (ok, mensaje_de_error).
    """
    try:
        libro = conectar_sheets()
        if not libro:
            return False, "No hay conexión con Google Sheets."
        hoja = obtener_hoja(libro)
        if not hoja:
            return False, "No se pudo abrir la hoja de inventario."
        valores = hoja.get_all_values()
        if not valores:
            return False, "El inventario está vacío."
        encabezado = valores[0]
        i_cod = encabezado.index("Código")
        i_stock = encabezado.index("Stock Actual")

        filas = {}
        for n, fila in enumerate(valores[1:], start=2):
            cod = limpiar_codigo(fila[i_cod]) if len(fila) > i_cod else ""
            if cod:
                filas[cod] = (n, fila)

        cambios = []
        for item in items:
            cod = limpiar_codigo(item["Código"])
            if cod not in filas:
                return False, f"'{item['Producto']}' ya no existe en el inventario."
            n, fila = filas[cod]
            try:
                stock = int(float(fila[i_stock]))
            except (ValueError, IndexError):
                stock = 0
            if stock < item["Cantidad"]:
                return False, f"Stock insuficiente de '{item['Producto']}' (quedan {stock})."
            cambios.append({
                "range": rowcol_to_a1(n, i_stock + 1),
                "values": [[stock - int(item["Cantidad"])]]
            })
        if cambios:
            hoja.batch_update(cambios)
        return True, ""
    except Exception as e:
        return False, f"Error descontando stock: {e}"


def guardar_cierre_sheets(fecha_legible, responsable, total_caja, articulos_totales, detalle_productos_texto):
    """Guarda el cierre de caja en una hoja separada de Google Sheets."""
    try:
        libro = conectar_sheets()
        if not libro:
            return False
        nombre_hoja = datetime.now().strftime("%B %Y").capitalize()
        try:
            hoja = libro.worksheet(nombre_hoja)
        except gspread.WorksheetNotFound:
            hoja = libro.add_worksheet(title=nombre_hoja, rows=1000, cols=6)
            hoja.append_row(["Fecha y Hora", "Responsable", "Total Recaudado ($)", "Artículos Vendidos", "Detalle de Productos"])
        hoja.append_row([fecha_legible, responsable, float(total_caja), int(articulos_totales), detalle_productos_texto])
        return True
    except Exception as e:
        st.error(f"Error guardando cierre: {e}")
        return False


def cargar_cierres_sheets(nombre_hoja):
    """Carga los cierres históricos desde Google Sheets."""
    try:
        libro = conectar_sheets()
        if not libro:
            return pd.DataFrame()
        hoja = libro.worksheet(nombre_hoja)
        datos = hoja.get_all_records()
        if not datos:
            return pd.DataFrame()
        return pd.DataFrame(datos)
    except Exception:
        return pd.DataFrame()


def listar_hojas_cierres():
    """Lista las hojas de cierres (excluye Inventario y Ventas_Turno)."""
    try:
        libro = conectar_sheets()
        if not libro:
            return []
        return [h.title for h in libro.worksheets() if h.title not in (HOJA_INVENTARIO, HOJA_VENTAS)]
    except Exception:
        return []


# ==========================================
# VENTAS DEL TURNO (persistentes en Sheets)
# ==========================================
def obtener_hoja_ventas(libro):
    try:
        return libro.worksheet(HOJA_VENTAS)
    except gspread.WorksheetNotFound:
        hoja = libro.add_worksheet(title=HOJA_VENTAS, rows=1000, cols=len(COLS_VENTAS))
        hoja.append_row(COLS_VENTAS)
        return hoja


def guardar_ticket_sheets(items):
    """Guarda las líneas de un ticket cobrado en la hoja Ventas_Turno."""
    try:
        libro = conectar_sheets()
        if not libro:
            return False
        hoja = obtener_hoja_ventas(libro)
        filas = [[
            int(i["Ticket"]), str(i["Hora Ticket"]), limpiar_codigo(i["Código"]), str(i["Producto"]),
            float(i["Precio"]), int(i["Cantidad"]), float(i["Total"])
        ] for i in items]
        hoja.append_rows(filas, value_input_option="RAW")
        return True
    except Exception as e:
        st.error(f"Error guardando el ticket del turno: {e}")
        return False


def cargar_ventas_turno():
    """Recupera las ventas del turno que quedaron guardadas (por si se recargó la página)."""
    try:
        libro = conectar_sheets()
        if not libro:
            return []
        hoja = obtener_hoja_ventas(libro)
        ventas = []
        for r in hoja.get_all_records():
            try:
                ventas.append({
                    "Ticket": int(r["Ticket"]),
                    "Hora Ticket": str(r["Hora Ticket"]),
                    "Código": limpiar_codigo(r["Código"]),
                    "Producto": str(r["Producto"]),
                    "Precio": float(r["Precio"]),
                    "Cantidad": int(r["Cantidad"]),
                    "Total": float(r["Total"]),
                })
            except (ValueError, KeyError, TypeError):
                continue
        return ventas
    except Exception:
        return []


def limpiar_ventas_turno():
    """Vacía la hoja de ventas del turno (después del cierre de caja)."""
    try:
        libro = conectar_sheets()
        if not libro:
            return False
        hoja = obtener_hoja_ventas(libro)
        hoja.clear()
        hoja.append_row(COLS_VENTAS)
        return True
    except Exception as e:
        st.error(f"Error limpiando ventas del turno: {e}")
        return False


# ==========================================
# IMÁGENES (local)
# ==========================================
def guardar_imagen_producto(codigo, archivo_subido):
    if not os.path.exists(CARPETA_IMAGENES):
        os.makedirs(CARPETA_IMAGENES)
    extension = archivo_subido.name.split(".")[-1].lower()
    ruta = os.path.join(CARPETA_IMAGENES, f"{codigo}.{extension}")
    with open(ruta, "wb") as f:
        f.write(archivo_subido.getbuffer())
    return ruta


def obtener_imagen_producto(codigo):
    for ext in ["jpg", "jpeg", "png", "webp"]:
        ruta = os.path.join(CARPETA_IMAGENES, f"{codigo}.{ext}")
        if os.path.exists(ruta):
            return ruta
    return None


def buscar_imagen_online(codigo, nombre_producto):
    try:
        if codigo and codigo not in ["", "nan", "None"]:
            url = f"https://world.openfoodfacts.org/api/v0/product/{codigo}.json"
            headers = {"User-Agent": "KioscoApp/1.0"}
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == 1:
                    product = data.get("product", {})
                    imagen_url = (
                        product.get("image_front_url") or
                        product.get("image_url") or
                        product.get("selected_images", {}).get("front", {}).get("display", {}).get("es") or
                        product.get("selected_images", {}).get("front", {}).get("display", {}).get("en")
                    )
                    if imagen_url:
                        img_response = requests.get(imagen_url, headers=headers, timeout=10)
                        if img_response.status_code == 200:
                            if not os.path.exists(CARPETA_IMAGENES):
                                os.makedirs(CARPETA_IMAGENES)
                            ruta = os.path.join(CARPETA_IMAGENES, f"{codigo}.jpg")
                            with open(ruta, "wb") as f:
                                f.write(img_response.content)
                            return ruta
    except Exception as e:
        print(f"No se pudo obtener imagen online: {e}")
    return None


# ==========================================
# EFECTOS DE SONIDO
# ==========================================
def emitir_sonido_navegador(tipo):
    if tipo == "exito":
        js_code = """<script>
        const ctx = new (window.AudioContext || window.webkitAudioContext)();
        const osc = ctx.createOscillator(); const gain = ctx.createGain();
        osc.type = 'sine'; osc.frequency.setValueAtTime(950, ctx.currentTime);
        gain.gain.setValueAtTime(0.1, ctx.currentTime);
        osc.connect(gain); gain.connect(ctx.destination);
        osc.start(); osc.stop(ctx.currentTime + 0.08);
        </script>"""
    elif tipo == "error":
        js_code = """<script>
        const ctx = new (window.AudioContext || window.webkitAudioContext)();
        const osc = ctx.createOscillator(); const gain = ctx.createGain();
        osc.type = 'sawtooth'; osc.frequency.setValueAtTime(130, ctx.currentTime);
        gain.gain.setValueAtTime(0.12, ctx.currentTime);
        osc.connect(gain); gain.connect(ctx.destination);
        osc.start(); osc.stop(ctx.currentTime + 0.25);
        </script>"""
    else:
        return
    components.html(js_code, height=0, width=0)


# ==========================================
# INICIALIZACIÓN DE SESIÓN
# ==========================================
if 'df' not in st.session_state:
    st.session_state.df = cargar_inventario()
if 'numero_ticket' not in st.session_state:
    st.session_state.numero_ticket = 1
if 'carrito_actual' not in st.session_state:
    st.session_state.carrito_actual = []
if 'ventas_del_dia' not in st.session_state:
    # Se recuperan desde Sheets por si la página se recargó a mitad del turno
    st.session_state.ventas_del_dia = cargar_ventas_turno()
    if st.session_state.ventas_del_dia:
        st.session_state.numero_ticket = max(v["Ticket"] for v in st.session_state.ventas_del_dia) + 1
if 'sonido_a_reproducir' not in st.session_state:
    st.session_state.sonido_a_reproducir = None
if 'historial_chat' not in st.session_state:
    st.session_state.historial_chat = []
if 'accion_pendiente' not in st.session_state:
    st.session_state.accion_pendiente = None
if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False
if 'rol' not in st.session_state:
    st.session_state.rol = None
if 'nombre_usuario' not in st.session_state:
    st.session_state.nombre_usuario = ""
if 'perfil_pendiente' not in st.session_state:
    st.session_state.perfil_pendiente = None
if 'intentos_pin' not in st.session_state:
    st.session_state.intentos_pin = 0
if 'bloqueado_hasta' not in st.session_state:
    st.session_state.bloqueado_hasta = 0.0

hoy = datetime.now()
df_actual = st.session_state.df

# ==========================================
# LOGIN CON PIN
# ==========================================
PERFILES = [
    {"rol": "jefe",       "nombre": "Jefe",       "icono": "corona", "color": "#E58A9B", "desc": "Administración completa"},
    {"rol": "encargado",  "nombre": "Encargado",  "icono": "llave",  "color": "#E8A24A", "desc": "Caja, inventario y cierres"},
    {"rol": "trabajador", "nombre": "Trabajador", "icono": "carrito", "color": "#6FC2A8", "desc": "Caja y consultas"},
]


def pines_configurados():
    """Lee los PIN desde st.secrets['PINES'] (nunca van escritos en el código)."""
    try:
        return {k: str(v) for k, v in dict(st.secrets["PINES"]).items()}
    except Exception:
        return {}


def verificar_pin(rol, pin_ingresado):
    esperado = pines_configurados().get(rol, "")
    if not esperado:
        return False
    return hmac.compare_digest(esperado.encode("utf-8"), pin_ingresado.encode("utf-8"))


if not st.session_state.autenticado:
    st.markdown("<br>", unsafe_allow_html=True)

    if not pines_configurados():
        st.error(
            "Faltan los PIN de acceso. Agregá esto en `.streamlit/secrets.toml` "
            "(y en los Secrets de Streamlit Cloud) y reiniciá la app:\n\n"
            "```toml\n[PINES]\njefe = \"1234\"\nencargado = \"5678\"\ntrabajador = \"0000\"\n```"
        )
        st.stop()

    if st.session_state.perfil_pendiente is None:
        md_html(f'<div class="login-head"><div class="hero-logo login-logo">{svg("tienda")}</div>'
                '<div class="hero-tag">Kiosco</div>'
                '<div class="login-title">¿Quién está usando el sistema?</div>'
                '<div class="login-sub">Seleccioná tu perfil para continuar</div></div>')
        col1, col2, col3 = st.columns(3)
        for col, perfil in zip([col1, col2, col3], PERFILES):
            with col:
                md_html(f'<div class="perfil-card" style="--acento:{perfil["color"]}">'
                        f'<div class="perfil-anillo">{svg(perfil["icono"])}</div>'
                        f'<div class="perfil-nombre">{perfil["nombre"]}</div>'
                        f'<div class="perfil-desc">{perfil["desc"]}</div></div>')
                if st.button(f"Entrar como {perfil['nombre']}", key=f"btn_{perfil['rol']}", use_container_width=True):
                    st.session_state.perfil_pendiente = perfil["rol"]
                    st.rerun()
    else:
        perfil = next(p for p in PERFILES if p["rol"] == st.session_state.perfil_pendiente)
        md_html(f'<div class="perfil-anillo pin-anillo" style="--acento:{perfil["color"]}">{svg(perfil["icono"])}</div>'
                f'<div class="pin-nombre">{perfil["nombre"]}</div><div class="pin-sub">Ingresá tu PIN</div>')
        _, centro, _ = st.columns([1, 1, 1])
        with centro:
            restante = int(st.session_state.bloqueado_hasta - time.time())
            if restante > 0:
                st.error(f"Demasiados intentos. Esperá {restante} segundos.")
                if st.button("Volver", use_container_width=True):
                    st.session_state.perfil_pendiente = None
                    st.rerun()
            else:
                with st.form("form_pin", clear_on_submit=True):
                    pin = st.text_input("PIN", type="password")
                    entrar = st.form_submit_button("Entrar", type="primary", use_container_width=True)
                    volver = st.form_submit_button("Volver", use_container_width=True)
                if volver:
                    st.session_state.perfil_pendiente = None
                    st.rerun()
                if entrar:
                    if verificar_pin(perfil["rol"], pin):
                        st.session_state.autenticado = True
                        st.session_state.rol = perfil["rol"]
                        st.session_state.nombre_usuario = perfil["nombre"]
                        st.session_state.perfil_pendiente = None
                        st.session_state.intentos_pin = 0
                        st.rerun()
                    else:
                        st.session_state.intentos_pin += 1
                        if st.session_state.intentos_pin >= 5:
                            st.session_state.bloqueado_hasta = time.time() + 60
                            st.session_state.intentos_pin = 0
                        st.error("PIN incorrecto.")
    # Único lugar donde st.stop() es correcto: nadie vio la app todavía
    if st.session_state.sonido_a_reproducir:
        emitir_sonido_navegador(st.session_state.sonido_a_reproducir)
        st.session_state.sonido_a_reproducir = None
    st.stop()

# ==========================================
# INTERFAZ PRINCIPAL
# ==========================================
col_titulo, col_usuario = st.columns([3, 1])
with col_titulo:
    md_html(f'<div class="hero"><div class="hero-marca"><div class="hero-logo">{svg("tienda")}</div>'
            '<div><div class="hero-tag">Sistema de gestión</div><div class="hero-title">Kiosco</div></div></div></div>')
with col_usuario:
    nombre_u = st.session_state.nombre_usuario
    md_html(f'<div class="user-chip"><div class="user-avatar">{nombre_u[:1].upper()}</div>'
            f'<div><div class="user-name">{nombre_u}</div>'
            f'<div class="user-role"><span class="dot"></span>Sesión activa</div></div></div>')
    if st.button("Cerrar sesión", use_container_width=True):
        st.session_state.autenticado = False
        st.session_state.rol = None
        st.session_state.nombre_usuario = ""
        st.session_state.perfil_pendiente = None
        st.session_state.accion_pendiente = None
        st.rerun()

st.markdown("<br>", unsafe_allow_html=True)
encabezado("caja", "Estado general", "Resumen del inventario")
productos_faltantes = 0
productos_vencidos = 0
if not df_actual.empty:
    productos_faltantes = len(df_actual[df_actual["Stock Actual"] <= df_actual["Stock Mínimo"]])
    for idx, fila in df_actual.iterrows():
        try:
            fecha_v = datetime.strptime(str(fila["Fecha Vencimiento"]).split()[0], '%Y-%m-%d')
            if (fecha_v - hoy).days < 0:
                productos_vencidos += 1
        except Exception:
            pass
with st.container(key="kpis"):
    col1, col2, col3 = st.columns(3)
    with col1:
        md_html(kpi_html("caja", "Productos", len(df_actual), "#E58A9B"))
    with col2:
        md_html(kpi_html("baja", "A reponer", productos_faltantes, "#E8A24A"))
    with col3:
        md_html(kpi_html("calendario_x", "Vencidos", productos_vencidos, "#FF6B6B"))
st.markdown("---")

tabs_base = ["Caja", "Inventario", "Nuevo Producto", "Alertas", "Asistente IA"]
if st.session_state.rol == "jefe":
    tabs_base.append("Administración")
tabs_resultado = st.tabs(tabs_base)
tab_caja = tabs_resultado[0]
tab_gestion = tabs_resultado[1]
tab_carga = tabs_resultado[2]
tab_vencimientos = tabs_resultado[3]
tab_ia = tabs_resultado[4]
tab_admin = tabs_resultado[5] if st.session_state.rol == "jefe" else None


# ==========================================
# FUNCIONES DE CAJA
# ==========================================
def cancelar_producto(idx_carrito):
    st.session_state.carrito_actual.pop(idx_carrito)
    st.toast("Producto quitado de la venta.")
    st.rerun()


def procesar_escaneo():
    codigo_leido = st.session_state.input_escanner.strip()
    if codigo_leido:
        df = st.session_state.df
        codigos_limpios = df["Código"].astype(str).str.replace(r'\.0$', '', regex=True)
        match = df[codigos_limpios == codigo_leido]
        if not match.empty:
            idx = match.index[0]
            producto = df.at[idx, "Producto"]
            stock_disp = df.at[idx, "Stock Actual"]
            precio = df.at[idx, "Precio Venta"]
            en_carrito = sum(item["Cantidad"] for item in st.session_state.carrito_actual if item["Código"] == codigo_leido)
            if stock_disp > en_carrito:
                encontrado = False
                for item in st.session_state.carrito_actual:
                    if item["Código"] == codigo_leido:
                        item["Cantidad"] += 1
                        item["Total"] = item["Precio"] * item["Cantidad"]
                        encontrado = True
                        break
                if not encontrado:
                    st.session_state.carrito_actual.append({
                        "Hora": datetime.now().strftime("%H:%M:%S"),
                        "Código": codigo_leido,
                        "Producto": producto,
                        "Precio": float(precio),
                        "Cantidad": 1,
                        "Total": float(precio)
                    })
                st.toast(f"Agregado: {producto} (${precio})")
                st.session_state.sonido_a_reproducir = "exito"
            else:
                st.toast(f"Sin stock de '{producto}'")
                st.session_state.sonido_a_reproducir = "error"
        else:
            st.toast(f"Código '{codigo_leido}' no registrado.")
            st.session_state.sonido_a_reproducir = "error"
    st.session_state.input_escanner = ""


# ==========================================
# PESTAÑA 1: CAJA
# ==========================================
with tab_caja:
    encabezado("escaner", "Punto de venta", "Escaneá los productos para armar la venta")
    st.text_input(
        "Escanear producto",
        key="input_escanner",
        on_change=procesar_escaneo
    )
    st.markdown("---")
    col_tabla, col_cierre = st.columns([2, 1])
    with col_tabla:
        st.markdown("#### Venta en curso")
        if st.session_state.carrito_actual:
            # key="carrito" permite que el CSS mantenga cada fila en una sola línea en el celular
            try:
                contenedor_carrito = st.container(height=270, key="carrito")
            except TypeError:  # Streamlit viejo sin 'key' en container
                contenedor_carrito = st.container(height=270)
            with contenedor_carrito:
                c_hora, c_prod, c_cant, c_prec, c_accion = st.columns([1, 2, 1, 1, 1])
                c_hora.markdown("**Hora**")
                c_prod.markdown("**Producto**")
                c_cant.markdown("**Cant.**")
                c_prec.markdown("**Total**")
                c_accion.markdown("**Quitar**")
                st.markdown("---")
                for i in reversed(range(len(st.session_state.carrito_actual))):
                    item = st.session_state.carrito_actual[i]
                    ch, cp, ccant, cpr, ca = st.columns([1, 2, 1, 1, 1])
                    ch.write(f"{item['Hora']}")
                    cp.write(item['Producto'])
                    col_menos, col_cant, col_mas = ccant.columns([1, 1, 1])
                    if col_menos.button("−", key=f"btn_menos_{i}", use_container_width=True):
                        if item["Cantidad"] > 1:
                            st.session_state.carrito_actual[i]["Cantidad"] -= 1
                            st.session_state.carrito_actual[i]["Total"] = item["Precio"] * st.session_state.carrito_actual[i]["Cantidad"]
                            st.rerun()
                        else:
                            cancelar_producto(i)
                    col_cant.markdown(f"<div class='cant-num'>{item['Cantidad']}</div>", unsafe_allow_html=True)
                    if col_mas.button("+", key=f"btn_mas_{i}", use_container_width=True):
                        df = st.session_state.df
                        codigos_limpios = df["Código"].astype(str).str.replace(r'\.0$', '', regex=True)
                        match = df[codigos_limpios == item["Código"]]
                        if not match.empty:
                            stock_disp = match.iloc[0]["Stock Actual"]
                            if item["Cantidad"] < stock_disp:
                                st.session_state.carrito_actual[i]["Cantidad"] += 1
                                st.session_state.carrito_actual[i]["Total"] = item["Precio"] * st.session_state.carrito_actual[i]["Cantidad"]
                                st.rerun()
                            else:
                                st.warning(f"Sin más stock de '{item['Producto']}'")
                    cpr.write(f"${item['Total']:,.2f}")
                    if ca.button("×", key=f"btn_carrito_{i}", type="secondary", use_container_width=True):
                        cancelar_producto(i)
            total_carrito = sum(item["Total"] for item in st.session_state.carrito_actual)
            md_html(f'<div class="total-caja compacto"><div class="total-label">Subtotal</div><div class="total-monto">${total_carrito:,.2f}</div></div>')
            if st.button("Cobrar y finalizar ticket", type="primary", use_container_width=True):
                hora_ticket = datetime.now().strftime("%H:%M:%S")
                with st.spinner("Guardando en Google Sheets..."):
                    # Descuenta sobre el stock REAL de la hoja (seguro con varios puestos)
                    ok_stock, error_stock = descontar_stock_sheets(st.session_state.carrito_actual)
                if not ok_stock:
                    st.error(f"{error_stock}")
                    st.session_state.df = cargar_inventario()
                else:
                    st.session_state.df = cargar_inventario()
                    for item in st.session_state.carrito_actual:
                        item["Ticket"] = st.session_state.numero_ticket
                        item["Hora Ticket"] = hora_ticket
                    # Guarda el ticket para no perderlo si se recarga la página
                    if not guardar_ticket_sheets(st.session_state.carrito_actual):
                        st.warning("La venta se cobró pero el ticket no se pudo respaldar en Sheets.")
                    st.session_state.ventas_del_dia.extend(st.session_state.carrito_actual)
                    st.session_state.carrito_actual = []
                    st.session_state.numero_ticket += 1
                    st.toast("¡Venta cobrada!")
                    st.rerun()
        else:
            vacio("escaner", "Esperando escaneo", "Pasá el lector por un producto para empezar la venta")

        st.markdown("---")
        st.markdown("#### Ventas del turno")
        if st.session_state.ventas_del_dia:
            df_ventas = pd.DataFrame(st.session_state.ventas_del_dia)
            for (ticket, hora_t), grupo in df_ventas.groupby(["Ticket", "Hora Ticket"]):
                detalle = ", ".join(f"{int(r.Cantidad)}x {r.Producto}" for r in grupo.itertuples())
                total_ticket = grupo["Total"].sum()
                articulos = int(grupo["Cantidad"].sum())
                md_html(f'<div class="ticket" style="--acento:#E58A9B"><div class="ticket-main"><div class="ticket-ico">{svg("ticket")}</div><div><div class="ticket-meta">Ticket {int(ticket)} · {hora_t}</div><div class="ticket-detalle">{detalle}</div></div></div><div><div class="ticket-total">${total_ticket:,.0f}</div><div class="ticket-cant">{articulos} artículo{"s" if articulos > 1 else ""}</div></div></div>')
            total_acumulado = df_ventas["Total"].sum()
            md_html(f'<div class="total-caja"><div class="total-label">Total en caja</div><div class="total-monto">${total_acumulado:,.2f}</div></div>')
        else:
            st.caption("Sin ventas cerradas en este turno.")

    with col_cierre:
        st.markdown("#### Cierre de caja")
        if st.session_state.rol == "trabajador":
            st.warning("Solo el encargado o jefe puede cerrar.")
        elif st.session_state.ventas_del_dia:
            df_ventas = pd.DataFrame(st.session_state.ventas_del_dia)
            total_caja = df_ventas["Total"].sum()
            articulos_totales = df_ventas["Cantidad"].sum()
            if st.button("Hacer cierre de caja", type="primary", use_container_width=True):
                fecha_legible = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
                df_agrupado_prod = df_ventas.groupby("Producto")["Cantidad"].sum().reset_index()
                detalle = ", ".join([f"{r['Producto']} (x{r['Cantidad']})" for _, r in df_agrupado_prod.iterrows()])
                with st.spinner("Guardando cierre en Google Sheets..."):
                    ok = guardar_cierre_sheets(fecha_legible, st.session_state.nombre_usuario, total_caja, articulos_totales, detalle)
                    if ok:
                        limpiar_ventas_turno()
                if ok:
                    st.session_state.ventas_del_dia = []
                    st.session_state.numero_ticket = 1
                    st.success("Cierre guardado en Google Sheets.")
                    st.rerun()

        st.markdown("---")
        st.markdown("#### Historial de cierres")
        hojas = listar_hojas_cierres()
        if hojas:
            hoja_sel = st.selectbox("Mes:", options=hojas[::-1], index=0)
            with st.spinner("Cargando..."):
                df_hist = cargar_cierres_sheets(hoja_sel)
            if not df_hist.empty:
                filas_visibles = st.selectbox("Mostrar:", options=[5, 10, 25, 50], index=1)
                st.dataframe(df_hist.iloc[::-1].head(filas_visibles), use_container_width=True)
            else:
                st.info("Sin cierres en este mes.")
        else:
            st.info("Sin cierres registrados aún.")


# ==========================================
# PESTAÑA 2: INVENTARIO
# ==========================================
def render_inventario():
    df = st.session_state.df
    if df.empty:
        st.info("El inventario está vacío.")
        return

    col_busca1, col_busca2 = st.columns(2)
    with col_busca1:
        buscar = st.text_input("Buscar por nombre:", "").strip()
    with col_busca2:
        codigo_escaneado = st.text_input("Escanear código:", key="scanner_edicion_manual").strip()
    if codigo_escaneado:
        df_filtrado = df[df["Código"].astype(str).str.replace(r'\.0$', '', regex=True) == codigo_escaneado]
        if df_filtrado.empty:
            st.error(f"No se encontró el código: '{codigo_escaneado}'")
    else:
        df_filtrado = df[df["Producto"].str.contains(buscar, case=False, na=False, regex=False)] if buscar else df

    if not df_filtrado.empty:
        producto_a_editar = st.selectbox("Seleccioná el producto:", df_filtrado["Producto"].unique())
        datos_prod = df[df["Producto"] == producto_a_editar].iloc[0]
        with st.form(f"form_edicion_{producto_a_editar}"):
            st.write(f"**Modificando:** {producto_a_editar}")
            imagen_actual = obtener_imagen_producto(limpiar_codigo(datos_prod.get("Código", "")))
            col_img, col_upload = st.columns([1, 2])
            with col_img:
                if imagen_actual:
                    st.image(imagen_actual, width=120)
                else:
                    st.caption("Sin imagen")
            with col_upload:
                nueva_imagen = st.file_uploader("Reemplazar imagen", type=["jpg", "jpeg", "png", "webp"], key=f"img_{producto_a_editar}")
            nuevo_nombre = st.text_input("Nombre:", value=producto_a_editar).strip()
            codigo_actual = limpiar_codigo(datos_prod.get("Código", ""))
            nuevo_codigo = st.text_input("Código:", value=codigo_actual).strip()
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                nuevo_precio = st.number_input("Precio ($)", min_value=0.0, value=float(datos_prod.get("Precio Venta", 0)), step=50.0)
            with c2:
                nuevo_stock = st.number_input("Stock Actual", min_value=0, value=int(float(datos_prod.get("Stock Actual", 0))))
            with c3:
                nuevo_minimo = st.number_input("Stock Mínimo", min_value=0, value=int(float(datos_prod.get("Stock Mínimo", 0))))
            with c4:
                try:
                    fecha_v_actual = datetime.strptime(str(datos_prod.get("Fecha Vencimiento", "")).split()[0], '%Y-%m-%d')
                except Exception:
                    fecha_v_actual = hoy
                nueva_fecha_v = st.date_input("Vencimiento", value=fecha_v_actual)
            col_b1, col_b2 = st.columns([1, 5])
            with col_b1:
                guardar = st.form_submit_button("Guardar")
            with col_b2:
                eliminar = st.form_submit_button("Eliminar")

        if guardar:
            if not nuevo_nombre:
                st.error("El nombre no puede estar vacío.")
            elif nuevo_nombre != producto_a_editar and nuevo_nombre in st.session_state.df["Producto"].values:
                st.error("Ya existe otro producto con ese nombre.")
            else:
                if nueva_imagen and nuevo_codigo:
                    guardar_imagen_producto(nuevo_codigo, nueva_imagen)
                st.session_state.df.loc[st.session_state.df["Producto"] == producto_a_editar,
                    ["Código", "Producto", "Precio Venta", "Stock Actual", "Stock Mínimo", "Fecha Vencimiento"]] = [
                    nuevo_codigo, nuevo_nombre, nuevo_precio, nuevo_stock, nuevo_minimo, nueva_fecha_v.strftime('%Y-%m-%d')]
                with st.spinner("Guardando..."):
                    ok = guardar_inventario(st.session_state.df)
                if ok:
                    st.success("¡Guardado!")
                    st.rerun()
        if eliminar:
            st.session_state.df = st.session_state.df[st.session_state.df["Producto"] != producto_a_editar]
            with st.spinner("Eliminando..."):
                guardar_inventario(st.session_state.df)
            st.success("Producto eliminado.")
            st.rerun()

    st.markdown("---")
    st.markdown("### Catálogo visual")
    if st.button("Buscar imágenes automáticamente"):
        productos_sin_imagen = [p for p in st.session_state.df.to_dict("records") if not obtener_imagen_producto(limpiar_codigo(p.get("Código", "")))]
        if not productos_sin_imagen:
            st.success("Todos los productos tienen imagen.")
        else:
            encontradas = 0
            barra = st.progress(0, text="Buscando...")
            for i, prod in enumerate(productos_sin_imagen):
                codigo = limpiar_codigo(str(prod.get("Código", "")).replace("#", ""))
                if buscar_imagen_online(codigo, str(prod.get("Producto", ""))):
                    encontradas += 1
                barra.progress((i + 1) / len(productos_sin_imagen), text=f"Buscando: {prod.get('Producto', '')}...")
            barra.empty()
            st.success(f"{encontradas} imágenes encontradas.")
            st.rerun()

    df_visual = st.session_state.df.copy()
    cols_por_fila = 4
    productos = df_visual.to_dict("records")
    for fila_idx in range(0, len(productos), cols_por_fila):
        fila = productos[fila_idx:fila_idx + cols_por_fila]
        columnas = st.columns(cols_por_fila)
        for col, prod in zip(columnas, fila):
            with col:
                imagen = obtener_imagen_producto(limpiar_codigo(prod.get("Código", "")))
                if imagen:
                    with open(imagen, "rb") as fimg:
                        img_b64 = base64.b64encode(fimg.read()).decode()
                    media = f'<div class="cat-img"><img src="data:image/jpeg;base64,{img_b64}" alt=""/></div>'
                else:
                    media = f'<div class="cat-vacio"><span class="ico">{svg("imagen")}</span>Sin imagen</div>'
                md_html(f'<div class="cat-card">{media}<div class="cat-info"><div class="cat-nombre">{prod.get("Producto", "")}</div>'
                        f'<div class="cat-fila"><div class="cat-precio">${prod.get("Precio Venta", 0):,.0f}</div>'
                        f'<div class="cat-stock">Stock {prod.get("Stock Actual", 0)}</div></div></div></div>')


with tab_gestion:
    encabezado("caja", "Inventario", "Editá productos, precios y stock")
    if st.session_state.rol == "trabajador":
        st.warning("No tenés permisos para modificar el inventario.")
    else:
        render_inventario()


# ==========================================
# PESTAÑA 3: NUEVO PRODUCTO
# ==========================================
def render_nuevo_producto():
    with st.form("formulario_producto", clear_on_submit=True):
        cod_input = st.text_input("Código de Barras").strip()
        c1, c2, c3 = st.columns(3)
        with c1:
            producto_input = st.text_input("Nombre del Producto").strip()
            precio_input = st.number_input("Precio de Venta ($)", min_value=0.0, value=0.0, step=0.5)
        with c2:
            stock_input = st.number_input("Stock Inicial", min_value=0, value=0)
            minimo_input = st.number_input("Stock Mínimo", min_value=0, value=5)
        with c3:
            fecha_venc_input = st.date_input("Fecha de Vencimiento", min_value=hoy)
        imagen_input = st.file_uploader("Imagen (opcional)", type=["jpg", "jpeg", "png", "webp"])
        enviado = st.form_submit_button("Agregar al Inventario")
    if enviado:
        df = st.session_state.df
        if not producto_input:
            st.error("El nombre no puede estar vacío.")
        elif producto_input in df["Producto"].values:
            st.error("El producto ya existe.")
        elif cod_input and cod_input in df["Código"].astype(str).map(limpiar_codigo).values:
            st.error("Ya existe un producto con ese código.")
        else:
            nueva_fila = pd.DataFrame([{
                "Código": cod_input, "Producto": producto_input,
                "Precio Venta": precio_input, "Stock Actual": stock_input,
                "Stock Mínimo": minimo_input, "Fecha Vencimiento": fecha_venc_input.strftime('%Y-%m-%d')
            }])
            st.session_state.df = pd.concat([df, nueva_fila], ignore_index=True)
            with st.spinner("Guardando en Google Sheets..."):
                ok = guardar_inventario(st.session_state.df)
            if ok:
                if imagen_input and cod_input:
                    guardar_imagen_producto(cod_input, imagen_input)
                st.success("¡Producto guardado!")
                st.rerun()


with tab_carga:
    encabezado("mas", "Nuevo producto", "Cargá un producto al inventario")
    if st.session_state.rol == "trabajador":
        st.warning("No tenés permisos para agregar productos.")
    else:
        render_nuevo_producto()

# ==========================================
# PESTAÑA 4: ALERTAS
# ==========================================
with tab_vencimientos:
    encabezado("campana", "Alertas", "Stock bajo y vencimientos")
    df = st.session_state.df
    if df.empty:
        st.info("No hay productos cargados.")
    else:
        st.markdown("#### Productos a reponer")
        df["Stock Actual"] = pd.to_numeric(df["Stock Actual"])
        df["Stock Mínimo"] = pd.to_numeric(df["Stock Mínimo"])
        reposiciones = df[df["Stock Actual"] <= df["Stock Mínimo"]].copy()
        if not reposiciones.empty:
            reposiciones["Faltante"] = reposiciones["Stock Mínimo"] - reposiciones["Stock Actual"]
            for _, row in reposiciones.iterrows():
                urgencia = "#FF6B6B" if row["Faltante"] > row["Stock Mínimo"] * 0.5 else "#E8A24A"
                md_html(f'<div class="alerta" style="--acento:{urgencia}"><div class="alerta-main"><div class="alerta-ico">{svg("baja")}</div><div><div class="alerta-nombre">{row["Producto"]}</div><div class="alerta-sub">Reposición pendiente</div></div></div><div class="alerta-cifras"><div class="cifra"><div class="cifra-label">Stock</div><div class="cifra-valor">{int(row["Stock Actual"])}</div></div><div class="cifra"><div class="cifra-label">Mínimo</div><div class="cifra-valor tenue">{int(row["Stock Mínimo"])}</div></div><div class="cifra"><div class="cifra-label">Faltan</div><div class="cifra-valor acento">{int(row["Faltante"])}</div></div></div></div>')
        else:
            st.success("Todo el stock al día.")
        st.markdown("---")
        lista_vencidos, lista_por_vencer = [], []
        for idx, fila in df.iterrows():
            try:
                fecha_v = datetime.strptime(str(fila["Fecha Vencimiento"]).split()[0], '%Y-%m-%d')
                dias = (fecha_v - hoy).days
                item = {"Producto": fila["Producto"], "Stock": fila["Stock Actual"], "Fecha Vencimiento": str(fila["Fecha Vencimiento"])}
                if dias < 0:
                    item["Días Vencido"] = abs(dias)
                    lista_vencidos.append(item)
                elif dias <= 15:
                    item["Días Restantes"] = dias
                    lista_por_vencer.append(item)
            except Exception:
                pass
        st.markdown("#### Productos vencidos")
        if lista_vencidos:
            for item in lista_vencidos:
                md_html(f'<div class="alerta" style="--acento:#FF6B6B"><div class="alerta-main"><div class="alerta-ico">{svg("calendario_x")}</div><div><div class="alerta-nombre">{item["Producto"]}</div><div class="alerta-sub">Venció el {item["Fecha Vencimiento"]}</div></div></div><div class="alerta-cifras"><div class="cifra"><div class="cifra-label">Vencido hace</div><div class="cifra-valor acento">{int(item["Días Vencido"])} d</div></div><div class="cifra"><div class="cifra-label">Stock</div><div class="cifra-valor tenue">{int(item["Stock"])}</div></div></div></div>')
        else:
            st.success("Ningún vencido.")
        st.markdown("#### Próximos a vencer (15 días)")
        if lista_por_vencer:
            for item in lista_por_vencer:
                color = "#FF6B6B" if item["Días Restantes"] <= 3 else "#E8A24A" if item["Días Restantes"] <= 7 else "#E58A9B"
                md_html(f'<div class="alerta" style="--acento:{color}"><div class="alerta-main"><div class="alerta-ico">{svg("reloj")}</div><div><div class="alerta-nombre">{item["Producto"]}</div><div class="alerta-sub">Vence el {item["Fecha Vencimiento"]}</div></div></div><div class="alerta-cifras"><div class="cifra"><div class="cifra-label">Faltan</div><div class="cifra-valor acento">{int(item["Días Restantes"])} d</div></div><div class="cifra"><div class="cifra-label">Stock</div><div class="cifra-valor tenue">{int(item["Stock"])}</div></div></div></div>')
        else:
            st.success("Sin vencimientos cercanos.")


# ==========================================
# PESTAÑA 5: ASISTENTE IA
# ==========================================
def buscar_producto_unico(df, nombre):
    """
    Devuelve (nombre_exacto, error). Solo acepta UN producto:
    primero coincidencia exacta; si no, coincidencia parcial única.
    Si hay varios candidatos no hace nada y pide aclarar.
    """
    nombre = str(nombre or "").strip()
    if not nombre:
        return None, "No me dijiste de qué producto hablás."
    exacto = df[df["Producto"].str.strip().str.lower() == nombre.lower()]
    if len(exacto) == 1:
        return exacto.iloc[0]["Producto"], None
    parcial = df[df["Producto"].str.contains(nombre, case=False, na=False, regex=False)]
    if len(parcial) == 1:
        return parcial.iloc[0]["Producto"], None
    if parcial.empty:
        return None, f"No encontré ningún producto parecido a '{nombre}'."
    lista = ", ".join(parcial["Producto"].head(8))
    return None, f"Hay varios productos que coinciden con '{nombre}': {lista}. ¿Cuál querés?"


def ejecutar_accion_ia(pend):
    """Ejecuta una acción ya confirmada. Devuelve (ok, mensaje)."""
    if st.session_state.rol == "trabajador":
        return False, "Tu perfil solo puede hacer consultas."
    df = st.session_state.df
    nombre = pend["producto"]
    mask = df["Producto"] == nombre
    if not mask.any():
        return False, f"El producto '{nombre}' ya no existe."
    if pend["accion"] == "ELIMINAR":
        st.session_state.df = df[~mask]
    elif pend["accion"] == "MODIFICAR":
        idx = df[mask].index[0]
        for campo, valor in pend["cambios"].items():
            st.session_state.df.at[idx, campo] = valor
    if guardar_inventario(st.session_state.df):
        return True, "Listo, cambio aplicado y guardado."
    return False, "No se pudo guardar en Google Sheets."


with tab_ia:
    encabezado("chat", "Asistente operativo", "Consultá o modificá el inventario hablando")
    st.write("Hablale para gestionar el inventario o pasá el lector de códigos en el chat.")
    gemini_key = ""
    if "GEMINI_KEY" in st.secrets:
        gemini_key = st.secrets["GEMINI_KEY"]
    else:
        gemini_key = st.text_input("API Key de Gemini", type="password").strip()
    st.markdown("---")
    for mensaje in st.session_state.historial_chat:
        with st.chat_message(mensaje["role"]):
            st.write(mensaje["content"])

    # Confirmación de acciones destructivas (modificar / eliminar)
    pend = st.session_state.accion_pendiente
    if pend:
        st.warning(f"Pendiente de confirmación: {pend['descripcion']}")
        cc1, cc2 = st.columns(2)
        if cc1.button("Confirmar", key="ia_confirmar", type="primary", use_container_width=True):
            with st.spinner("Aplicando..."):
                ok, msg = ejecutar_accion_ia(pend)
            st.session_state.accion_pendiente = None
            st.session_state.historial_chat.append({"role": "assistant", "content": msg})
            st.rerun()
        if cc2.button("Cancelar", key="ia_cancelar", use_container_width=True):
            st.session_state.accion_pendiente = None
            st.session_state.historial_chat.append({"role": "assistant", "content": "Acción cancelada. No se modificó nada."})
            st.rerun()

    prompt_chat = st.chat_input("Escribí una orden o pasá el escáner acá...")
    if prompt_chat:
        st.session_state.accion_pendiente = None  # una orden nueva descarta la pendiente
        with st.chat_message("user"):
            st.write(prompt_chat)
        st.session_state.historial_chat.append({"role": "user", "content": prompt_chat})
        if not gemini_key:
            respuesta_visible = "Ingresá tu API Key de Gemini para operar."
        else:
            es_solo_consulta = st.session_state.rol == "trabajador"
            with st.spinner("Procesando..."):
                texto_ingresado = prompt_chat.strip()
                df_actual = st.session_state.df
                if texto_ingresado.isdigit() and len(texto_ingresado) >= 4:
                    if not df_actual.empty:
                        codigos_limpios = df_actual["Código"].astype(str).str.replace(r'\.0$', '', regex=True)
                        match = df_actual[codigos_limpios == texto_ingresado]
                        if not match.empty:
                            nombre_prod = match.iloc[0]["Producto"]
                            prompt_a_enviar_ia = f"Acabo de escanear: '{nombre_prod}' (Código: {texto_ingresado}). Mostrame sus datos y preguntame qué modificamos."
                        else:
                            prompt_a_enviar_ia = f"Código '{texto_ingresado}' no está en el inventario. ¿Lo agrego?"
                    else:
                        prompt_a_enviar_ia = f"Código '{texto_ingresado}', inventario vacío. ¿Cómo se llama para agregarlo?"
                else:
                    prompt_a_enviar_ia = texto_ingresado
                resumen_inventario = st.session_state.df.to_string(index=False)
                fecha_hoy_humano = datetime.now().strftime("%d/%m/%Y")
                # La key va en el header, no en la URL (así no aparece en logs ni errores)
                # Modelo configurable: si Google lo retira, cambialo en secrets.toml (GEMINI_MODEL) sin tocar el código
                modelo_gemini = st.secrets["GEMINI_MODEL"] if "GEMINI_MODEL" in st.secrets else "gemini-3.5-flash"
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{modelo_gemini}:generateContent"
                headers = {'Content-Type': 'application/json', 'x-goog-api-key': gemini_key}
                modo_ia = "solo puede hacer CONSULTAS." if es_solo_consulta else "puede realizar ACCIONES y CONSULTAS."
                instruccion_sistema = (
                    f"Sos un Agente IA para un kiosco. El usuario {modo_ia}\n"
                    f"Hoy es {fecha_hoy_humano}.\n\n"
                    f"--- INVENTARIO ---\n{resumen_inventario}\n\n"
                    "RESPONDÉ SOLO EN JSON RECTO SIN TEXTO AFUERA:\n"
                    '{"accion":"AGREGAR"|"MODIFICAR"|"ELIMINAR"|"NINGUNA","datos":{"Código":"","Producto":"","Precio Venta":0.0,"Stock Actual":0,"Stock Mínimo":5,"Fecha Vencimiento":""},"mensaje":"respuesta amigable"}\n'
                    "REGLAS: en MODIFICAR incluí en 'datos' SOLO el nombre exacto del Producto y los campos que realmente cambian "
                    "(omití los demás). En ELIMINAR incluí solo el nombre exacto del Producto. "
                    "Usá el nombre completo tal como figura en el inventario."
                )
                payload = {"contents": [{"parts": [{"text": f"{instruccion_sistema}\n\nPetición: {prompt_a_enviar_ia}"}]}]}
                try:
                    response = requests.post(url, headers=headers, json=payload, timeout=30)
                    if response.status_code == 200:
                        resultado_raw = response.json()['candidates'][0]['content']['parts'][0]['text'].strip()
                        if resultado_raw.startswith("```"):
                            resultado_raw = resultado_raw.replace("```json", "").replace("```", "").strip()
                        paquete = json.loads(resultado_raw)
                        accion = paquete.get("accion", "NINGUNA")
                        datos = paquete.get("datos", {}) or {}
                        respuesta_visible = paquete.get("mensaje", "Orden procesada.")

                        if accion in ("AGREGAR", "MODIFICAR", "ELIMINAR") and es_solo_consulta:
                            respuesta_visible = "Tu perfil solo puede hacer consultas, no cambios en el inventario."
                        elif accion == "AGREGAR":
                            nombre_nuevo = str(datos.get("Producto", "")).strip()
                            if not nombre_nuevo:
                                respuesta_visible = "Necesito el nombre del producto para agregarlo."
                            elif nombre_nuevo.lower() in st.session_state.df["Producto"].str.lower().values:
                                respuesta_visible = f"'{nombre_nuevo}' ya existe en el inventario."
                            else:
                                nueva_fila = pd.DataFrame([{
                                    "Código": limpiar_codigo(datos.get("Código", "")),
                                    "Producto": nombre_nuevo,
                                    "Precio Venta": float(datos.get("Precio Venta") or 0.0),
                                    "Stock Actual": int(datos.get("Stock Actual") or 0),
                                    "Stock Mínimo": int(datos.get("Stock Mínimo") or 5),
                                    "Fecha Vencimiento": str(datos.get("Fecha Vencimiento") or "")
                                }])
                                st.session_state.df = pd.concat([st.session_state.df, nueva_fila], ignore_index=True)
                                with st.spinner("Guardando en Google Sheets..."):
                                    guardar_inventario(st.session_state.df)
                        elif accion in ("MODIFICAR", "ELIMINAR"):
                            nombre_exacto, error = buscar_producto_unico(st.session_state.df, datos.get("Producto"))
                            if error:
                                respuesta_visible = error
                            elif accion == "ELIMINAR":
                                stock = int(st.session_state.df[st.session_state.df["Producto"] == nombre_exacto].iloc[0]["Stock Actual"])
                                desc = f"Eliminar '{nombre_exacto}' del inventario (stock actual: {stock})"
                                st.session_state.accion_pendiente = {"accion": "ELIMINAR", "producto": nombre_exacto, "cambios": {}, "descripcion": desc}
                                respuesta_visible = f"{desc}. ¿Confirmás?"
                            else:
                                cambios = {}
                                if datos.get("Precio Venta") is not None:
                                    cambios["Precio Venta"] = float(datos["Precio Venta"])
                                if datos.get("Stock Actual") is not None:
                                    cambios["Stock Actual"] = int(datos["Stock Actual"])
                                if datos.get("Stock Mínimo") is not None:
                                    cambios["Stock Mínimo"] = int(datos["Stock Mínimo"])
                                if datos.get("Fecha Vencimiento"):
                                    cambios["Fecha Vencimiento"] = str(datos["Fecha Vencimiento"])
                                if not cambios:
                                    respuesta_visible = "No entendí qué querés cambiar. ¿Me lo repetís?"
                                else:
                                    detalle = ", ".join(f"{k} → {v}" for k, v in cambios.items())
                                    desc = f"Modificar '{nombre_exacto}': {detalle}"
                                    st.session_state.accion_pendiente = {"accion": "MODIFICAR", "producto": nombre_exacto, "cambios": cambios, "descripcion": desc}
                                    respuesta_visible = f"{desc}. ¿Confirmás?"
                    elif response.status_code == 503:
                        respuesta_visible = "Servidores saturados. Esperá un momento."
                    elif response.status_code == 429:
                        respuesta_visible = "Límite de la API alcanzado. Esperá 60 segundos."
                    elif response.status_code == 404:
                        respuesta_visible = f"Error 404: el modelo '{modelo_gemini}' ya no está disponible. Cambiá GEMINI_MODEL en secrets.toml."
                    else:
                        respuesta_visible = f"Error {response.status_code}."
                except Exception as e:
                    respuesta_visible = f"Error: {str(e)}"
        st.session_state.historial_chat.append({"role": "assistant", "content": respuesta_visible})
        st.rerun()

# ==========================================
# PESTAÑA 6: ADMIN (SOLO JEFE)
# ==========================================
if st.session_state.rol == "jefe" and tab_admin:
    with tab_admin:
        encabezado("sliders", "Administración", "Perfiles y resumen")
        st.markdown("#### Perfiles")
        for perfil in PERFILES:
            st.markdown(f"- **{perfil['nombre']}** — rol: `{perfil['rol']}`")
        st.markdown("---")
        st.markdown("#### Resumen")
        df_admin = st.session_state.df
        col_a1, col_a2 = st.columns(2)
        with col_a1:
            st.metric("Total productos", len(df_admin))
        with col_a2:
            if not df_admin.empty:
                valor = (pd.to_numeric(df_admin["Precio Venta"], errors='coerce').fillna(0) *
                         pd.to_numeric(df_admin["Stock Actual"], errors='coerce').fillna(0)).sum()
                st.metric("Valor del inventario", f"${valor:,.0f}")

# ==========================================
# AUDIO
# ==========================================
if st.session_state.sonido_a_reproducir:
    emitir_sonido_navegador(st.session_state.sonido_a_reproducir)
    st.session_state.sonido_a_reproducir = None