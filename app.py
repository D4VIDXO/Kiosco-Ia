import streamlit as st
import pandas as pd
import os
import hmac
import hashlib
import uuid
import math
from html import escape as esc
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

# ── PWA: manifest + meta tags para "Agregar a pantalla de inicio" ──
st.markdown("""
<link rel="manifest" href="app/static/manifest.json">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="Kiosco">
<meta name="theme-color" content="#080C14">
<link rel="apple-touch-icon" href="app/static/icon-192.png">
<style>
/* En modo standalone (instalado) ocultar la barra de Streamlit */
@media all and (display-mode: standalone) {
    [data-testid="stHeader"] { display: none !important; }
    .main .block-container,
    [data-testid="stMainBlockContainer"] { padding-top: 20px !important; }
}
</style>
""", unsafe_allow_html=True)

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


ICONOS.update({
    "usuarios": '<circle cx="9" cy="8.5" r="3.2"/><path d="M3.5 19a5.5 5.5 0 0 1 11 0"/><circle cx="17.2" cy="9.5" r="2.4"/><path d="M16.5 14.2A4.6 4.6 0 0 1 20.5 19"/>',
    "usuario": '<circle cx="12" cy="8.5" r="3.5"/><path d="M4.5 20a7.5 7.5 0 0 1 15 0"/>',
    "grafico": '<path d="M4 19.5h16"/><rect x="5.5" y="11" width="3" height="6.5" rx="1"/><rect x="10.5" y="6.5" width="3" height="11" rx="1"/><rect x="15.5" y="9" width="3" height="8.5" rx="1"/>',
    "moneda": '<circle cx="12" cy="12" r="8.5"/><path d="M14.8 9.2c-.5-.8-1.5-1.2-2.8-1.2-1.6 0-2.8.8-2.8 2s1.1 1.7 2.8 2 2.8.8 2.8 2-1.2 2-2.8 2c-1.3 0-2.4-.5-2.9-1.4M12 6.5V8M12 16v1.5"/>',
    "usuario_mas": '<circle cx="9.5" cy="8.5" r="3.2"/><path d="M3.5 19a6 6 0 0 1 12 0M18.5 8.5v6M15.5 11.5h6"/>',
    "calendario": '<rect x="4" y="5.5" width="16" height="14.5" rx="2.5"/><path d="M4 10h16M8 3.5v4M16 3.5v4"/>',
})

# Marca: la "K" de la referencia, con las esquinas redondeadas
MARCA = ('<svg viewBox="0 0 24 24" aria-hidden="true"><defs><linearGradient id="kgrad" x1="0" y1="0" x2="1" y2="1">'
         '<stop offset="0" stop-color="#EAF2FF"/><stop offset="1" stop-color="#5E93FF"/></linearGradient></defs>'
         '<path d="M1.25 3.33L1.32 20.37Q1.32 21.57 2.03 20.60L13.07 5.34Q13.78 4.37 14.98 4.35L17.03 4.32Q18.23 4.30 18.12 4.62L18.10 4.68Q18.00 5.01 17.30 5.98L13.62 11.07Q12.92 12.04 13.62 13.01L17.60 18.54Q18.30 19.52 17.10 19.54L15.05 19.57Q13.85 19.59 13.15 18.62L11.30 16.08Q10.60 15.10 9.94 16.03L9.83 16.19Q9.18 17.12 9.89 18.09L11.94 20.83Q12.65 21.80 13.85 21.81L21.55 21.90Q22.75 21.91 22.05 20.93L16.42 13.01Q15.72 12.04 16.41 11.06L22.02 3.07Q22.71 2.09 21.51 2.09L13.85 2.09Q12.65 2.09 11.95 3.06L4.27 13.68Q3.57 14.65 3.56 13.45L3.47 5.57Q3.46 4.37 4.66 4.34L5.51 4.32Q6.71 4.30 7.44 3.35L7.66 3.08Q8.39 2.13 7.19 2.13L2.45 2.13Q1.25 2.13 1.25 3.33Z" fill="url(#kgrad)" fill-rule="evenodd"/></svg>')


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
    """Tarjeta de indicador. Los enteros se animan contando desde cero."""
    if isinstance(valor, int):
        v = f'<div class="kpi-valor num" style="--n:{valor}" aria-label="{valor}"></div>'
    else:
        v = f'<div class="kpi-valor moneda">{valor}</div>'
    return (f'<div class="kpi" style="--acento:{color}"><div class="kpi-ico">{svg(nombre)}</div>'
            f'<div><div class="kpi-label">{etiqueta}</div>{v}</div></div>')



SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

COLUMNAS_INV = ["Código", "Producto", "Precio Venta", "Stock Actual", "Stock Mínimo", "Fecha Vencimiento"]
HOJA_INVENTARIO = "Inventario"
HOJA_VENTAS = "Ventas_Turno"
HOJA_USUARIOS = "Usuarios"
HOJA_HISTORIAL = "Ventas_Historial"
COLS_USUARIOS = ["ID", "Nombre", "Rol", "PIN"]
COLS_HIST = ["Fecha", "Hora", "Ticket", "Código", "Producto", "Precio", "Cantidad", "Total", "Responsable"]
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


@st.cache_data(ttl=60, show_spinner=False)
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


@st.cache_data(ttl=60, show_spinner=False)
def listar_hojas_cierres():
    """Lista las hojas de cierres (excluye Inventario y Ventas_Turno)."""
    try:
        libro = conectar_sheets()
        if not libro:
            return []
        return [h.title for h in libro.worksheets() if h.title not in (HOJA_INVENTARIO, HOJA_VENTAS, HOJA_USUARIOS, HOJA_HISTORIAL)]
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
# HISTORIAL DE VENTAS (para las estadísticas)
# ==========================================
def guardar_historial_sheets(items, responsable):
    """Registra cada línea vendida en un historial permanente."""
    try:
        libro = conectar_sheets()
        if not libro:
            return False
        try:
            hoja = libro.worksheet(HOJA_HISTORIAL)
        except gspread.WorksheetNotFound:
            hoja = libro.add_worksheet(title=HOJA_HISTORIAL, rows=5000, cols=len(COLS_HIST))
            hoja.append_row(COLS_HIST)
        fecha = datetime.now().strftime("%Y-%m-%d")
        filas = [[fecha, str(i["Hora Ticket"]), int(i["Ticket"]), limpiar_codigo(i["Código"]), str(i["Producto"]),
                  float(i["Precio"]), int(i["Cantidad"]), float(i["Total"]), str(responsable)] for i in items]
        hoja.append_rows(filas, value_input_option="RAW")
        return True
    except Exception as e:
        print(f"No se pudo guardar el historial: {e}")
        return False


