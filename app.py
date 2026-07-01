import streamlit as st
import pandas as pd
import os
import gspread
from google.oauth2.service_account import Credentials
import requests
import json
from datetime import datetime
import streamlit.components.v1 as components
import base64

# Configuración de la página web
st.set_page_config(
    page_title="Kiosco",
    page_icon="🏪",
    layout="wide"
)

CARPETA_IMAGENES = "imagenes_productos"
CARPETA_REPORTES = "reportes_cierre"

# Cargar estilos desde archivo externo
with open("estilos.css", encoding="utf-8") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# ==========================================
# 📊 CONEXIÓN GOOGLE SHEETS
# ==========================================
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

@st.cache_resource
def conectar_sheets():
    """Conecta con Google Sheets usando las credenciales de Streamlit Secrets."""
    try:
        creds = Credentials.from_service_account_info(
            st.secrets["gcp_service_account"],
            scopes=SCOPES
        )
        cliente = gspread.authorize(creds)
        sheet_id = st.secrets["SHEET_ID"]
        libro = cliente.open_by_key(sheet_id)
        return libro
    except Exception as e:
        st.error(f"❌ Error conectando con Google Sheets: {e}")
        return None

def obtener_hoja(libro, nombre="Inventario"):
    """Obtiene o crea la hoja de inventario."""
    try:
        try:
            return libro.worksheet(nombre)
        except gspread.WorksheetNotFound:
            hoja = libro.add_worksheet(title=nombre, rows=1000, cols=10)
            hoja.append_row(["Código", "Producto", "Precio Venta", "Stock Actual", "Stock Mínimo", "Fecha Vencimiento"])
            return hoja
    except Exception as e:
        st.error(f"❌ Error obteniendo hoja: {e}")
        return None

def cargar_inventario():
    """Carga el inventario desde Google Sheets."""
    columnas = ["Código", "Producto", "Precio Venta", "Stock Actual", "Stock Mínimo", "Fecha Vencimiento"]
    try:
        libro = conectar_sheets()
        if not libro:
            return pd.DataFrame(columns=columnas)
        hoja = obtener_hoja(libro)
        if not hoja:
            return pd.DataFrame(columns=columnas)
        datos = hoja.get_all_records()
        if not datos:
            return pd.DataFrame(columns=columnas)
        df = pd.DataFrame(datos)
        for col in columnas:
            if col not in df.columns:
                df[col] = ""
        df["Código"] = df["Código"].fillna("").astype(str).str.strip()
        df["Precio Venta"] = pd.to_numeric(df["Precio Venta"], errors='coerce').fillna(0.0)
        df["Stock Actual"] = pd.to_numeric(df["Stock Actual"], errors='coerce').fillna(0).astype(int)
        df["Stock Mínimo"] = pd.to_numeric(df["Stock Mínimo"], errors='coerce').fillna(5).astype(int)
        df["Fecha Vencimiento"] = df["Fecha Vencimiento"].fillna("").astype(str)
        return df
    except Exception as e:
        st.error(f"⚠️ Error cargando inventario: {e}")
        return pd.DataFrame(columns=columnas)

def guardar_inventario(df):
    """Guarda el inventario completo en Google Sheets."""
    try:
        libro = conectar_sheets()
        if not libro:
            return False
        hoja = obtener_hoja(libro)
        if not hoja:
            return False
        hoja.clear()
        encabezados = ["Código", "Producto", "Precio Venta", "Stock Actual", "Stock Mínimo", "Fecha Vencimiento"]
        datos = [encabezados]
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
        return True
    except Exception as e:
        st.error(f"❌ Error guardando inventario: {e}")
        return False

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
        hoja.append_row([fecha_legible, responsable, total_caja, int(articulos_totales), detalle_productos_texto])
        return True
    except Exception as e:
        st.error(f"❌ Error guardando cierre: {e}")
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
    except:
        return pd.DataFrame()

def listar_hojas_cierres():
    """Lista todas las hojas excepto Inventario."""
    try:
        libro = conectar_sheets()
        if not libro:
            return []
        return [h.title for h in libro.worksheets() if h.title != "Inventario"]
    except:
        return []

# ==========================================
# 🖼️ IMÁGENES (Google Drive o local)
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
# 🔊 EFECTOS DE SONIDO
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
    components.html(js_code, height=0, width=0)

