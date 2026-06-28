import streamlit as st
import pandas as pd
import os
import shutil
import requests
import json
from datetime import datetime
import streamlit.components.v1 as components

# Configuración de la página web (Pestaña del navegador y diseño ancho)
st.set_page_config(
    page_title="Kiosco",
    page_icon="imagenes/kiosco.png",
    layout="wide"
)

# Constantes de rutas para archivos de datos y reportes
NOMBRE_ARCHIVO = "Inventario_Quiosco.xlsx"
CARPETA_BACKUPS = "backups_inventario"
CARPETA_REPORTES = "reportes_cierre"

# ==========================================
# ⚙️ INICIALIZACIÓN DE VARIABLES DE ESTADO
# ==========================================
# Acá inicializamos el número de ticket y los carritos para que no se borren
if "numero_ticket" not in st.session_state:
    st.session_state.numero_ticket = 1

if "carrito_actual" not in st.session_state:
    st.session_state.carrito_actual = []
    
if "ventas_del_dia" not in st.session_state:
    st.session_state.ventas_del_dia = []

# ==========================================
# 🛡️ SISTEMA DE SEGURIDAD: BACKUP AUTOMÁTICO
# ==========================================
def realizar_backup():
    """Genera una copia de seguridad numerada del archivo de Excel."""
    try:
        if os.path.exists(NOMBRE_ARCHIVO):
            if not os.path.exists(CARPETA_BACKUPS):
                os.makedirs(CARPETA_BACKUPS)
            
            # Crear nombre único con fecha y hora exacta
            fecha_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            nombre_backup = os.path.join(CARPETA_BACKUPS, f"Inventario_Backup_{fecha_str}.xlsx")
            
            # Copiar archivo
            shutil.copy(NOMBRE_ARCHIVO, nombre_backup)
            
            # Mantener únicamente los últimos 10 backups para optimizar espacio
            todos_backups = sorted(
                [os.path.join(CARPETA_BACKUPS, f) for f in os.listdir(CARPETA_BACKUPS) if f.endswith('.xlsx')],
                key=os.path.getmtime
            )
            while len(todos_backups) > 10:
                os.remove(todos_backups.pop(0))
    except Exception as e:
        print(f"No se pudo generar la copia de seguridad: {e}")

# ==========================================
# 📊 CONEXIÓN EXCEL: CARGA Y GUARDADO
# ==========================================
def cargar_inventario():
    """Carga los datos del Excel adaptándose automáticamente a cambios de esquema."""
    columnas = ["Código", "Producto", "Precio Venta", "Stock Actual", "Stock Mínimo", "Fecha Vencimiento"]
    if os.path.exists(NOMBRE_ARCHIVO):
        try:
            df = pd.read_excel(NOMBRE_ARCHIVO)
            
            # Asegurar que todas las columnas requeridas existan de forma segura
            for col in columnas:
                if col not in df.columns:
                    if col == "Código":
                        df.insert(0, "Código", "")
                    elif col == "Precio Venta":
                        df.insert(2, "Precio Venta", 0.0)
                    else:
                        df[col] = ""
            
            # Normalizar y limpiar tipos de datos
            df["Código"] = df["Código"].fillna("").astype(str).str.strip()
            if "Fecha Vencimiento" in df.columns:
                df["Fecha Vencimiento"] = pd.to_datetime(df["Fecha Vencimiento"], errors='coerce').dt.strftime('%Y-%m-%d')
                df["Fecha Vencimiento"] = df["Fecha Vencimiento"].fillna("")
            
            df["Precio Venta"] = pd.to_numeric(df["Precio Venta"], errors='coerce').fillna(0.0)
            df["Stock Actual"] = pd.to_numeric(df["Stock Actual"], errors='coerce').fillna(0).astype(int)
            df["Stock Mínimo"] = pd.to_numeric(df["Stock Mínimo"], errors='coerce').fillna(5).astype(int)
            
            return df
        except Exception as e:
            st.error(f"⚠️ Error al leer el archivo Excel: {e}")
            return pd.DataFrame(columns=columnas)
    return pd.DataFrame(columns=columnas)

def guardar_inventario(df):
    """Guarda el inventario en el archivo Excel y dispara un backup de respaldo."""
    try:
        df.to_excel(NOMBRE_ARCHIVO, index=False)
        realizar_backup()
        return True
    except PermissionError:
        st.error("❌ ¡Atención! No se pudo guardar porque el archivo de Excel está abierto. Cerralo y volvé a intentar.")
        st.session_state.sonido_a_reproducir = "error"
        return False