@st.cache_data(ttl=300, show_spinner=False)
def cargar_historial_ventas():
    """Devuelve el historial de ventas como DataFrame (vacío si todavía no hay)."""
    vacio_df = pd.DataFrame(columns=COLS_HIST)
    try:
        libro = conectar_sheets()
        if not libro:
            return vacio_df
        hoja = libro.worksheet(HOJA_HISTORIAL)
        datos = hoja.get_all_records()
        if not datos:
            return vacio_df
        df = pd.DataFrame(datos)
        for c in COLS_HIST:
            if c not in df.columns:
                df[c] = ""
        df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce")
        df["Precio"] = pd.to_numeric(df["Precio"], errors="coerce").fillna(0.0)
        df["Cantidad"] = pd.to_numeric(df["Cantidad"], errors="coerce").fillna(0).astype(int)
        df["Total"] = pd.to_numeric(df["Total"], errors="coerce").fillna(0.0)
        df["Hora"] = df["Hora"].astype(str)
        df["Producto"] = df["Producto"].astype(str)
        return df.dropna(subset=["Fecha"])
    except Exception:
        return vacio_df


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
ROLES = ["jefe", "encargado", "trabajador"]
ROL_INFO = {
    "jefe":       {"nombre": "Jefe",       "plural": "Jefes",        "icono": "corona",  "color": "#8FB4FF", "desc": "Administración completa"},
    "encargado":  {"nombre": "Encargado",  "plural": "Encargados",   "icono": "llave",   "color": "#5CC8E8", "desc": "Caja, inventario y cierres"},
    "trabajador": {"nombre": "Trabajador", "plural": "Trabajadores", "icono": "carrito", "color": "#7FD6B2", "desc": "Caja y consultas"},
}

for _k, _v in {"usuario_id": None, "usuarios": []}.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v


def pines_configurados():
    """PIN iniciales opcionales en st.secrets['PINES'] (solo se usan la primera vez)."""
    try:
        return {k: str(v) for k, v in dict(st.secrets["PINES"]).items()}
    except Exception:
        return {}


def hash_pin(pin, salt=None):
    salt = salt or os.urandom(16).hex()
    h = hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), bytes.fromhex(salt), 120_000).hex()
    return f"{salt}${h}"


def verificar_hash(pin, almacenado):
    try:
        salt, h = str(almacenado).split("$")
        return hmac.compare_digest(hash_pin(pin, salt).split("$")[1], h)
    except Exception:
        return False


def pin_valido(pin):
    return pin.isdigit() and 4 <= len(pin) <= 8


def nuevo_id():
    return "u" + uuid.uuid4().hex[:8]


def ordenar_usuarios(usuarios):
    return sorted(usuarios, key=lambda u: (ROLES.index(u["rol"]), u["nombre"].lower()))


def obtener_hoja_usuarios(libro):
    try:
        return libro.worksheet(HOJA_USUARIOS)
    except gspread.WorksheetNotFound:
        hoja = libro.add_worksheet(title=HOJA_USUARIOS, rows=200, cols=len(COLS_USUARIOS))
        hoja.append_row(COLS_USUARIOS)
        return hoja


def cargar_usuarios():
    """Lee las personas desde Google Sheets. Devuelve None si no se pudo leer."""
    try:
        libro = conectar_sheets()
        if not libro:
            return None
        hoja = obtener_hoja_usuarios(libro)
        usuarios = []
        for r in hoja.get_all_records():
            rol = str(r.get("Rol", "")).strip().lower()
            nombre = str(r.get("Nombre", "")).strip()
            if rol in ROLES and nombre and str(r.get("PIN", "")).strip():
                usuarios.append({"id": str(r.get("ID", "")).strip() or nuevo_id(), "nombre": nombre,
                                 "rol": rol, "pin": str(r["PIN"]).strip()})
        return ordenar_usuarios(usuarios)
    except Exception as e:
        print(f"Error leyendo usuarios: {e}")
        return None


def guardar_usuarios(usuarios):
    try:
        libro = conectar_sheets()
        if not libro:
            return False
        hoja = obtener_hoja_usuarios(libro)
        filas = [COLS_USUARIOS] + [[u["id"], u["nombre"], u["rol"], u["pin"]] for u in ordenar_usuarios(usuarios)]
        hoja.clear()
        hoja.append_rows(filas, value_input_option="RAW")
        return True
    except Exception as e:
        st.error(f"No se pudo guardar el equipo: {e}")
        return False


def pantalla_configuracion_inicial():
    """Primera vez: crea el usuario Jefe."""
    md_html(f'<div class="login-head"><div class="login-logo">{MARCA}</div><div class="hero-tag">Primera vez</div>'
            '<div class="login-title">Creá tu usuario</div>'
            '<div class="login-sub">Va a ser el Jefe: después podrás agregar al resto del equipo</div></div>')
    _, centro, _ = st.columns([1, 1.3, 1])
    with centro:
        with st.form("form_inicial"):
            nombre = st.text_input("Tu nombre")
            pin = st.text_input("PIN (4 a 8 números)", type="password")
            pin2 = st.text_input("Repetí el PIN", type="password")
            enviar = st.form_submit_button("Crear y continuar", type="primary", use_container_width=True)
        if enviar:
            if not nombre.strip():
                st.error("Escribí tu nombre.")
            elif not pin_valido(pin):
                st.error("El PIN debe tener entre 4 y 8 números.")
            elif pin != pin2:
                st.error("Los PIN no coinciden.")
            elif guardar_usuarios([{"id": nuevo_id(), "nombre": nombre.strip(), "rol": "jefe", "pin": hash_pin(pin)}]):
                st.rerun()
    st.stop()


def crear_usuarios_iniciales():
    """Si hay PIN en secrets.toml, crea un usuario por cada rol con ese PIN."""
    pines = pines_configurados()
    usuarios = [{"id": nuevo_id(), "nombre": ROL_INFO[r]["nombre"], "rol": r, "pin": hash_pin(pines[r])}
                for r in ROLES if pines.get(r)]
    if usuarios and guardar_usuarios(usuarios):
        return ordenar_usuarios(usuarios)
    return []


if not st.session_state.autenticado:
    st.markdown("<br>", unsafe_allow_html=True)
    usuarios = cargar_usuarios()
    if usuarios is None:
        st.error("No se pudo leer la lista de personas. Revisá la conexión con Google Sheets.")
        st.stop()
    if not usuarios:
        usuarios = crear_usuarios_iniciales()
        if not usuarios:
            pantalla_configuracion_inicial()
    st.session_state.usuarios = usuarios

    elegido = next((u for u in usuarios if u["id"] == st.session_state.perfil_pendiente), None)
    if elegido is None:
        st.session_state.perfil_pendiente = None
        md_html(f'<div class="login-head"><div class="login-logo">{MARCA}</div><div class="hero-tag">Kiosco</div>'
                '<div class="login-title">¿Quién está usando el sistema?</div>'
                '<div class="login-sub">Seleccioná tu perfil para continuar</div></div>')
        for ini in range(0, len(usuarios), 3):
            cols = st.columns(3)
            for col, u in zip(cols, usuarios[ini:ini + 3]):
                info = ROL_INFO[u["rol"]]
                with col:
                    md_html(f'<div class="perfil-card" style="--acento:{info["color"]}">'
                            f'<div class="perfil-anillo">{svg(info["icono"])}</div>'
                            f'<div class="perfil-nombre">{esc(u["nombre"])}</div>'
                            f'<div class="perfil-desc">{info["nombre"]}</div></div>')
                    if st.button("Entrar", key=f"btn_{u['id']}", use_container_width=True):
                        st.session_state.perfil_pendiente = u["id"]
                        st.rerun()
    else:
        info = ROL_INFO[elegido["rol"]]
        md_html(f'<div class="perfil-anillo pin-anillo" style="--acento:{info["color"]}">{svg(info["icono"])}</div>'
                f'<div class="pin-nombre">{esc(elegido["nombre"])}</div><div class="pin-sub">Ingresá tu PIN</div>')
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
                    if verificar_hash(pin, elegido["pin"]):
                        st.session_state.autenticado = True
                        st.session_state.usuario_id = elegido["id"]
                        st.session_state.rol = elegido["rol"]
                        st.session_state.nombre_usuario = elegido["nombre"]
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
    st.stop()