# ==========================================
# 🔄 INICIALIZACIÓN DE SESIÓN
# ==========================================
if 'df' not in st.session_state:
    st.session_state.df = cargar_inventario()
if 'numero_ticket' not in st.session_state:
    st.session_state.numero_ticket = 1
if 'carrito_actual' not in st.session_state:
    st.session_state.carrito_actual = []
if 'ventas_del_dia' not in st.session_state:
    st.session_state.ventas_del_dia = []
if 'sonido_a_reproducir' not in st.session_state:
    st.session_state.sonido_a_reproducir = None
if 'historial_chat' not in st.session_state:
    st.session_state.historial_chat = []
if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False
if 'rol' not in st.session_state:
    st.session_state.rol = None
if 'nombre_usuario' not in st.session_state:
    st.session_state.nombre_usuario = ""

hoy = datetime.now()
df_actual = st.session_state.df

# ==========================================
# 🔐 PANTALLA DE LOGIN
# ==========================================
PERFILES = [
    {"rol": "jefe",       "nombre": "Jefe",       "emoji": "👑", "color": "#C9A84C"},
    {"rol": "encargado",  "nombre": "Encargado",  "emoji": "🗝️", "color": "#7EB8F7"},
    {"rol": "trabajador", "nombre": "Trabajador", "emoji": "🛒", "color": "#6BD4A0"},
]