# ==========================================
# 🔊 EFECTOS DE SONIDO (WEB AUDIO API)
# ==========================================
def emitir_sonido_navegador(tipo):
    """Genera tonos de sonido directamente desde la tarjeta de audio del navegador."""
    if tipo == "exito":
        # Sonido 'bip' de éxito (agudo y corto)
        js_code = """
        <script>
        const ctx = new (window.AudioContext || window.webkitAudioContext)();
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = 'sine';
        osc.frequency.setValueAtTime(950, ctx.currentTime);
        gain.gain.setValueAtTime(0.1, ctx.currentTime);
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start();
        osc.stop(ctx.currentTime + 0.08);
        </script>
        """
    elif tipo == "error":
        # Sonido de error (grave y sostenido)
        js_code = """
        <script>
        const ctx = new (window.AudioContext || window.webkitAudioContext)();
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = 'sawtooth';
        osc.frequency.setValueAtTime(130, ctx.currentTime);
        gain.gain.setValueAtTime(0.12, ctx.currentTime);
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start();
        osc.stop(ctx.currentTime + 0.25);
        </script>
        """
    components.html(js_code, height=0, width=0)

# ==========================================
# 🔄 INICIALIZACIÓN DE VARIABLES EN SESIÓN
# ==========================================
if 'df' not in st.session_state:
    st.session_state.df = cargar_inventario()

if 'ventas_del_dia' not in st.session_state:
    st.session_state.ventas_del_dia = []

if 'sonido_a_reproducir' not in st.session_state:
    st.session_state.sonido_a_reproducir = None

if 'historial_chat' not in st.session_state:
    st.session_state.historial_chat = []

hoy = datetime.now()
df_actual = st.session_state.df

# --- INTERFAZ VISUAL PRINCIPAL ---
st.title("🏪 Kiosco")
st.subheader("Sistema de Gestión Inteligente para el Quiosco")

# Panel Superior: Indicadores Clave en Tiempo Real
st.markdown("### 📊 Estado General")
col1, col2, col3 = st.columns(3)

productos_faltantes = 0
productos_vencidos = 0

if not df_actual.empty:
    productos_faltantes = len(df_actual[df_actual["Stock Actual"] <= df_actual["Stock Mínimo"]])
    for idx, fila in df_actual.iterrows():
        try:
            fecha_v_str = str(fila["Fecha Vencimiento"]).split()[0]
            fecha_v = datetime.strptime(fecha_v_str, '%Y-%m-%d')
            if (fecha_v - hoy).days < 0:
                productos_vencidos += 1
        except:
            pass

with col1:
    st.metric("Total Productos", len(df_actual))
with col2:
    st.metric("⚠️ Productos a Reponer", productos_faltantes)
with col3:
    st.metric("❌ Productos Vencidos", productos_vencidos)

st.markdown("---")

# Creación de Pestañas de Trabajo
tab_caja, tab_gestion, tab_carga, tab_vencimientos, tab_ia = st.tabs([
    "🛒 Caja (Escáner de Barras)",
    "🔍 Modificar Inventario",
    "📥 Cargar Nuevo Producto",
    "🚨 Alertas de Vencimiento y Reponer",
    "🤖 Asistente IA Operativo"
])

# ==========================================
# 🛒 PROCESO AUTOMATIZADO DE ESCANEO Y AJUSTES
# ==========================================

if "carrito_actual" not in st.session_state:
    st.session_state.carrito_actual = []

def cancelar_producto(idx_carrito):
    """Elimina el producto del carrito actual sin tocar el inventario porque aún no se descontó"""
    venta_a_cancelar = st.session_state.carrito_actual.pop(idx_carrito)
    st.toast(f"🔄 Quitado: '{venta_a_cancelar['Producto']}' eliminado de la venta actual.", icon="↩️")
    st.session_state.sonido_a_reproducir = "error"
    st.rerun()
    
    # Buscar el producto en el inventario maestro para devolverle su unidad
    match = df[df["Código"] == codigo_prod]
    if not match.empty:
        idx_inv = match.index[0]
        st.session_state.df.at[idx_inv, "Stock Actual"] += 1
        guardar_inventario(st.session_state.df)
    
    # Eliminar de la lista del carrito actual
    st.session_state.carrito_actual.pop(idx_carrito)
    st.toast(f"🔄 Quitado: Se devolvió 1 unidad de '{venta_a_cancelar['Producto']}' al stock.", icon="↩️")
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
            
            # Chequeamos cuántos de este producto ya tenemos metidos en el carrito actual
            en_carrito = sum(1 for item in st.session_state.carrito_actual if item["Código"] == codigo_leido)
            
            # Solo dejamos agregarlo si el stock real es mayor a lo que ya tenemos en la mano
            if stock_disp > en_carrito:
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
                st.error(f"🚨 ¡Sin Stock! Solo te quedan {stock_disp} unidades de '{producto}' y ya las escaneaste todas.")
                st.session_state.sonido_a_reproducir = "error"
        else:
            st.warning(f"🔍 Código '{codigo_leido}' no registrado.")
            st.session_state.sonido_a_reproducir = "error"
            
    # Limpiar el input para el próximo escaneo
    st.session_state.input_escanner = ""