# ==========================================
# INTERFAZ PRINCIPAL
# ==========================================
DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
saludo = "Buen día" if hoy.hour < 12 else "Buenas tardes" if hoy.hour < 20 else "Buenas noches"
fecha_txt = f"{DIAS[hoy.weekday()]} {hoy.day} de {MESES[hoy.month - 1]}"
nombre_u = st.session_state.nombre_usuario
rol_u = ROL_INFO.get(st.session_state.rol, ROL_INFO["trabajador"])

col_titulo, col_usuario = st.columns([3, 1])
with col_titulo:
    md_html(f'<div class="hero-card"><div class="anillos"></div><div class="hero-marca"><div class="hero-logo">{MARCA}</div>'
            f'<div><div class="hero-tag">{fecha_txt}</div><div class="hero-title">Kiosco</div>'
            f'<div class="hero-saludo">{saludo}, {esc(nombre_u)}</div></div></div></div>')
with col_usuario:
    md_html(f'<div class="user-chip"><div class="user-avatar">{esc(nombre_u[:1].upper())}</div>'
            f'<div><div class="user-name">{esc(nombre_u)}</div>'
            f'<div class="user-role"><span class="dot"></span>{rol_u["nombre"]}</div></div></div>')
    if st.button("Cerrar sesión", use_container_width=True):
        st.session_state.autenticado = False
        st.session_state.usuario_id = None
        st.session_state.rol = None
        st.session_state.nombre_usuario = ""
        st.session_state.perfil_pendiente = None
        st.session_state.accion_pendiente = None
        st.rerun()

tabs_base = ["Caja", "Inventario", "Nuevo producto", "Alertas", "Asistente IA"]
if st.session_state.rol == "jefe":
    tabs_base.append("Administración")
tabs_resultado = st.tabs(tabs_base)

st.markdown("---")
encabezado("caja", "Estado general", "Resumen del inventario")
productos_faltantes = 0
productos_vencidos = 0
if not df_actual.empty:
    productos_faltantes = int(len(df_actual[df_actual["Stock Actual"] <= df_actual["Stock Mínimo"]]))
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
        md_html(kpi_html("caja", "Productos", int(len(df_actual)), "#8FB4FF"))
    with col2:
        md_html(kpi_html("baja", "A reponer", productos_faltantes, "#F0B04E"))
    with col3:
        md_html(kpi_html("calendario_x", "Vencidos", productos_vencidos, "#FF6B7A"))
st.markdown("<br>", unsafe_allow_html=True)
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


def vender_item_directo(codigo_leido, df):
    """Registra UNA unidad como vendida al instante (modo trabajador/encargado)."""
    codigos_limpios = df["Código"].astype(str).str.replace(r'\.0$', '', regex=True)
    match = df[codigos_limpios == codigo_leido]
    if match.empty:
        st.toast(f"Código '{codigo_leido}' no registrado.")
        st.session_state.sonido_a_reproducir = "error"
        return
    idx = match.index[0]
    producto = df.at[idx, "Producto"]
    stock_disp = int(df.at[idx, "Stock Actual"])
    precio = float(df.at[idx, "Precio Venta"])
    if stock_disp < 1:
        st.toast(f"Sin stock de '{producto}'")
        st.session_state.sonido_a_reproducir = "error"
        return
    hora_now = datetime.now().strftime("%H:%M:%S")
    item = {
        "Ticket": st.session_state.numero_ticket,
        "Hora Ticket": hora_now,
        "Hora": hora_now,
        "Código": codigo_leido,
        "Producto": producto,
        "Precio": precio,
        "Cantidad": 1,
        "Total": precio,
    }
    ok_stock, err = descontar_stock_sheets([item])
    if not ok_stock:
        st.toast(f"Error de stock: {err}")
        st.session_state.sonido_a_reproducir = "error"
        return
    guardar_ticket_sheets([item])
    guardar_historial_sheets([item], st.session_state.nombre_usuario)
    st.session_state.ventas_del_dia.append(item)
    st.session_state.numero_ticket += 1
    # Refrescar el df local para que el stock baje visualmente
    st.session_state.df = cargar_inventario()
    st.toast(f"✓ Vendido: {producto}  ${precio:,.2f}")
    st.session_state.sonido_a_reproducir = "exito"