if not st.session_state.autenticado:
    st.markdown("<br><br>", unsafe_allow_html=True)
    st.markdown("<h2 style='text-align:center;font-family:Georgia,serif;color:#F0EDE6;'>¿Quién está usando el sistema?</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align:center;color:#5A5650;font-size:13px;margin-bottom:2rem'>Seleccioná tu perfil para continuar</p>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)
    for col, perfil in zip([col1, col2, col3], PERFILES):
        with col:
            st.markdown(f"""
            <div style='background:#1C1C1C;border:1px solid #2A2A2A;border-radius:12px;padding:2rem 1rem;text-align:center;margin-bottom:0.5rem;'>
                <div style='font-size:3rem;margin-bottom:0.75rem'>{perfil['emoji']}</div>
                <div style='font-size:1rem;font-weight:600;color:{perfil['color']};letter-spacing:0.06em;text-transform:uppercase;'>{perfil['nombre']}</div>
            </div>""", unsafe_allow_html=True)
            if st.button(f"Entrar como {perfil['nombre']}", key=f"btn_{perfil['rol']}", use_container_width=True):
                st.session_state.autenticado = True
                st.session_state.rol = perfil["rol"]
                st.session_state.nombre_usuario = perfil["nombre"]
                st.rerun()
    st.stop()

# ==========================================
# 🏠 INTERFAZ PRINCIPAL
# ==========================================
col_titulo, col_usuario = st.columns([3, 1])
with col_titulo:
    st.title("Kiosco")
    st.subheader("Sistema de Gestión Inteligente")
with col_usuario:
    st.markdown(f"**👤 {st.session_state.nombre_usuario}**")
    st.caption(f"Rol: {st.session_state.rol}")
    if st.button("🔒 Cerrar sesión", use_container_width=True):
        st.session_state.autenticado = False
        st.session_state.rol = None
        st.session_state.nombre_usuario = ""
        st.rerun()

st.markdown("### 📊 Estado General")
col1, col2, col3 = st.columns(3)
productos_faltantes = 0
productos_vencidos = 0
if not df_actual.empty:
    productos_faltantes = len(df_actual[df_actual["Stock Actual"] <= df_actual["Stock Mínimo"]])
    for idx, fila in df_actual.iterrows():
        try:
            fecha_v = datetime.strptime(str(fila["Fecha Vencimiento"]).split()[0], '%Y-%m-%d')
            if (fecha_v - hoy).days < 0:
                productos_vencidos += 1
        except:
            pass
with col1:
    st.metric("Total Productos", len(df_actual))
with col2:
    st.metric("⚠️ A Reponer", productos_faltantes)
with col3:
    st.metric("❌ Vencidos", productos_vencidos)
st.markdown("---")

tabs_base = ["🛒 Caja", "🔍 Inventario", "📥 Nuevo Producto", "🚨 Alertas", "🤖 Asistente IA"]
if st.session_state.rol == "jefe":
    tabs_base.append("⚙️ Administración")
tabs_resultado = st.tabs(tabs_base)
tab_caja      = tabs_resultado[0]
tab_gestion   = tabs_resultado[1]
tab_carga     = tabs_resultado[2]
tab_vencimientos = tabs_resultado[3]
tab_ia        = tabs_resultado[4]
tab_admin     = tabs_resultado[5] if st.session_state.rol == "jefe" else None

# ==========================================
# 🛒 FUNCIONES DE CAJA
# ==========================================
def cancelar_producto(idx_carrito):
    st.session_state.carrito_actual.pop(idx_carrito)
    st.toast("🔄 Producto quitado de la venta.", icon="↩️")
    st.session_state.sonido_a_reproducir = "error"
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
            en_carrito = sum(1 for item in st.session_state.carrito_actual if item["Código"] == codigo_leido)
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
                st.toast(f"📥 Agregado: {producto} (${precio})", icon="🛒")
                st.session_state.sonido_a_reproducir = "exito"
            else:
                st.error(f"🚨 Sin Stock de '{producto}'")
                st.session_state.sonido_a_reproducir = "error"
        else:
            st.warning(f"🔍 Código '{codigo_leido}' no registrado.")
            st.session_state.sonido_a_reproducir = "error"
    st.session_state.input_escanner = ""

# ==========================================
# 🛒 PESTAÑA 1: CAJA
# ==========================================
with tab_caja:
    st.markdown("### ⚡ Punto de Venta")
    st.text_input(
        "👉 Hacé clic acá y pasá el lector por el código de barras:",
        key="input_escanner",
        on_change=procesar_escaneo
    )
    st.markdown("---")
    col_tabla, col_cierre = st.columns([2, 1])
    with col_tabla:
        st.markdown("#### 🛒 Venta en Curso")
        if st.session_state.carrito_actual:
            with st.container(height=270):
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
                    ch.write(f"⏱️ {item['Hora']}")
                    cp.write(item['Producto'])
                    col_menos, col_cant, col_mas = ccant.columns([1, 1, 1])
                    if col_menos.button("−", key=f"btn_menos_{i}", use_container_width=True):
                        if item["Cantidad"] > 1:
                            st.session_state.carrito_actual[i]["Cantidad"] -= 1
                            st.session_state.carrito_actual[i]["Total"] = item["Precio"] * st.session_state.carrito_actual[i]["Cantidad"]
                        else:
                            cancelar_producto(i)
                        st.rerun()
                    col_cant.markdown(f"<div style='text-align:center;padding-top:6px'><b>{item['Cantidad']}</b></div>", unsafe_allow_html=True)
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
                                st.warning(f"🚨 Sin más stock de '{item['Producto']}'")
                    cpr.write(f"${item['Total']:,.2f}")
                    if ca.button("❌", key=f"btn_carrito_{i}", type="secondary", use_container_width=True):
                        cancelar_producto(i)
            total_carrito = sum(item["Total"] for item in st.session_state.carrito_actual)
            st.markdown(f"##### Subtotal: **${total_carrito:,.2f}**")
            if st.button("💰 COBRAR Y FINALIZAR TICKET", type="primary", use_container_width=True):
                hora_ticket = datetime.now().strftime("%H:%M:%S")
                df = st.session_state.df
                codigos_limpios = df["Código"].astype(str).str.replace(r'\.0$', '', regex=True)
                for item in st.session_state.carrito_actual:
                    match = df[codigos_limpios == item["Código"]]
                    if not match.empty:
                        idx = match.index[0]
                        df.at[idx, "Stock Actual"] -= item["Cantidad"]
                with st.spinner("Guardando en Google Sheets..."):
                    guardado = guardar_inventario(df)
                if guardado:
                    st.session_state.df = df
                    for item in st.session_state.carrito_actual:
                        item["Ticket"] = st.session_state.numero_ticket
                        item["Hora Ticket"] = hora_ticket
                    st.session_state.ventas_del_dia.extend(st.session_state.carrito_actual)
                    st.session_state.carrito_actual = []
                    st.session_state.numero_ticket += 1
                    st.toast("✅ ¡Venta cobrada!", icon="💰")
                    st.session_state.sonido_a_reproducir = "exito"
                    st.rerun()
        else:
            st.info("Esperando escaneo de productos...")

        st.markdown("---")
        st.markdown("#### ✅ Ventas del Turno")
        if st.session_state.ventas_del_dia:
            df_ventas = pd.DataFrame(st.session_state.ventas_del_dia)
            df_agrupado = df_ventas.groupby(["Ticket", "Hora Ticket"]).agg(
                Artículos=('Cantidad', 'sum'),
                Total_Cobrado=('Total', 'sum'),
                Detalle=('Producto', lambda x: ", ".join([f"{list(x).count(p)}x {p}" for p in set(x)]))
            ).reset_index()
            for _, row in df_agrupado.iterrows():
                st.markdown(f"""
                <div style='background:#1C1C1C;border:1px solid #2A2A2A;border-radius:10px;padding:12px 16px;margin-bottom:8px;display:flex;justify-content:space-between;align-items:center;'>
                    <div>
                        <div style='font-size:10px;color:#5A5650;letter-spacing:0.1em;text-transform:uppercase;margin-bottom:4px'>Ticket #{int(row["Ticket"])} · {row["Hora Ticket"]}</div>
                        <div style='font-size:13px;color:#F0EDE6;font-weight:500'>{row["Detalle"]}</div>
                    </div>
                    <div style='text-align:right'>
                        <div style='font-family:Georgia,serif;font-size:20px;font-weight:700;color:#C9A84C'>${row["Total_Cobrado"]:,.0f}</div>
                        <div style='font-size:10px;color:#5A5650'>{int(row["Artículos"])} artículo{"s" if row["Artículos"] > 1 else ""}</div>
                    </div>
                </div>""", unsafe_allow_html=True)
            total_acumulado = df_ventas["Total"].sum()
            st.markdown(f"### 💰 Total en Caja: **${total_acumulado:,.2f}**")
        else:
            st.caption("Sin ventas cerradas en este turno.")

    with col_cierre:
        st.markdown("#### 🔒 Cierre de Caja")
        if st.session_state.rol == "trabajador":
            st.warning("🚫 Solo el encargado o jefe puede cerrar.")
        elif st.session_state.ventas_del_dia:
            df_ventas = pd.DataFrame(st.session_state.ventas_del_dia)
            total_caja = df_ventas["Total"].sum()
            articulos_totales = df_ventas["Cantidad"].sum()
            if st.button("🏁 HACER CIERRE DE CAJA", type="primary", use_container_width=True):
                fecha_legible = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
                df_agrupado_prod = df_ventas.groupby("Producto")["Cantidad"].sum().reset_index()
                detalle = ", ".join([f"{r['Producto']} (x{r['Cantidad']})" for _, r in df_agrupado_prod.iterrows()])
                with st.spinner("Guardando cierre en Google Sheets..."):
                    ok = guardar_cierre_sheets(fecha_legible, st.session_state.nombre_usuario, total_caja, articulos_totales, detalle)
                if ok:
                    st.session_state.ventas_del_dia = []
                    st.session_state.numero_ticket = 1
                    st.success("✅ Cierre guardado en Google Sheets.")
                    st.session_state.sonido_a_reproducir = "exito"
                    st.rerun()

        st.markdown("---")
        st.markdown("#### 📋 Historial de Cierres")
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
# 🔍 PESTAÑA 2: INVENTARIO
# ==========================================
with tab_gestion:
    st.markdown("### 🛠️ Control y Edición de Productos")
    if st.session_state.rol == "trabajador":
        st.warning("🚫 No tenés permisos para modificar el inventario.")
        st.stop()
    df = st.session_state.df
    if df.empty:
        st.info("El inventario está vacío.")
    else:
        col_busca1, col_busca2 = st.columns(2)
        with col_busca1:
            buscar = st.text_input("🔍 Buscar por nombre:", "").strip()
        with col_busca2:
            codigo_escaneado = st.text_input("⚡ Escanear código:", key="scanner_edicion_manual").strip()
        if codigo_escaneado:
            df_filtrado = df[df["Código"].astype(str).str.replace(r'\.0$', '', regex=True) == codigo_escaneado]
            if df_filtrado.empty:
                st.error(f"❌ No se encontró el código: '{codigo_escaneado}'")
        else:
            df_filtrado = df[df["Producto"].str.contains(buscar, case=False, na=False)] if buscar else df
        if not df_filtrado.empty:
            producto_a_editar = st.selectbox("Seleccioná el producto:", df_filtrado["Producto"].unique())
            datos_prod = df[df["Producto"] == producto_a_editar].iloc[0]
            with st.form(f"form_edicion_{producto_a_editar}"):
                st.write(f"✍️ **Modificando:** {producto_a_editar}")
                imagen_actual = obtener_imagen_producto(str(datos_prod.get("Código", "")))
                col_img, col_upload = st.columns([1, 2])
                with col_img:
                    if imagen_actual:
                        st.image(imagen_actual, width=120)
                    else:
                        st.caption("Sin imagen")
                with col_upload:
                    nueva_imagen = st.file_uploader("Reemplazar imagen", type=["jpg","jpeg","png","webp"], key=f"img_{producto_a_editar}")
                    if nueva_imagen:
                        guardar_imagen_producto(str(datos_prod.get("Código","")), nueva_imagen)
                        st.success("Imagen actualizada")
                nuevo_nombre = st.text_input("📦 Nombre:", value=producto_a_editar).strip()
                codigo_actual = str(datos_prod.get("Código",""))
                if codigo_actual.endswith(".0"):
                    codigo_actual = codigo_actual[:-2]
                if codigo_actual.lower() in ["nan","none","<na>"]:
                    codigo_actual = ""
                nuevo_codigo = st.text_input("🏷️ Código:", value=codigo_actual)
                c1, c2, c3, c4 = st.columns(4)
                with c1:
                    precio_excel = float(datos_prod.get("Precio Venta", 0))
                    nuevo_precio = st.number_input("Precio ($)", min_value=0, value=int(precio_excel) if precio_excel.is_integer() else precio_excel, step=50)
                with c2:
                    nuevo_stock = st.number_input("Stock Actual", min_value=0, value=int(float(datos_prod.get("Stock Actual",0))))
                with c3:
                    nuevo_minimo = st.number_input("Stock Mínimo", min_value=0, value=int(float(datos_prod.get("Stock Mínimo",0))))
                with c4:
                    try:
                        fecha_v_actual = datetime.strptime(str(datos_prod.get("Fecha Vencimiento",hoy)), '%Y-%m-%d')
                    except:
                        fecha_v_actual = hoy
                    nueva_fecha_v = st.date_input("Vencimiento", value=fecha_v_actual)
                col_b1, col_b2 = st.columns([1,5])
                with col_b1:
                    if st.form_submit_button("💾 Guardar"):
                        st.session_state.df.loc[st.session_state.df["Producto"] == producto_a_editar,
                            ["Código","Precio Venta","Stock Actual","Stock Mínimo","Fecha Vencimiento"]] = [
                            str(nuevo_codigo), nuevo_precio, nuevo_stock, nuevo_minimo, nueva_fecha_v.strftime('%Y-%m-%d')]
                        with st.spinner("Guardando..."):
                            ok = guardar_inventario(st.session_state.df)
                        if ok:
                            st.success("¡Guardado!")
                            st.session_state.sonido_a_reproducir = "exito"
                            st.rerun()
                with col_b2:
                    if st.form_submit_button("🗑️ Eliminar"):
                        st.session_state.df = st.session_state.df[st.session_state.df["Producto"] != producto_a_editar]
                        with st.spinner("Eliminando..."):
                            guardar_inventario(st.session_state.df)
                        st.success("Producto eliminado.")
                        st.rerun()

        st.markdown("---")
        st.markdown("### 🖼️ Catálogo Visual")
        if st.button("🔍 Buscar imágenes automáticamente"):
            productos_sin_imagen = [p for p in st.session_state.df.to_dict("records") if not obtener_imagen_producto(str(p.get("Código","")))]
            if not productos_sin_imagen:
                st.success("✅ Todos los productos tienen imagen.")
            else:
                encontradas = 0
                barra = st.progress(0, text="Buscando...")
                for i, prod in enumerate(productos_sin_imagen):
                    codigo = str(prod.get("Código","")).replace("#","").strip()
                    if codigo.endswith(".0"):
                        codigo = codigo[:-2]
                    if buscar_imagen_online(codigo, str(prod.get("Producto",""))):
                        encontradas += 1
                    barra.progress((i+1)/len(productos_sin_imagen), text=f"Buscando: {prod.get('Producto','')}...")
                barra.empty()
                st.success(f"✅ {encontradas} imágenes encontradas.")
                st.rerun()

        df_visual = st.session_state.df.copy()
        cols_por_fila = 4
        productos = df_visual.to_dict("records")
        for fila_idx in range(0, len(productos), cols_por_fila):
            fila = productos[fila_idx:fila_idx+cols_por_fila]
            columnas = st.columns(cols_por_fila)
            for col, prod in zip(columnas, fila):
                with col:
                    imagen = obtener_imagen_producto(str(prod.get("Código","")))
                    if imagen:
                        st.markdown(f"""
                        <div style='height:200px;overflow:hidden;border-radius:8px;background:#1C1C1C;'>
                            <img src='data:image/jpeg;base64,{base64.b64encode(open(imagen,"rb").read()).decode()}'
                            style='width:100%;height:100%;object-fit:cover;'/>
                        </div>""", unsafe_allow_html=True)
                    else:
                        st.markdown("""<div style='background:#1C1C1C;border:1px dashed #3A3A3A;border-radius:8px;height:200px;display:flex;align-items:center;justify-content:center;color:#3A3A3A;font-size:11px;'>SIN IMAGEN</div>""", unsafe_allow_html=True)
                    st.markdown(f"""
                    <div style='padding:8px 2px 16px'>
                        <div style='font-size:12px;font-weight:600;color:#F0EDE6;text-transform:uppercase;margin-bottom:4px;'>{prod.get("Producto","")}</div>
                        <div style='font-size:18px;font-weight:700;color:#C9A84C;font-family:Georgia,serif;'>${prod.get("Precio Venta",0):,.0f}</div>
                        <div style='font-size:10px;color:#5A5650;margin-top:3px;'>STOCK: {prod.get("Stock Actual",0)}</div>
                    </div>""", unsafe_allow_html=True)

# ==========================================
# 📥 PESTAÑA 3: NUEVO PRODUCTO
# ==========================================
with tab_carga:
    st.markdown("### 📥 Registrar Producto Nuevo")
    if st.session_state.rol == "trabajador":
        st.warning("🚫 No tenés permisos para agregar productos.")
        st.stop()
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
        imagen_input = st.file_uploader("Imagen (opcional)", type=["jpg","jpeg","png","webp"])
        if st.form_submit_button("➕ Agregar al Inventario"):
            df = st.session_state.df
            if not producto_input:
                st.error("El nombre no puede estar vacío.")
            elif producto_input in df["Producto"].values:
                st.error("El producto ya existe.")
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
                    st.session_state.sonido_a_reproducir = "exito"
                    st.rerun()

# ==========================================
# 🚨 PESTAÑA 4: ALERTAS
# ==========================================
with tab_vencimientos:
    st.markdown("### 🚨 Control de Stock y Vencimientos")
    df = st.session_state.df
    if df.empty:
        st.info("No hay productos cargados.")
    else:
        st.markdown("#### 🛒 Productos a Reponer")
        df["Stock Actual"] = pd.to_numeric(df["Stock Actual"])
        df["Stock Mínimo"] = pd.to_numeric(df["Stock Mínimo"])
        reposiciones = df[df["Stock Actual"] <= df["Stock Mínimo"]].copy()
        if not reposiciones.empty:
            reposiciones["Faltante"] = reposiciones["Stock Mínimo"] - reposiciones["Stock Actual"]
            for _, row in reposiciones.iterrows():
                urgencia = "#C44" if row["Faltante"] > row["Stock Mínimo"] * 0.5 else "#C9853A"
                st.markdown(f"""
                <div style='background:#1C1C1C;border-left:3px solid {urgencia};border-radius:10px;padding:12px 16px;margin-bottom:8px;display:flex;justify-content:space-between;align-items:center;'>
                    <div style='font-size:13px;color:#F0EDE6;font-weight:600'>{row["Producto"]}</div>
                    <div style='display:flex;gap:20px;text-align:center'>
                        <div><div style='font-size:9px;color:#5A5650;text-transform:uppercase'>Stock</div><div style='font-size:16px;font-weight:700;color:#F0EDE6'>{int(row["Stock Actual"])}</div></div>
                        <div><div style='font-size:9px;color:#5A5650;text-transform:uppercase'>Mínimo</div><div style='font-size:16px;font-weight:700;color:#9A9590'>{int(row["Stock Mínimo"])}</div></div>
                        <div><div style='font-size:9px;color:#5A5650;text-transform:uppercase'>Faltan</div><div style='font-size:16px;font-weight:700;color:{urgencia}'>{int(row["Faltante"])}</div></div>
                    </div>
                </div>""", unsafe_allow_html=True)
        else:
            st.success("✅ Todo el stock al día.")
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
            except:
                pass
        st.markdown("#### ❌ Productos Vencidos")
        if lista_vencidos:
            for item in lista_vencidos:
                st.markdown(f"""
                <div style='background:#1C1C1C;border-left:3px solid #C44;border-radius:10px;padding:12px 16px;margin-bottom:8px;display:flex;justify-content:space-between;'>
                    <div><div style='font-size:13px;color:#F0EDE6;font-weight:600'>{item["Producto"]}</div><div style='font-size:10px;color:#5A5650'>Venció el {item["Fecha Vencimiento"]}</div></div>
                    <div style='text-align:right'><div style='font-size:18px;font-weight:700;color:#F08080'>{int(item["Días Vencido"])} días</div><div style='font-size:10px;color:#5A5650'>Stock: {int(item["Stock"])}</div></div>
                </div>""", unsafe_allow_html=True)
        else:
            st.success("🎉 Ningún vencido.")
        st.markdown("#### ⚠️ Próximos a Vencer (15 días)")
        if lista_por_vencer:
            for item in lista_por_vencer:
                color = "#C44" if item["Días Restantes"] <= 3 else "#C9853A" if item["Días Restantes"] <= 7 else "#C9A84C"
                st.markdown(f"""
                <div style='background:#1C1C1C;border-left:3px solid {color};border-radius:10px;padding:12px 16px;margin-bottom:8px;display:flex;justify-content:space-between;'>
                    <div><div style='font-size:13px;color:#F0EDE6;font-weight:600'>{item["Producto"]}</div><div style='font-size:10px;color:#5A5650'>Vence el {item["Fecha Vencimiento"]}</div></div>
                    <div style='text-align:right'><div style='font-size:18px;font-weight:700;color:{color}'>{int(item["Días Restantes"])} días</div><div style='font-size:10px;color:#5A5650'>Stock: {int(item["Stock"])}</div></div>
                </div>""", unsafe_allow_html=True)
        else:
            st.success("👍 Sin vencimientos cercanos.")

# ==========================================
# 🤖 PESTAÑA 5: ASISTENTE IA
# ==========================================
with tab_ia:
    st.markdown("### 🤖 Asistente Operativo IA")
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
    prompt_chat = st.chat_input("Escribí una orden o pasá el escáner acá...")
    if prompt_chat:
        with st.chat_message("user"):
            st.write(prompt_chat)
        st.session_state.historial_chat.append({"role": "user", "content": prompt_chat})
        if not gemini_key:
            respuesta_visible = "⚠️ Ingresá tu API Key de Gemini para operar."
            with st.chat_message("assistant"):
                st.write(respuesta_visible)
            st.session_state.historial_chat.append({"role": "assistant", "content": respuesta_visible})
        else:
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
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={gemini_key}"
                headers = {'Content-Type': 'application/json'}
                es_solo_consulta = st.session_state.rol == "trabajador"
                modo_ia = "solo puede hacer CONSULTAS." if es_solo_consulta else "puede realizar ACCIONES y CONSULTAS."
                instruccion_sistema = (
                    f"Sos un Agente IA para un kiosco. El usuario {modo_ia}\n"
                    f"Hoy es {fecha_hoy_humano}.\n\n"
                    f"--- INVENTARIO ---\n{resumen_inventario}\n\n"
                    "RESPONDÉ SOLO EN JSON RECTO SIN TEXTO AFUERA:\n"
                    '{"accion":"AGREGAR"|"MODIFICAR"|"ELIMINAR"|"NINGUNA","datos":{"Código":"","Producto":"","Precio Venta":0.0,"Stock Actual":0,"Stock Mínimo":5,"Fecha Vencimiento":""},"mensaje":"respuesta amigable"}'
                )
                payload = {"contents": [{"parts": [{"text": f"{instruccion_sistema}\n\nPetición: {prompt_a_enviar_ia}"}]}]}
                hubo_cambios = False
                try:
                    response = requests.post(url, headers=headers, json=payload)
                    if response.status_code == 200:
                        resultado_raw = response.json()['candidates'][0]['content']['parts'][0]['text'].strip()
                        if resultado_raw.startswith("```"):
                            resultado_raw = resultado_raw.replace("```json","").replace("```","").strip()
                        paquete = json.loads(resultado_raw)
                        accion = paquete.get("accion","NINGUNA")
                        datos = paquete.get("datos",{})
                        respuesta_visible = paquete.get("mensaje","Orden procesada.")
                        if accion == "AGREGAR":
                            nueva_fila = pd.DataFrame([{
                                "Código": str(datos.get("Código","")),
                                "Producto": str(datos.get("Producto","Nuevo")),
                                "Precio Venta": float(datos.get("Precio Venta",0.0)),
                                "Stock Actual": int(datos.get("Stock Actual",0)),
                                "Stock Mínimo": int(datos.get("Stock Mínimo",5)),
                                "Fecha Vencimiento": str(datos.get("Fecha Vencimiento",""))
                            }])
                            st.session_state.df = pd.concat([df_actual, nueva_fila], ignore_index=True)
                            hubo_cambios = True
                        elif accion == "MODIFICAR":
                            prod_nombre = datos.get("Producto")
                            match = df_actual[df_actual["Producto"].str.contains(prod_nombre, case=False, na=False)]
                            if not match.empty:
                                idx = match.index[0]
                                if datos.get("Precio Venta") is not None:
                                    st.session_state.df.at[idx,"Precio Venta"] = float(datos["Precio Venta"])
                                if datos.get("Stock Actual") is not None:
                                    st.session_state.df.at[idx,"Stock Actual"] = int(datos["Stock Actual"])
                                if datos.get("Stock Mínimo") is not None:
                                    st.session_state.df.at[idx,"Stock Mínimo"] = int(datos["Stock Mínimo"])
                                if datos.get("Fecha Vencimiento"):
                                    st.session_state.df.at[idx,"Fecha Vencimiento"] = str(datos["Fecha Vencimiento"])
                                hubo_cambios = True
                        elif accion == "ELIMINAR":
                            prod_nombre = datos.get("Producto")
                            st.session_state.df = df_actual[~df_actual["Producto"].str.contains(prod_nombre, case=False, na=False)]
                            hubo_cambios = True
                        if hubo_cambios:
                            with st.spinner("Guardando en Google Sheets..."):
                                guardar_inventario(st.session_state.df)
                            st.session_state.sonido_a_reproducir = "exito"
                    elif response.status_code == 503:
                        respuesta_visible = "⏳ Servidores saturados. Esperá un momento."
                    elif response.status_code == 429:
                        respuesta_visible = "🛑 Límite de la API alcanzado. Esperá 60 segundos."
                    else:
                        respuesta_visible = f"❌ Error {response.status_code}."
                except Exception as e:
                    respuesta_visible = f"❌ Error: {str(e)}"
            with st.chat_message("assistant"):
                st.write(respuesta_visible)
            st.session_state.historial_chat.append({"role": "assistant", "content": respuesta_visible})
            if hubo_cambios:
                st.rerun()

# ==========================================
# ⚙️ PESTAÑA 6: ADMIN (SOLO JEFE)
# ==========================================
if st.session_state.rol == "jefe" and tab_admin:
    with tab_admin:
        st.markdown("### ⚙️ Administración")
        st.markdown("#### 👥 Perfiles")
        for perfil in PERFILES:
            st.markdown(f"- {perfil['emoji']} **{perfil['nombre']}** — rol: `{perfil['rol']}`")
        st.markdown("---")
        st.markdown("#### 📊 Resumen")
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
# 🔊 AUDIO
# ==========================================
if st.session_state.sonido_a_reproducir:
    emitir_sonido_navegador(st.session_state.sonido_a_reproducir)
    st.session_state.sonido_a_reproducir = None