# PESTAÑA 1: PUNTO DE VENTA (CAJA)
with tab_caja:
    st.markdown("### ⚡ Punto de Venta Automatizado")
    st.text_input(
        "👉 Hacé clic acá y pasá el lector por el código de barras del producto:",
        key="input_escanner",
        on_change=procesar_escaneo
    )
    st.markdown("---")
    
    col_tabla, col_cierre = st.columns([2, 1])
    
    with col_tabla:
        # ----------------------------------------------------
        # SECCIÓN A: PRODUCTOS QUE SE ESTÁN ESCANEANDO AHORA
        # ----------------------------------------------------
        st.markdown("#### 🛒 Venta en Curso (Próxima Venta)")
        
        if st.session_state.carrito_actual:
            with st.container(height=270):
                c_hora, c_prod, c_prec, c_accion = st.columns([1, 2, 1, 1])
                c_hora.markdown("**Hora**")
                c_prod.markdown("**Producto**")
                c_prec.markdown("**Precio**")
                c_accion.markdown("**Modificar**")
                st.markdown("---")
                
                for i in reversed(range(len(st.session_state.carrito_actual))):
                    item = st.session_state.carrito_actual[i]
                    ch, cp, cpr, ca = st.columns([1, 2, 1, 1])
                    ch.write(f"⏱️ {item['Hora']}")
                    cp.write(item['Producto'])
                    cpr.write(f"${item['Precio']:,.2f}")
                    
                    if ca.button("❌ Quitar", key=f"btn_carrito_{i}", type="secondary", use_container_width=True):
                        cancelar_producto(i)
            
            total_carrito = sum(item["Total"] for item in st.session_state.carrito_actual)
            st.markdown(f"##### Subtotal a Cobrar: **${total_carrito:,.2f}**")
            
            # Botón para consolidar y pasar la venta al historial
            if st.button("💰 COBRAR Y FINALIZAR TICKET", type="primary", use_container_width=True):
                hora_ticket = datetime.now().strftime("%H:%M:%S")
                df = st.session_state.df
                codigos_limpios = df["Código"].astype(str).str.replace(r'\.0$', '', regex=True)
                
                # 1. Recién ahora descontamos el stock definitivo del Excel
                for item in st.session_state.carrito_actual:
                    codigo = item["Código"]
                    match = df[codigos_limpios == codigo]
                    if not match.empty:
                        idx = match.index[0]
                        df.at[idx, "Stock Actual"] -= 1 # Restamos 1 por cada unidad vendida
                
                # Guardamos los cambios en el Excel
                guardar_inventario(df)
                st.session_state.df = df
                
                # 2. Asignamos número de ticket y pasamos al historial
                for item in st.session_state.carrito_actual:
                    item["Ticket"] = st.session_state.numero_ticket
                    item["Hora Ticket"] = hora_ticket
                    
                st.session_state.ventas_del_dia.extend(st.session_state.carrito_actual)
                st.session_state.carrito_actual = []
                st.session_state.numero_ticket += 1 # Preparamos el número para el próximo cliente
                
                st.toast("✅ ¡Venta cobrada y stock actualizado con éxito!", icon="💰")
                st.session_state.sonido_a_reproducir = "exito"
                st.rerun()
        else:
            st.info("Esperando escaneo de productos para iniciar un ticket...")
            
        st.markdown("---")
        
        # ----------------------------------------------------
        # SECCIÓN B: HISTORIAL DE VENTAS YA COBRADAS (AGRUPADAS)
        # ----------------------------------------------------
        st.markdown("#### ✅ Ventas ya Realizadas en este Turno")
        if st.session_state.ventas_del_dia:
            df_ventas = pd.DataFrame(st.session_state.ventas_del_dia)
            
            # 🌟 CAMBIO ACÁ: Agrupamos todo por el número de Ticket y mejoramos el resumen visual
            df_agrupado = df_ventas.groupby(["Ticket", "Hora Ticket"]).agg(
                Artículos=('Cantidad', 'sum'),
                Total_Cobrado=('Total', 'sum'),
                # El nuevo truco está acá: Cuenta las apariciones y le pone el formato "Cantidad x Producto"
                Detalle=('Producto', lambda x: ", ".join([f"{list(x).count(p)}x {p}" for p in set(x)])) 
            ).reset_index()
            
            # Renombramos las columnas para que la tabla quede prolija
            df_agrupado.rename(columns={"Ticket": "Nº Venta", "Hora Ticket": "Hora", "Total_Cobrado": "Total ($)"}, inplace=True)
            
            # 🌟 CAMBIO ACÁ: Quitamos el st.container y usamos height=250 directo en el dataframe
            st.dataframe(
                df_agrupado[["Nº Venta", "Hora", "Artículos", "Detalle", "Total ($)"]], 
                use_container_width=True, 
                hide_index=True,
                height=250
            )
            
            total_acumulado = df_ventas["Total"].sum()
            st.markdown(f"### 💰 Total Acumulado en Caja: **${total_acumulado:,.2f}**")
        else:
            st.caption("Aún no hay ventas cerradas en este turno.")
            
    with col_cierre:
        st.markdown("#### 🔒 Módulo de Cierre de Caja")
        st.write("Al cerrar la caja, se guardará un reporte histórico detallado en tu computadora y se reiniciará el saldo del turno.")
        
        if st.session_state.ventas_del_dia:
            df_ventas = pd.DataFrame(st.session_state.ventas_del_dia)
            total_caja = df_ventas["Total"].sum()
            articulos_totales = df_ventas["Cantidad"].sum()
            
            if st.button("🏁 HACER CIERRE DE CAJA", type="primary", use_container_width=True):
                if not os.path.exists(CARPETA_REPORTES):
                    os.makedirs(CARPETA_REPORTES)
                
                fecha_hoy_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                fecha_legible = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
                nombre_reporte = os.path.join(CARPETA_REPORTES, f"Reporte_Cierre_{fecha_hoy_str}.txt")                
                with open(nombre_reporte, "w", encoding="utf-8") as f:
                    f.write("=========================================\n")
                    f.write("          REPORTE DE CIERRE DE CAJA       \n")
                    f.write("=========================================\n")
                    f.write(f"Fecha y Hora: {fecha_legible}\n")
                    f.write(f"Total Recaudado: ${total_caja:,.2f}\n")
                    f.write(f"Artículos Vendidos: {articulos_totales}\n")
                    f.write("-----------------------------------------\n")
                    f.write("DETALLE DE LAS VENTAS:\n")
                    f.write(df_ventas.to_string(index=False))
                    f.write("\n=========================================\n")
                
                archivo_excel = os.path.join(CARPETA_REPORTES, "cierres_historicos.csv")
                col_nombre_producto = "Producto" if "Producto" in df_ventas.columns else df_ventas.columns[0]
                df_agrupado = df_ventas.groupby(col_nombre_producto)["Cantidad"].sum().reset_index()
                
                lista_resumen = []
                for _, fila in df_agrupado.iterrows():
                    lista_resumen.append(f"{fila[col_nombre_producto]} (x{fila['Cantidad']})")
                detalle_productos_texto = ", ".join(lista_resumen)
                
                datos_nueva_fila = {
                    "Fecha y Hora": [fecha_legible],
                    "Total Recaudado ($)": [total_caja],
                    "Artículos Vendidos": [articulos_totales],
                    "Detalle de Productos": [detalle_productos_texto]
                }
                df_nueva_fila = pd.DataFrame(datos_nueva_fila)
                
                if os.path.exists(archivo_excel):
                    df_nueva_fila.to_csv(archivo_excel, mode='a', header=False, index=False, encoding='utf-8-sig')
                else:
                    df_nueva_fila.to_csv(archivo_excel, index=False, encoding='utf-8-sig')
                
                st.session_state.ventas_del_dia = []
                st.session_state.numero_ticket = 1
                st.success(f"Cierre exitoso. Guardado en la carpeta '{CARPETA_REPORTES}'.")
                st.session_state.sonido_a_reproducir = "exito"
                st.rerun()
        else:
            st.button("🏁 HACER CIERRE DE CAJA", disabled=True, use_container_width=True, help="Registrá y cobrá ventas para habilitar el cierre.")
            
    # MOSTRAR EL HISTORIAL LIMITADO ABAJO
    st.markdown("---")
    st.markdown("### 📊 Historial de Cierres de Caja Recientes")
    archivo_excel = os.path.join(CARPETA_REPORTES, "cierres_historicos.csv")
    
    if os.path.exists(archivo_excel):
        df_historico = pd.read_csv(archivo_excel)
        filas_visibles = st.number_input("Mostrar últimos cierres:", min_value=1, max_value=100, value=10)
        df_recortado = df_historico.iloc[::-1].head(filas_visibles)
        st.dataframe(df_recortado, use_container_width=True)
    else:
        st.info("Aún no hay cierres registrados en el historial general.")