def procesar_escaneo():
    codigo_leido = st.session_state.input_escanner.strip()
    if codigo_leido:
        df = st.session_state.df
        rol = st.session_state.rol
        if rol in ("trabajador", "encargado"):
            # Modo directo: vende al instante, sin carrito
            vender_item_directo(codigo_leido, df)
        else:
            # Modo carrito (jefe): acumula y cobra al final
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

    # Input del escáner: visible y simple.
    st.text_input(
        "Código de barras",
        key="input_escanner",
        on_change=procesar_escaneo,
        placeholder="Escaneá un producto...",
    )

    # ── MODO DIRECTO (trabajador / encargado) ─────────────────
    if st.session_state.rol in ("trabajador", "encargado"):
        col_ventas, col_cierre = st.columns([2, 1])
        with col_ventas:
            st.markdown("#### Ventas del turno")
            if st.session_state.ventas_del_dia:
                df_ventas = pd.DataFrame(st.session_state.ventas_del_dia)
                for (ticket, hora_t), grupo in df_ventas.groupby(["Ticket", "Hora Ticket"]):
                    detalle = ", ".join(f"{int(r.Cantidad)}x {r.Producto}" for r in grupo.itertuples())
                    total_ticket = grupo["Total"].sum()
                    articulos = int(grupo["Cantidad"].sum())
                    md_html(f'<div class="ticket" style="--acento:#8FB4FF"><div class="ticket-main"><div class="ticket-ico">{svg("ticket")}</div>'
                            f'<div><div class="ticket-meta">Ticket {int(ticket)} · {hora_t}</div>'
                            f'<div class="ticket-detalle">{detalle}</div></div></div>'
                            f'<div><div class="ticket-total">${total_ticket:,.0f}</div>'
                            f'<div class="ticket-cant">{articulos} artículo{"s" if articulos > 1 else ""}</div></div></div>')
                total_acumulado = df_ventas["Total"].sum()
                md_html(f'<div class="total-caja"><div class="total-label">Total en caja</div><div class="total-monto">${total_acumulado:,.2f}</div></div>')
            else:
                vacio("escaner", "Sin ventas aún", "Escaneá el primer producto para registrar una venta")
        with col_cierre:
            st.markdown("#### Cierre de caja")
            if st.session_state.ventas_del_dia:
                df_ventas = pd.DataFrame(st.session_state.ventas_del_dia)
                total_caja = df_ventas["Total"].sum()
                articulos_totales = df_ventas["Cantidad"].sum()
                if st.button("Hacer cierre de caja", type="primary", use_container_width=True):
                    fecha_legible = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
                    df_agrupado_prod = df_ventas.groupby("Producto")["Cantidad"].sum().reset_index()
                    detalle = ", ".join([f"{r['Producto']} (x{r['Cantidad']})" for _, r in df_agrupado_prod.iterrows()])
                    with st.spinner("Guardando cierre..."):
                        ok = guardar_cierre_sheets(fecha_legible, st.session_state.nombre_usuario, total_caja, articulos_totales, detalle)
                        if ok:
                            limpiar_ventas_turno()
                    if ok:
                        st.session_state.ventas_del_dia = []
                        st.session_state.numero_ticket = 1
                        listar_hojas_cierres.clear()
                        cargar_cierres_sheets.clear()
                        st.toast("Cierre de caja guardado")
                        st.rerun()
            else:
                st.caption("Sin ventas para cerrar.")

    # ── MODO CARRITO (jefe) ───────────────────────────────────
    else:
        col_tabla, col_cierre = st.columns([2, 1])
        with col_tabla:
            st.markdown("#### Venta en curso")
            if st.session_state.carrito_actual:
                try:
                    contenedor_carrito = st.container(height=270, key="carrito")
                except TypeError:
                    contenedor_carrito = st.container(height=270)
                with contenedor_carrito:
                    c_hora, c_prod, c_menos, c_cant, c_mas, c_prec, c_accion = st.columns([1.1, 2.8, 0.6, 0.7, 0.6, 1.6, 0.6])
                    c_hora.markdown("**Hora**"); c_prod.markdown("**Producto**")
                    c_menos.markdown("** **"); c_cant.markdown("**Cant**")
                    c_mas.markdown("** **"); c_prec.markdown("**Total**"); c_accion.markdown("** **")
                    st.markdown("---")
                    for i in reversed(range(len(st.session_state.carrito_actual))):
                        item = st.session_state.carrito_actual[i]
                        ch, cp, cmenos, ccant, cmas, cpr, ca = st.columns([1.1, 2.8, 0.6, 0.7, 0.6, 1.6, 0.6])
                        ch.write(f"{item['Hora']}")
                        cp.write(item['Producto'])
                        if cmenos.button("−", key=f"btn_menos_{i}", use_container_width=True):
                            if item["Cantidad"] > 1:
                                st.session_state.carrito_actual[i]["Cantidad"] -= 1
                                st.session_state.carrito_actual[i]["Total"] = item["Precio"] * st.session_state.carrito_actual[i]["Cantidad"]
                                st.rerun()
                            else:
                                cancelar_producto(i)
                        ccant.markdown(f"<div class='cant-num'>{item['Cantidad']}</div>", unsafe_allow_html=True)
                        if cmas.button("+", key=f"btn_mas_{i}", use_container_width=True):
                            _df = st.session_state.df
                            _cl = _df["Código"].astype(str).str.replace(r'\.0$', '', regex=True)
                            _m = _df[_cl == item["Código"]]
                            if not _m.empty:
                                if item["Cantidad"] < _m.iloc[0]["Stock Actual"]:
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
                        ok_stock, error_stock = descontar_stock_sheets(st.session_state.carrito_actual)
                    if not ok_stock:
                        st.error(f"{error_stock}")
                        st.session_state.df = cargar_inventario()
                    else:
                        st.session_state.df = cargar_inventario()
                        for item in st.session_state.carrito_actual:
                            item["Ticket"] = st.session_state.numero_ticket
                            item["Hora Ticket"] = hora_ticket
                        if not guardar_ticket_sheets(st.session_state.carrito_actual):
                            st.warning("La venta se cobró pero el ticket no se pudo respaldar en Sheets.")
                        guardar_historial_sheets(st.session_state.carrito_actual, st.session_state.nombre_usuario)
                        cargar_historial_ventas.clear()
                        st.session_state.ventas_del_dia.extend(st.session_state.carrito_actual)
                        st.session_state.carrito_actual = []
                        st.session_state.numero_ticket += 1
                        st.toast("¡Venta cobrada!")
                        st.rerun()
            else:
                vacio("escaner", "Esperando escaneo", "Pasá el lector por un producto para empezar la venta")

            md_html('<div style="margin:20px 0 14px;padding-top:4px;border-top:1px solid var(--line-soft);"><span style="font-size:1rem;font-weight:500;color:var(--sky);">Ventas del turno</span></div>')
            if st.session_state.ventas_del_dia:
                df_ventas = pd.DataFrame(st.session_state.ventas_del_dia)
                for (ticket, hora_t), grupo in df_ventas.groupby(["Ticket", "Hora Ticket"]):
                    detalle = ", ".join(f"{int(r.Cantidad)}x {r.Producto}" for r in grupo.itertuples())
                    total_ticket = grupo["Total"].sum()
                    articulos = int(grupo["Cantidad"].sum())
                    md_html(f'<div class="ticket" style="--acento:#8FB4FF"><div class="ticket-main"><div class="ticket-ico">{svg("ticket")}</div><div><div class="ticket-meta">Ticket {int(ticket)} · {hora_t}</div><div class="ticket-detalle">{detalle}</div></div></div><div><div class="ticket-total">${total_ticket:,.0f}</div><div class="ticket-cant">{articulos} artículo{"s" if articulos > 1 else ""}</div></div></div>')
                total_acumulado = df_ventas["Total"].sum()
                md_html(f'<div class="total-caja"><div class="total-label">Total en caja</div><div class="total-monto">${total_acumulado:,.2f}</div></div>')
            else:
                st.caption("Sin ventas cerradas en este turno.")

        with col_cierre:
            st.markdown("#### Cierre de caja")
            if st.session_state.ventas_del_dia:
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
                        listar_hojas_cierres.clear()
                        cargar_cierres_sheets.clear()
                        st.toast("Cierre de caja guardado")
                        st.rerun()
            else:
                st.caption("No hay ventas abiertas para cerrar en este turno.")

            st.markdown("---")
            encabezado("calendario", "Historial de cierres", "Cierres guardados por mes")
            hojas = listar_hojas_cierres()
            if hojas:
                col_mes, col_cant = st.columns([2, 1])
                with col_mes:
                    hoja_sel = st.selectbox("Mes:", options=hojas[::-1], index=0, label_visibility="collapsed")
                with col_cant:
                    filas_visibles = st.selectbox("Mostrar:", options=[5, 10, 25, 50], index=1, label_visibility="collapsed")
                with st.spinner("Cargando..."):
                    df_hist = cargar_cierres_sheets(hoja_sel)
                if not df_hist.empty:
                    registros = df_hist.iloc[::-1].head(filas_visibles).to_dict("records")
                    for reg in registros:
                        fecha_hora = str(reg.get("Fecha y Hora", "—"))
                        responsable = str(reg.get("Responsable", "—"))
                        total = reg.get("Total Recaudado ($)", 0)
                        articulos = reg.get("Artículos Vendidos", 0)
                        detalle = str(reg.get("Detalle de Productos", ""))
                        try:
                            total_fmt = f"${float(total):,.2f}"
                        except Exception:
                            total_fmt = str(total)
                        detalle_html = ""
                        if detalle and detalle != "nan":
                            items_det = detalle.split(" | ")
                            items_li = "".join(f"<li>{it.strip()}</li>" for it in items_det if it.strip())
                            detalle_html = f'<ul class="cierre-detalle">{items_li}</ul>'
                        md_html(f'''<div class="cierre-card">
                            <div class="cierre-top">
                                <div class="cierre-fecha">{svg("calendario")}<span>{fecha_hora}</span></div>
                                <div class="cierre-resp">{svg("usuario")}<span>{responsable}</span></div>
                            </div>
                            <div class="cierre-stats">
                                <div class="cierre-stat">
                                    <div class="cierre-stat-val">{total_fmt}</div>
                                    <div class="cierre-stat-lbl">Recaudado</div>
                                </div>
                                <div class="cierre-stat">
                                    <div class="cierre-stat-val">{articulos}</div>
                                    <div class="cierre-stat-lbl">Artículos</div>
                                </div>
                            </div>
                            {detalle_html}
                        </div>''')
                else:
                    vacio("calendario", "Sin cierres", "No hay cierres registrados en este mes.")
            else:
                vacio("calendario", "Sin cierres", "Todavía no se registró ningún cierre de caja.")


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
                color = "#FF6B6B" if item["Días Restantes"] <= 3 else "#E8A24A" if item["Días Restantes"] <= 7 else "#8FB4FF"
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