# PESTAÑA 2: MODIFICACIÓN MANUAL DETALLADA
with tab_gestion:
    st.markdown("### 🛠️ Control y Edición de Productos")
    df = st.session_state.df
    if df.empty:
        st.info("El inventario está vacío.")
    else:
        col_busca1, col_busca2 = st.columns(2)
        
        with col_busca1:
            buscar = st.text_input("🔍 Buscar producto por nombre (Edición):", "").strip()
            
        with col_busca2:
            codigo_escaneado = st.text_input("⚡ Escanear código para buscar:", key="scanner_edicion_manual").strip()
        
        # 🎯 FILTRADO LOGICO: El escáner tiene prioridad absoluta
        if codigo_escaneado:
            df_filtrado = df[df.get("Código", "").astype(str).str.replace(r'\.0$', '', regex=True) == codigo_escaneado]
            if df_filtrado.empty:
                st.error(f"❌ No se encontró ningún producto con el código: '{codigo_escaneado}'")
        else:
            df_filtrado = df[df["Producto"].str.contains(buscar, case=False, na=False)] if buscar else df
        
        if df_filtrado.empty and not codigo_escaneado:
            st.warning("No se encontraron productos.")
            
        elif not df_filtrado.empty:
            producto_a_editar = st.selectbox("Seleccioná el producto:", df_filtrado["Producto"].unique(), key="selector_global")
            datos_prod = df[df["Producto"] == producto_a_editar].iloc[0]
            
            with st.form(f"form_edicion_{producto_a_editar}"):
                st.write(f"✍️ **Modificando:** {producto_a_editar}")
                nuevo_nombre = st.text_input("📦 Nombre del Producto:", value=producto_a_editar, key=f"nm_{producto_a_editar}").strip()
                
                # --- LIMPIEZA DEL CÓDIGO (Chau .0) ---
                codigo_actual = str(datos_prod.get("Código", ""))
                if codigo_actual.endswith(".0"):
                    codigo_actual = codigo_actual[:-2] # Le recorta los dos últimos caracteres
                if codigo_actual.lower() in ["nan", "none", "<na>"]:
                    codigo_actual = ""
                    
                nuevo_codigo = st.text_input("🏷️ Código de Barras (Escanealo acá si está en blanco):", value=codigo_actual, key=f"cd_{producto_a_editar}")
                
                c_edit1, c_edit2, c_edit3, c_edit4 = st.columns(4)
                with c_edit1:
                    # --- LIMPIEZA DEL PRECIO ---
                    precio_excel = float(datos_prod.get("Precio Venta", 0))
                    # Si es un número redondo sin centavos reales, lo forzamos a entero
                    if precio_excel.is_integer():
                        nuevo_precio = st.number_input("Precio Venta ($)", min_value=0, value=int(precio_excel), step=50, key=f"pr_{producto_a_editar}")
                    else:
                        nuevo_precio = st.number_input("Precio Venta ($)", min_value=0.0, value=precio_excel, step=0.5, key=f"pr_{producto_a_editar}")
                
                with c_edit2:
                    # Aseguramos que el stock sea entero, pasando primero por float para evitar errores de lectura
                    stock_actual = int(float(datos_prod.get("Stock Actual", 0)))
                    nuevo_stock = st.number_input("Stock Actual", min_value=0, value=stock_actual, key=f"st_{producto_a_editar}")
                
                with c_edit3:
                    stock_minimo = int(float(datos_prod.get("Stock Mínimo", 0)))
                    nuevo_minimo = st.number_input("Stock Mínimo", min_value=0, value=stock_minimo, key=f"mn_{producto_a_editar}")
                
                with c_edit4:
                    try:
                        fecha_v_actual = datetime.strptime(str(datos_prod.get("Fecha Vencimiento", hoy)), '%Y-%m-%d')
                    except:
                        fecha_v_actual = hoy
                    nueva_fecha_v = st.date_input("Nueva Fecha", value=fecha_v_actual, key=f"fc_{producto_a_editar}")
                
                col_btn1, col_btn2 = st.columns([1, 5])
                with col_btn1:
                    if st.form_submit_button("💾 Guardar"):
                        # Al guardar, lo guardamos explícitamente como texto limpio
                        st.session_state.df.loc[st.session_state.df["Producto"] == producto_a_editar, ["Código", "Precio Venta", "Stock Actual", "Stock Mínimo", "Fecha Vencimiento"]] = [str(nuevo_codigo), nuevo_precio, nuevo_stock, nuevo_minimo, nueva_fecha_v.strftime('%Y-%m-%d')]
                        if guardar_inventario(st.session_state.df):
                            st.success("¡Cambios guardados!")
                            st.session_state.sonido_a_reproducir = "exito"
                            st.rerun()
                with col_btn2:
                    if st.form_submit_button("🗑️ Eliminar"):
                        st.session_state.df = st.session_state.df[st.session_state.df["Producto"] != producto_a_editar]
                        if guardar_inventario(st.session_state.df):
                            st.success("Producto eliminado.")
                            st.rerun()
                            
        df_visual = st.session_state.df.copy()
        
        # Forzamos la columna a texto, le volamos el .0 y reemplazamos los vacíos por nada
        if "Código" in df_visual.columns:
            df_visual["Código"] = df_visual["Código"].astype(str).str.replace(r'\.0$', '', regex=True).replace(['nan', 'None', '<NA>'], '')
            
        st.dataframe(df_visual, use_container_width=True)