def procesar_mensaje_ia(prompt_chat, gemini_key):
    """Envía la orden al modelo y devuelve el texto de respuesta para el chat."""
    if not gemini_key:
        return "Ingresá tu API Key de Gemini para operar."
    es_solo_consulta = st.session_state.rol == "trabajador"
    respuesta_visible = "Orden procesada."
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
    return respuesta_visible


def burbuja_html(rol, texto):
    t = esc(texto).replace("\n", "<br>")
    if rol == "user":
        return f'<div class="msg user"><div class="msg-body">{t}</div></div>'
    return f'<div class="msg"><div class="msg-av">{svg("chat")}</div><div class="msg-body">{t}</div></div>'


ESCRIBIENDO_HTML = ('<div class="msg"><div class="msg-av">' + svg("chat") + '</div><div class="msg-body">'
                    '<div class="typing"><span></span><span></span><span></span></div></div></div>')


with tab_ia:
    encabezado("chat", "Asistente operativo", "Consultá o modificá el inventario hablando")
    gemini_key = st.secrets["GEMINI_KEY"] if "GEMINI_KEY" in st.secrets else ""
    if not gemini_key:
        gemini_key = st.text_input("API Key de Gemini", type="password").strip()
    modo_chat = "Solo consultas" if st.session_state.rol == "trabajador" else "Consultas y acciones"

    # ── Encabezado del chat ──────────────────────────────────
    md_html(f'<div class="chat-head"><div class="chat-av">{svg("chat")}</div><div>'
            '<div class="chat-nombre">Asistente Kiosco</div>'
            '<div class="chat-estado"><span class="dot"></span>En línea</div></div>'
            f'<div class="chat-modo">{modo_chat}</div></div>')

    # ── Burbujas de mensajes ─────────────────────────────────
    chat_msgs = st.container(height=380, border=False, key="chat_msgs")

    # ── Confirmación de acciones ─────────────────────────────
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

    # ── Sugerencias rápidas ──────────────────────────────────
    sugerencia = None
    s1, s2, s3 = st.columns(3)
    if s1.button("Stock bajo", key="sug_1", use_container_width=True):
        sugerencia = "¿Qué productos tienen poco stock y conviene reponer?"
    if s2.button("Por vencer", key="sug_2", use_container_width=True):
        sugerencia = "¿Qué productos vencen en los próximos 15 días?"
    if s3.button("Resumen", key="sug_3", use_container_width=True):
        sugerencia = "Haceme un resumen del inventario: cantidad de productos, valor total y qué conviene reponer."

    # ── Input de texto con micrófono ─────────────────────────
    # Usamos st.text_input oculto + JS que lo escucha
    voz_key = "chat_voz_texto"
    if voz_key not in st.session_state:
        st.session_state[voz_key] = ""

    # HTML del campo custom con botón de micrófono
    mic_html = """
<div id="chat-input-wrap">
  <div id="chat-field-row">
    <textarea id="chat-txt" rows="1" placeholder="Escribí o hablá con el asistente..."></textarea>
    <button id="mic-btn" title="Hablar" type="button">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"
           stroke-linecap="round" stroke-linejoin="round">
        <rect x="9" y="2" width="6" height="12" rx="3"/>
        <path d="M5 10a7 7 0 0 0 14 0M12 19v3M9 22h6"/>
      </svg>
    </button>
    <button id="send-btn" title="Enviar" type="button">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"
           stroke-linecap="round" stroke-linejoin="round">
        <path d="M22 2L11 13M22 2L15 22l-4-9-9-4 20-7z"/>
      </svg>
    </button>
  </div>
  <div id="mic-status"></div>
</div>

<style>
  #chat-input-wrap {
    margin: 10px 0 4px;
    font-family: 'Jost', system-ui, sans-serif;
  }
  #chat-field-row {
    display: flex; align-items: flex-end; gap: 8px;
    background: #16213A;
    border: 1.5px solid #1E3058;
    border-radius: 20px;
    padding: 8px 8px 8px 16px;
    transition: border-color .25s;
  }
  #chat-field-row:focus-within {
    border-color: #4A90E2;
    box-shadow: 0 0 0 3px rgba(74,144,226,.15);
  }
  #chat-txt {
    flex: 1; background: transparent; border: none; outline: none; resize: none;
    color: #E8F0FC; font-family: inherit; font-size: .93rem; line-height: 1.5;
    max-height: 120px; overflow-y: auto; padding: 4px 0;
    caret-color: #4A90E2;
  }
  #chat-txt::placeholder { color: #4A6080; }
  #mic-btn, #send-btn {
    width: 38px; height: 38px; border: none; border-radius: 12px; cursor: pointer;
    display: flex; align-items: center; justify-content: center; flex: none;
    transition: transform .15s, background .2s, box-shadow .2s;
  }
  #mic-btn {
    background: rgba(74,144,226,.12);
    color: #7EB3E8;
  }
  #mic-btn:hover { background: rgba(74,144,226,.22); }
  #mic-btn.escuchando {
    background: rgba(255,107,107,.18);
    color: #FF6B6B;
    animation: mic-pulse 1.2s ease-in-out infinite;
  }
  #send-btn {
    background: linear-gradient(135deg,#4A90E2,#1A4A8A);
    color: #fff;
    box-shadow: 0 2px 8px rgba(74,144,226,.35);
  }
  #send-btn:hover { transform: scale(1.08); box-shadow: 0 4px 14px rgba(74,144,226,.5); }
  #send-btn:active { transform: scale(.96); }
  #mic-btn svg, #send-btn svg { width: 18px; height: 18px; }
  #mic-status {
    font-size: .75rem; color: #FF6B6B; margin: 4px 0 0 8px; min-height: 16px;
    transition: opacity .2s;
  }
  @keyframes mic-pulse {
    0%,100% { box-shadow: 0 0 0 0 rgba(255,107,107,.4); }
    50%      { box-shadow: 0 0 0 8px rgba(255,107,107,0); }
  }
</style>

<script>
(function() {
  const txt   = document.getElementById('chat-txt');
  const micBtn = document.getElementById('mic-btn');
  const sendBtn = document.getElementById('send-btn');
  const status = document.getElementById('mic-status');

  /* Auto-resize textarea */
  txt.addEventListener('input', () => {
    txt.style.height = 'auto';
    txt.style.height = Math.min(txt.scrollHeight, 120) + 'px';
  });

  /* Enviar al presionar Enter (sin Shift) */
  txt.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); enviar(); }
  });

  function enviar() {
    const v = txt.value.trim();
    if (!v) return;
    // Envía el texto al DOM padre via postMessage (el script receptor está en el page JS)
    window.parent.postMessage({type: 'chat_send', text: v}, '*');
    txt.value = '';
    txt.style.height = 'auto';
  }

  sendBtn.addEventListener('click', enviar);

  /* Micrófono */
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    micBtn.style.display = 'none';
  } else {
    let escuchando = false;

    micBtn.addEventListener('click', () => {
      if (escuchando) return;

      const rec = new SpeechRecognition();
      rec.lang = 'es-AR';
      rec.interimResults = false;
      rec.maxAlternatives = 1;
      escuchando = true;
      micBtn.classList.add('escuchando');
      status.textContent = '🎙 Escuchando...';

      rec.onresult = (e) => {
        const texto = e.results[0][0].transcript;
        txt.value = txt.value ? txt.value + ' ' + texto : texto;
        txt.style.height = 'auto';
        txt.style.height = Math.min(txt.scrollHeight, 120) + 'px';
      };

      rec.onend = () => {
        escuchando = false;
        micBtn.classList.remove('escuchando');
        status.textContent = '';
      };

      rec.onerror = (e) => {
        escuchando = false;
        micBtn.classList.remove('escuchando');
        status.textContent = e.error === 'not-allowed' ? 'Permiso denegado.' : '';
      };

      rec.start();
    });
  }
})();
</script>
"""

    # Renderizar el campo custom (textarea + micrófono + enviar)
    components.html(mic_html, height=110, scrolling=False)

    # El campo custom envía via postMessage al script receptor en la página padre
    # Este script receptor actualiza el st.text_input oculto y simula Enter
    components.html("""
<script>
(function(){
  if (window._chatListenerReady) return;
  window._chatListenerReady = true;
  window.addEventListener('message', function(e) {
    if (!e.data || e.data.type !== 'chat_send') return;
    const v = e.data.text;
    // Busca el input de Streamlit con la clase específica del key
    const inp = window.parent.document.querySelector('.st-key-chat_envio_key input');
    if (!inp) return;
    // Inyecta el valor via el setter nativo de React
    const nv = Object.getOwnPropertyDescriptor(window.parent.HTMLInputElement.prototype, 'value').set;
    nv.call(inp, v);
    inp.dispatchEvent(new window.parent.Event('input', {bubbles: true}));
    // Presiona Enter después de 20ms para darle tiempo a React
    setTimeout(() => {
      inp.focus();
      inp.dispatchEvent(new window.parent.KeyboardEvent('keydown', {key:'Enter', keyCode:13, which:13, bubbles:true}));
      inp.dispatchEvent(new window.parent.KeyboardEvent('keypress',{key:'Enter', keyCode:13, which:13, bubbles:true}));
      inp.dispatchEvent(new window.parent.KeyboardEvent('keyup',   {key:'Enter', keyCode:13, which:13, bubbles:true}));
    }, 20);
  });
})();
</script>""", height=0)

    # Input oculto de Streamlit — recibe el texto desde JS
    prompt_chat = st.text_input(
        "chat_envio",
        key="chat_envio_key",
        label_visibility="collapsed",
        placeholder="",
    )

    prompt = (prompt_chat or "").strip() or sugerencia
    if prompt:
        st.session_state.accion_pendiente = None  # una orden nueva descarta la pendiente
        st.session_state.historial_chat.append({"role": "user", "content": prompt})

    with chat_msgs:
        if not st.session_state.historial_chat:
            md_html(f'<div class="chat-vacio"><span class="ico">{svg("chat")}</span>'
                    '<div class="t">¿En qué te ayudo?</div>'
                    '<div>Preguntame por el stock, los vencimientos o pedime cambios en el inventario.</div></div>')
        for m in st.session_state.historial_chat:
            md_html(burbuja_html(m["role"], m["content"]))
        escribiendo = st.empty()
        if prompt:
            escribiendo.markdown(ESCRIBIENDO_HTML, unsafe_allow_html=True)

    # Lleva la conversación hasta el último mensaje
    components.html(f"""<script>
    const n = {len(st.session_state.historial_chat)};
    const raiz = window.parent.document.querySelector('.st-key-chat_msgs');
    if (raiz) {{
        const el = [raiz, ...raiz.querySelectorAll('*')].find(e => e.scrollHeight > e.clientHeight + 4 && ['auto', 'scroll'].includes(getComputedStyle(e).overflowY));
        if (el) setTimeout(() => el.scrollTo({{top: el.scrollHeight, behavior: 'smooth'}}), 140);
    }}
    </script>""", height=0)

    if prompt:
        # Limpia el input oculto para que no se reprocese en el siguiente rerun
        st.session_state["chat_envio_key"] = ""
        respuesta = procesar_mensaje_ia(prompt, gemini_key)
        st.session_state.historial_chat.append({"role": "assistant", "content": respuesta})
        st.rerun()

# ==========================================
# PESTAÑA 6: ADMINISTRACIÓN (SOLO JEFE)
# ==========================================
def fmt_dinero(v):
    return f"${v:,.0f}"


def fmt_corto(v):
    if v >= 1_000_000:
        return f"${v / 1_000_000:.1f}M"
    if v >= 10_000:
        return f"${v / 1_000:.0f}k"
    if v >= 1_000:
        return f"${v / 1_000:.1f}k"
    return f"${v:.0f}"


def maximo_redondo(v):
    if v <= 0:
        return 1
    exp = 10 ** math.floor(math.log10(v))
    for m in (1, 2, 2.5, 5, 10):
        if v <= m * exp:
            return m * exp
    return 10 * exp


def grafico_barras(etiquetas, valores, dinero=True, alto=270):
    """Gráfico de barras en SVG, con el estilo de la app (barras animadas y valor al pasar el cursor)."""
    W, H = 720, alto
    ml, mr, mt, mb = 56, 12, 24, 36
    cw, ch = W - ml - mr, H - mt - mb
    n = max(len(valores), 1)
    vmax = maximo_redondo(max(valores) if valores else 0)
    slot = cw / n
    bw = min(slot * 0.58, 46)
    out = [f'<svg class="chart" viewBox="0 0 {W} {H}" role="img" preserveAspectRatio="xMidYMid meet">',
           '<defs><linearGradient id="barGrad" x1="0" y1="0" x2="0" y2="1">'
           '<stop offset="0" stop-color="#9CBBFF"/><stop offset="1" stop-color="#2A56C4"/></linearGradient></defs>']
    for k in range(5):
        y = mt + ch - ch * k / 4
        val = vmax * k / 4
        txt = fmt_corto(val) if dinero else f"{val:.0f}"
        out.append(f'<line class="grid" x1="{ml}" y1="{y:.1f}" x2="{W - mr}" y2="{y:.1f}"/>')
        out.append(f'<text class="eje" x="{ml - 10}" y="{y + 4:.1f}" text-anchor="end">{txt}</text>')
    paso = max(1, math.ceil(n / 12))
    for i, (et, v) in enumerate(zip(etiquetas, valores)):
        x = ml + slot * i + (slot - bw) / 2
        h = ch * v / vmax if vmax else 0
        y = mt + ch - h
        valor_txt = fmt_dinero(v) if dinero else f"{int(v)}"
        tw = max(64, 9 * len(valor_txt) + 18)
        tx = min(max(x + bw / 2 - tw / 2, ml), W - mr - tw)
        ty = max(y - 40, 0)
        barra = (f'<rect class="bar" style="--i:{i}" x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{h:.1f}" '
                 f'rx="{min(8, bw / 2):.1f}" fill="url(#barGrad)"/>') if v > 0 else ""
        out.append(f'<g class="bar-g"><rect x="{ml + slot * i:.1f}" y="{mt}" width="{slot:.1f}" height="{ch}" fill="transparent"/>'
                   f'{barra}<g class="tip"><rect x="{tx:.1f}" y="{ty:.1f}" width="{tw}" height="28" rx="8" fill="#16213A" stroke="#1E3058" stroke-width="1"/>'
                   f'<text x="{tx + tw / 2:.1f}" y="{ty + 18:.1f}" text-anchor="middle" fill="#E8F0FC" font-size="12" font-family="Jost,system-ui,sans-serif" font-weight="500">{valor_txt}</text></g></g>')
        if i % paso == 0:
            out.append(f'<text class="eje" x="{x + bw / 2:.1f}" y="{H - 12}" text-anchor="middle">{esc(str(et))}</text>')
    out.append("</svg>")
    return "".join(out)