# PESTAÑA 3: CARGA TRADICIONAL
with tab_carga:
    st.markdown("### 📥 Registrar Producto Nuevo")
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
        
        if st.form_submit_button("➕ Agregar al Inventario"):
            df = st.session_state.df
            if not producto_input:
                st.error("El nombre no puede estar vacío.")
            elif cod_input and (cod_input in df["Código"].values and cod_input != ""):
                st.error("El código ya existe.")
            elif producto_input in df["Producto"].values:
                st.error("El producto ya existe.")
            else:
                nueva_fila = pd.DataFrame([{"Código": cod_input, "Producto": producto_input, "Precio Venta": precio_input, "Stock Actual": stock_input, "Stock Mínimo": minimo_input, "Fecha Vencimiento": fecha_venc_input.strftime('%Y-%m-%d')}])
                st.session_state.df = pd.concat([df, nueva_fila], ignore_index=True)
                if guardar_inventario(st.session_state.df):
                    st.success("¡Guardado!")
                    st.session_state.sonido_a_reproducir = "exito"
                    st.rerun()

# PESTAÑA 4: REPORTES DE VENCIMIENTOS
with tab_vencimientos:
    st.markdown("### 🚨 Control Crítico de Stock y Fechas")
    df = st.session_state.df
    
    if df.empty:
        st.info("No hay productos cargados.")
    else:
        # --- NUEVA SECCIÓN: REPOSICIÓN ---
        st.markdown("#### 🛒 Productos a Reponer")
        # Convertimos a numérico para asegurar el filtrado
        df["Stock Actual"] = pd.to_numeric(df["Stock Actual"])
        df["Stock Mínimo"] = pd.to_numeric(df["Stock Mínimo"])
        
        reposiciones = df[df["Stock Actual"] <= df["Stock Mínimo"]].copy()
        
        if not reposiciones.empty:
            reposiciones["Faltante"] = reposiciones["Stock Mínimo"] - reposiciones["Stock Actual"]
            st.dataframe(
                reposiciones[["Producto", "Stock Actual", "Stock Mínimo", "Faltante"]]
                .style.background_gradient(cmap="OrRd", subset=["Faltante"]), 
                use_container_width=True
            )
        else:
            st.success("✅ ¡Todo el stock está al día!")

        st.markdown("---")

        # --- TU SECCIÓN ORIGINAL DE VENCIMIENTOS ---
        lista_vencidos, lista_por_vencer = [], []
        hoy = datetime.now()
        
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
            st.dataframe(pd.DataFrame(lista_vencidos).style.background_gradient(cmap="Reds", subset=["Días Vencido"]), use_container_width=True)
        else: 
            st.success("🎉 ¡Ninguno vencido!")
        
        st.markdown("---")
        st.markdown("#### ⚠️ Próximos a Vencer (Menos de 15 días)")
        if lista_por_vencer: 
            st.dataframe(pd.DataFrame(lista_por_vencer).style.background_gradient(cmap="YlOrRd", subset=["Días Restantes"]), use_container_width=True)
        else: 
            st.success("👍 Sin vencimientos cercanos.")


# ==========================================
# 🤖 PESTAÑA 5: ASISTENTE AGENTE IA (MODIFICACIONES POR CHAT)
# ==========================================

with tab_ia:
    st.markdown("### 🤖 Tu Asistente Operativo Inteligente")
    st.write("Hablale a tu asistente para gestionar el inventario o **pasá el lector de códigos directamente en el chat**.")
    
    ARCHIVO_KEY = "api_key.txt"
    key_saved = ""
    
    if os.path.exists(ARCHIVO_KEY):
        with open(ARCHIVO_KEY, "r") as f:
            key_saved = f.read().strip()
            
    gemini_key = st.text_input(
        "API Key",
        value=key_saved,
        type="password"
    ).strip()
    
    if gemini_key and gemini_key != key_saved:
        with open(ARCHIVO_KEY, "w") as f:
            f.write(gemini_key)
        st.success("✅ ¡Clave guardada de forma segura!")
    
    st.markdown("---")
    
    # Renderizar el historial de chat interactivo visible
    for mensaje in st.session_state.historial_chat:
        with st.chat_message(mensaje["role"]):
            st.write(mensaje["content"])
            
    # ÚNICA CAJA DE ENTRADA: Sirve para escribir o para gatillar el escáner
    prompt_chat = st.chat_input("Escribí una orden o pasá el escáner acá...")
    
    if prompt_chat:
        # 1. Mostramos en pantalla exactamente lo que entró (ej: el número del código o el texto)
        with st.chat_message("user"):
            st.write(prompt_chat)
        st.session_state.historial_chat.append({"role": "user", "content": prompt_chat})
        
        if not gemini_key:
            respuesta_visible = "⚠️ **Por favor, ingresá tu API Key de Gemini arriba para poder operar.**"
            with st.chat_message("assistant"):
                st.write(respuesta_visible)
            st.session_state.historial_chat.append({"role": "assistant", "content": respuesta_visible})
        else:
            with st.spinner("Procesando..."):
                texto_ingresado = prompt_chat.strip()
                df_actual = st.session_state.df
                
                # 2. FILTRO INVISIBLE: ¿Es un código de barras o es texto normal?
                # Si tiene solo números y al menos 4 dígitos, asumimos que fue el lector
                if texto_ingresado.isdigit() and len(texto_ingresado) >= 4:
                    if not df_actual.empty:
                        codigos_limpios = df_actual["Código"].astype(str).str.replace(r'\.0$', '', regex=True)
                        match = df_actual[codigos_limpios == texto_ingresado]
                        
                        if not match.empty:
                            nombre_prod = match.iloc[0]["Producto"]
                            prompt_a_enviar_ia = f"Acabo de escanear el producto: '{nombre_prod}' (Código: {texto_ingresado}). Mostrame sus datos actuales de forma breve y preguntame qué le modificamos."
                        else:
                            prompt_a_enviar_ia = f"Acabo de escanear el código: '{texto_ingresado}', pero no está en el inventario. Preguntame si lo quiero agregar como nuevo producto y guíame."
                    else:
                        prompt_a_enviar_ia = f"Acabo de escanear el código: '{texto_ingresado}', pero el inventario está vacío. Preguntame cómo se llama para agregarlo."
                else:
                    # Si tiene letras, es una orden normal tipeada por vos
                    prompt_a_enviar_ia = texto_ingresado
                
                # 3. PREPARACIÓN DEL CONTEXTO PARA LA IA
                resumen_inventario = st.session_state.df.to_string(index=False)
                fecha_hoy_humano = datetime.now().strftime("%d/%m/%Y")
                
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={gemini_key}"
                headers = {'Content-Type': 'application/json'}
                
                instruccion_sistema = (
                    "Sos un Agente IA operativo para un kiosco. Tu tarea es analizar lo que te pide el dueño "
                    "y decidir si quiere realizar una ACCIÓN en el inventario o solo hacer una CONSULTA.\n"
                    f"Hoy es exactamente {fecha_hoy_humano}.\n\n"
                    f"--- INVENTARIO ACTUAL ---\n{resumen_inventario}\n\n"
                    "DEBÉS RESPONDER ÚNICAMENTE EN FORMATO JSON RECTO, SIN TEXTO AFUERA NI BLOQUES DE CÓDIGO.\n"
                    "El formato DEBE ser exactamente este formato estructurado:\n"
                    "{\n"
                    '  "accion": "AGREGAR" | "MODIFICAR" | "ELIMINAR" | "NINGUNA",\n'
                    '  "datos": {\n'
                    '    "Código": "string o vacío",\n'
                    '    "Producto": "Nombre exacto",\n'
                    '    "Precio Venta": 0.0,\n'
                    '    "Stock Actual": 0,\n'
                    '    "Stock Mínimo": 5,\n'
                    '    "Fecha Vencimiento": "YYYY-MM-DD o vacío"\n'
                    "  },\n"
                    '  "mensaje": "Tu respuesta amigable en español contándole al dueño lo que hiciste o preguntándole qué necesita hacer."\n'
                    "}\n\n"
                    "Reglas:\n"
                    "1. Si te pide AGREGAR: busca completar todos los campos según su texto. Si no define stock mínimo, usa 5.\n"
                    "2. Si te pide MODIFICAR: el nombre del producto debe coincidir con uno existente. Solo altera los campos que te pidió cambiar, mantén el resto igual.\n"
                    "3. Si es solo un escaneo o pregunta: usa 'NINGUNA' en accion y contestá en 'mensaje'."
                )
                
                payload = {
                    "contents": [{
                        "parts": [{"text": f"{instruccion_sistema}\n\nPetición del dueño: {prompt_a_enviar_ia}"}]
                    }]
                }
                
                # 4. CONEXIÓN CON GEMINI Y EJECUCIÓN
                try:
                    response = requests.post(url, headers=headers, json=payload)
                    if response.status_code == 200:
                        resultado_raw = response.json()['candidates'][0]['content']['parts'][0]['text'].strip()
                        
                        if resultado_raw.startswith("```"):
                            resultado_raw = resultado_raw.replace("```json", "").replace("```", "").strip()
                        
                        paquete = json.loads(resultado_raw)
                        accion = paquete.get("accion", "NINGUNA")
                        datos = paquete.get("datos", {})
                        respuesta_visible = paquete.get("mensaje", "Orden procesada.")
                        
                        hubo_cambios = False
                        
                        if accion == "AGREGAR":
                            nueva_fila = pd.DataFrame([{
                                "Código": str(datos.get("Código", "")),
                                "Producto": str(datos.get("Producto", "Nuevo Producto")),
                                "Precio Venta": float(datos.get("Precio Venta", 0.0)),
                                "Stock Actual": int(datos.get("Stock Actual", 0)),
                                "Stock Mínimo": int(datos.get("Stock Mínimo", 5)),
                                "Fecha Vencimiento": str(datos.get("Fecha Vencimiento", ""))
                            }])
                            st.session_state.df = pd.concat([df_actual, nueva_fila], ignore_index=True)
                            hubo_cambios = True
                            
                        elif accion == "MODIFICAR":
                            prod_nombre = datos.get("Producto")
                            match = df_actual[df_actual["Producto"].str.contains(prod_nombre, case=False, na=False)]
                            if not match.empty:
                                idx = match.index[0]
                                if "Precio Venta" in datos and datos["Precio Venta"] is not None:
                                    st.session_state.df.at[idx, "Precio Venta"] = float(datos["Precio Venta"])
                                if "Stock Actual" in datos and datos["Stock Actual"] is not None:
                                    st.session_state.df.at[idx, "Stock Actual"] = int(datos["Stock Actual"])
                                if "Stock Mínimo" in datos and datos["Stock Mínimo"] is not None:
                                    st.session_state.df.at[idx, "Stock Mínimo"] = int(datos["Stock Mínimo"])
                                if "Fecha Vencimiento" in datos and datos["Fecha Vencimiento"]:
                                    st.session_state.df.at[idx, "Fecha Vencimiento"] = str(datos["Fecha Vencimiento"])
                                hubo_cambios = True
                                
                        elif accion == "ELIMINAR":
                            prod_nombre = datos.get("Producto")
                            st.session_state.df = df_actual[~df_actual["Producto"].str.contains(prod_nombre, case=False, na=False)]
                            hubo_cambios = True
                        
                        if hubo_cambios:
                            if guardar_inventario(st.session_state.df):
                                st.session_state.sonido_a_reproducir = "exito"
                                
                    elif response.status_code == 503:
                        respuesta_visible = "⏳ Los servidores de Google están saturados. Esperá un minuto."
                    elif response.status_code == 429:
                        respuesta_visible = "🛑 La versión gratuita tiene un límite. Esperá 60 segundos."
                    else:
                        respuesta_visible = f"❌ Error de conexión con Gemini (Código {response.status_code})."
                except Exception as e:
                    respuesta_visible = f"❌ Error procesando el comando: {str(e)}"
                    
            with st.chat_message("assistant"):
                st.write(respuesta_visible)
            st.session_state.historial_chat.append({"role": "assistant", "content": respuesta_visible})
            
            if 'hubo_cambios' in locals() and hubo_cambios:
                st.rerun()
# ==========================================
# 🔊 DISPARADOR DE AUDIO GLOBAL
# ==========================================
if st.session_state.sonido_a_reproducir:
    emitir_sonido_navegador(st.session_state.sonido_a_reproducir)
    st.session_state.sonido_a_reproducir = None