def panel_html(titulo, sub, cuerpo):
    return (f'<div class="panel"><div class="panel-head"><div class="panel-titulo">{titulo}</div>'
            f'<div class="panel-sub">{sub}</div></div>{cuerpo}</div>')


def top_productos_html(df_top):
    if df_top.empty:
        return '<div class="panel-vacio">Sin ventas en este período.</div>'
    mayor = df_top["Total"].max() or 1
    filas = []
    for i, r in enumerate(df_top.itertuples(), start=1):
        ancho = max(r.Total / mayor * 100, 4)
        filas.append(f'<div class="top-fila"><div class="top-rank">{i}</div><div class="top-info">'
                     f'<div class="top-nombre">{esc(r.Producto)}</div><div class="top-barra">'
                     f'<div class="top-fill" style="--w:{ancho:.0f}%;--d:{0.08 * i + 0.1:.2f}s"></div></div></div>'
                     f'<div class="top-cifras"><div class="top-monto">{fmt_dinero(r.Total)}</div>'
                     f'<div class="top-unid">{int(r.Cantidad)} u.</div></div></div>')
    return "".join(filas)


def render_estadisticas():
    c1, c2 = st.columns([3, 1])
    with c1:
        periodo = st.segmented_control("Período", ["7 días", "30 días", "90 días"], default="30 días",
                                       key="periodo_stats", label_visibility="collapsed")
    with c2:
        if st.button("Actualizar datos", key="refrescar_stats", use_container_width=True):
            cargar_historial_ventas.clear()
            st.rerun()
    dias = {"7 días": 7, "30 días": 30, "90 días": 90}.get(periodo or "30 días", 30)

    df = cargar_historial_ventas()
    desde = pd.Timestamp(hoy.date()) - pd.Timedelta(days=dias - 1)
    dfp = df[df["Fecha"] >= desde].copy() if not df.empty else df

    recaudado = float(dfp["Total"].sum()) if not dfp.empty else 0.0
    tickets = int(dfp.groupby(["Fecha", "Hora", "Ticket"]).ngroups) if not dfp.empty else 0
    unidades = int(dfp["Cantidad"].sum()) if not dfp.empty else 0
    promedio = recaudado / tickets if tickets else 0.0

    st.markdown("<br>", unsafe_allow_html=True)
    with st.container(key="kpis_ventas"):
        k1, k2, k3, k4 = st.columns(4)
        with k1:
            md_html(kpi_html("moneda", "Recaudado", fmt_dinero(recaudado), "#8FB4FF"))
        with k2:
            md_html(kpi_html("ticket", "Tickets", tickets, "#5CC8E8"))
        with k3:
            md_html(kpi_html("caja", "Unidades vendidas", unidades, "#7FD6B2"))
        with k4:
            md_html(kpi_html("grafico", "Ticket promedio", fmt_dinero(promedio), "#F0B04E"))
    st.markdown("<br>", unsafe_allow_html=True)

    if dfp.empty:
        md_html(panel_html("Ventas", f"Últimos {dias} días",
                           '<div class="panel-vacio">Todavía no hay ventas registradas en este período.<br>'
                           'Las estadísticas se arman con los tickets cobrados desde ahora.</div>'))
    else:
        if dias <= 30:
            idx = pd.date_range(desde, periods=dias, freq="D")
            serie = dfp.groupby("Fecha")["Total"].sum().reindex(idx, fill_value=0.0)
            etiquetas = [d.strftime("%d/%m") for d in idx]
            sub = "Recaudación por día"
        else:
            serie = dfp.set_index("Fecha")["Total"].resample("W").sum()
            etiquetas = [d.strftime("%d/%m") for d in serie.index]
            sub = "Recaudación por semana"
        md_html(panel_html("Ventas en el tiempo", sub, grafico_barras(etiquetas, [float(v) for v in serie.values])))

        top = (dfp.groupby("Producto").agg(Total=("Total", "sum"), Cantidad=("Cantidad", "sum"))
                  .sort_values("Total", ascending=False).head(6).reset_index())
        horas = pd.to_numeric(dfp["Hora"].astype(str).str.slice(0, 2), errors="coerce")
        por_hora = dfp.assign(H=horas).dropna(subset=["H"]).groupby("H")["Total"].sum()
        col_a, col_b = st.columns(2)
        with col_a:
            md_html(panel_html("Productos más vendidos", "Por monto", top_productos_html(top)))
        with col_b:
            if por_hora.empty:
                cuerpo_h = '<div class="panel-vacio">Sin datos de horario.</div>'
            else:
                rango = range(int(por_hora.index.min()), int(por_hora.index.max()) + 1)
                serie_h = por_hora.reindex(rango, fill_value=0.0)
                cuerpo_h = grafico_barras([f"{h:02d}h" for h in rango], [float(v) for v in serie_h.values], alto=300)
            md_html(panel_html("Horarios de mayor venta", "Recaudación por hora", cuerpo_h))

    st.markdown("#### Inventario")
    inv = st.session_state.df
    if inv.empty:
        st.info("El inventario está vacío.")
        return
    precio = pd.to_numeric(inv["Precio Venta"], errors="coerce").fillna(0)
    stock = pd.to_numeric(inv["Stock Actual"], errors="coerce").fillna(0)
    minimo = pd.to_numeric(inv["Stock Mínimo"], errors="coerce").fillna(0)
    with st.container(key="kpis_inventario"):
        i1, i2, i3, i4 = st.columns(4)
        with i1:
            md_html(kpi_html("moneda", "Valor del inventario", fmt_dinero(float((precio * stock).sum())), "#8FB4FF"))
        with i2:
            md_html(kpi_html("caja", "Unidades en stock", int(stock.sum()), "#7FD6B2"))
        with i3:
            md_html(kpi_html("baja", "Stock bajo", int((stock <= minimo).sum()), "#F0B04E"))
        with i4:
            md_html(kpi_html("campana", "Sin stock", int((stock <= 0).sum()), "#FF6B7A"))


def render_equipo():
    usuarios = st.session_state.usuarios
    yo = st.session_state.usuario_id
    cantidad_jefes = sum(1 for u in usuarios if u["rol"] == "jefe")

    st.markdown("<br>", unsafe_allow_html=True)
    for rol in ROLES:
        del_rol = [u for u in usuarios if u["rol"] == rol]
        info = ROL_INFO[rol]
        md_html(f'<div class="equipo-titulo">{info["plural"]} · {len(del_rol)}</div>')
        if not del_rol:
            st.caption("Nadie con este rol todavía.")
        for u in del_rol:
            vos = " · sos vos" if u["id"] == yo else ""
            md_html(f'<div class="persona" style="--acento:{info["color"]}"><div class="persona-av">{esc(u["nombre"][:1].upper())}</div>'
                    f'<div><div class="persona-nombre">{esc(u["nombre"])}</div><div class="persona-sub">{info["desc"]}{vos}</div></div>'
                    f'<div class="persona-tag">{info["nombre"]}</div></div>')

    st.markdown("---")
    col_a, col_b = st.columns(2, gap="large")

    with col_a:
        st.markdown("#### Editar persona")
        opciones = {u["id"]: f'{u["nombre"]} · {ROL_INFO[u["rol"]]["nombre"]}' for u in usuarios}
        sel = st.selectbox("Persona", list(opciones.keys()), format_func=lambda i: opciones[i], key="sel_persona")
        u = next(x for x in usuarios if x["id"] == sel)
        es_yo = u["id"] == yo
        with st.form(f"form_editar_{u['id']}"):
            nuevo_nombre = st.text_input("Nombre", value=u["nombre"])
            nuevo_rol = st.selectbox("Rol", ROLES, index=ROLES.index(u["rol"]),
                                     format_func=lambda r: ROL_INFO[r]["nombre"], disabled=es_yo)
            nuevo_pin = st.text_input("Nuevo PIN (vacío para no cambiarlo)", type="password")
            confirmar = st.checkbox("Confirmo que quiero eliminar a esta persona", disabled=es_yo)
            b1, b2 = st.columns(2)
            guardar = b1.form_submit_button("Guardar cambios", type="primary", use_container_width=True)
            eliminar = b2.form_submit_button("Eliminar", use_container_width=True, disabled=es_yo)
        if es_yo:
            st.caption("No podés cambiar tu propio rol ni eliminarte.")

        if guardar:
            nombre = nuevo_nombre.strip()
            error = None
            if not nombre:
                error = "El nombre no puede estar vacío."
            elif any(x["id"] != u["id"] and x["nombre"].lower() == nombre.lower() for x in usuarios):
                error = "Ya existe una persona con ese nombre."
            elif nuevo_pin and not pin_valido(nuevo_pin):
                error = "El PIN debe tener entre 4 y 8 números."
            elif u["rol"] == "jefe" and nuevo_rol != "jefe" and cantidad_jefes <= 1:
                error = "Tiene que quedar al menos un jefe."
            if error:
                st.error(error)
            else:
                u["nombre"], u["rol"] = nombre, nuevo_rol
                if nuevo_pin:
                    u["pin"] = hash_pin(nuevo_pin)
                if guardar_usuarios(usuarios):
                    if es_yo:
                        st.session_state.nombre_usuario = nombre
                    st.toast("Cambios guardados")
                    st.rerun()
                else:
                    st.session_state.usuarios = cargar_usuarios() or usuarios

        if eliminar:
            if not confirmar:
                st.warning("Marcá la casilla de confirmación para eliminar.")
            elif u["rol"] == "jefe" and cantidad_jefes <= 1:
                st.error("Tiene que quedar al menos un jefe.")
            else:
                restantes = [x for x in usuarios if x["id"] != u["id"]]
                if guardar_usuarios(restantes):
                    st.session_state.usuarios = restantes
                    st.toast("Persona eliminada")
                    st.rerun()

    with col_b:
        st.markdown("#### Agregar persona")
        with st.form("form_agregar_persona", clear_on_submit=True):
            nombre_n = st.text_input("Nombre")
            rol_n = st.selectbox("Rol", ROLES, index=2, format_func=lambda r: ROL_INFO[r]["nombre"])
            pin_n = st.text_input("PIN (4 a 8 números)", type="password")
            agregar = st.form_submit_button("Agregar al equipo", type="primary", use_container_width=True)
        if agregar:
            nombre = nombre_n.strip()
            if not nombre:
                st.error("Escribí el nombre.")
            elif any(x["nombre"].lower() == nombre.lower() for x in usuarios):
                st.error("Ya existe una persona con ese nombre.")
            elif not pin_valido(pin_n):
                st.error("El PIN debe tener entre 4 y 8 números.")
            else:
                nuevos = usuarios + [{"id": nuevo_id(), "nombre": nombre, "rol": rol_n, "pin": hash_pin(pin_n)}]
                if guardar_usuarios(nuevos):
                    st.session_state.usuarios = ordenar_usuarios(nuevos)
                    st.toast(f"{nombre} se sumó al equipo")
                    st.rerun()


if st.session_state.rol == "jefe" and tab_admin:
    with tab_admin:
        encabezado("sliders", "Administración", "Estadísticas del negocio y gestión del equipo")
        vista = st.segmented_control("Vista", ["Estadísticas", "Equipo"], default="Estadísticas",
                                     key="vista_admin", label_visibility="collapsed")
        if vista == "Equipo":
            render_equipo()
        else:
            render_estadisticas()

# ==========================================
# AUDIO
# ==========================================
if st.session_state.sonido_a_reproducir:
    emitir_sonido_navegador(st.session_state.sonido_a_reproducir)
    st.session_state.sonido_a_reproducir = None