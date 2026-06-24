import pandas as pd
import os
from datetime import datetime

# Volvemos a .xlsx para trabajar directamente con Excel
NOMBRE_ARCHIVO = "Inventario_Quiosco.xlsx"

def cargar_inventario():
    # Si el archivo de Excel ya existe, lo lee. Si no, crea uno nuevo.
    if os.path.exists(NOMBRE_ARCHIVO):
        try:
            df = pd.read_excel(NOMBRE_ARCHIVO)
            # Asegura que las fechas se mantengan en el formato año-mes-día
            if "Fecha Vencimiento" in df.columns:
                df["Fecha Vencimiento"] = pd.to_datetime(df["Fecha Vencimiento"]).dt.strftime('%Y-%m-%d')
            return df
        except Exception as e:
            print(f"Aviso: No se pudo leer el archivo de Excel. Se iniciará un inventario nuevo. Error: {e}")
    
    columnas = ["Producto", "Stock Actual", "Stock Mínimo", "Fecha Vencimiento"]
    return pd.DataFrame(columns=columnas)

def guardar_inventario(df):
    try:
        df.to_excel(NOMBRE_ARCHIVO, index=False)
        print(f"\n[✔] Datos guardados con éxito en '{NOMBRE_ARCHIVO}'.")
    except Exception as e:
        print(f"\n❌ Error al guardar: Asegúrate de tener el archivo de Excel cerrado antes de guardar. Detalle: {e}")

def mostrar_inventario(df):
    if df.empty:
        print("\nEl inventario está vacío. Agrega productos seleccionando la opción 2.")
        return

    print("\n======================================================================")
    print("                        INVENTARIO Y ALERTAS")
    print("======================================================================")
    hoy = datetime.now()
    
    for idx, fila in df.iterrows():
        producto = fila["Producto"]
        stock = int(fila["Stock Actual"])
        minimo = int(fila["Stock Mínimo"])
        fecha_venc_str = str(fila["Fecha Vencimiento"]).split()[0]
        
        # 1. Alerta de Stock Mínimo
        alerta_stock = ""
        if stock <= minimo:
            alerta_stock = "⚠️ [¡REPONER STOCK!]"
        
        # 2. Alerta de Vencimiento
        alerta_venc = ""
        try:
            fecha_venc = datetime.strptime(fecha_venc_str, '%Y-%m-%d')
            dias_restantes = (fecha_venc - hoy).days
            if dias_restantes < 0:
                alerta_venc = f"❌ [VENCIDO hace {-dias_restantes} días]"
            elif dias_restantes <= 15:
                alerta_venc = f"⚠️ [VENCE EN {dias_restantes} DÍAS]"
        except ValueError:
            alerta_venc = "[Fecha sin formato válido]"

        # Imprime la fila ordenada en columnas de la terminal
        print(f"- {producto:<25} | Stock: {stock}/{minimo} {alerta_stock:<18} | Vence: {fecha_venc_str} {alerta_venc}")
    print("======================================================================")

def agregar_o_actualizar(df):
    print("\n--- AGREGAR / ACTUALIZAR PRODUCTO ---")
    producto = input("Nombre del producto: ").strip()
    
    if not producto:
        print("El nombre del producto no puede estar vacío.")
        return df

    try:
        stock = int(input("Stock Actual (Cantidad en estantería): "))
        minimo = int(input("Stock Mínimo (Límite para que te avise que falta): "))
        fecha_venc = input("Fecha de Vencimiento (Formato AÑO-MES-DÍA, ej. 2026-10-31): ").strip()
        
        # Valida el formato de fecha
        datetime.strptime(fecha_venc, '%Y-%m-%d')
    except ValueError:
        print("\n❌ Error: El stock debe ser un número entero y la fecha debe cumplir el formato estricto AÑO-MES-DÍA.")
        return df

    # Si el producto ya existe, lo actualiza. Si no, crea una fila nueva.
    if producto in df["Producto"].values:
        df.loc[df["Producto"] == producto, ["Stock Actual", "Stock Mínimo", "Fecha Vencimiento"]] = [stock, minimo, fecha_venc]
        print(f"\n[✔] Producto '{producto}' actualizado correctamente.")
    else:
        nueva_fila = pd.DataFrame([{
            "Producto": producto,
            "Stock Actual": stock,
            "Stock Mínimo": minimo,
            "Fecha Vencimiento": fecha_venc
        }])
        df = pd.concat([df, nueva_fila], ignore_index=True)
        print(f"\n[✔] Producto '{producto}' agregado con éxito.")
    
    return df

def menu_principal():
    df = cargar_inventario()
    
    while True:
        print("\n>>> SISTEMA DE CONTROL DE STOCK (EXCEL) <<<")
        print("1. Ver inventario completo y alertas")
        print("2. Agregar o modificar un producto")
        print("3. Guardar cambios")
        print("4. Guardar y Salir")
        
        opcion = input("\nSelecciona una opción (1-4): ").strip()
        
        if opcion == "1":
            mostrar_inventario(df)
        elif opcion == "2":
            df = agregar_o_actualizar(df)
        elif opcion == "3":
            guardar_inventario(df)
        elif opcion == "4":
            guardar_inventario(df)
            print("\n¡Cambios asegurados! Sistema cerrado correctamente.")
            break
        else:
            print("\n❌ Opción inválida. Elige un número del 1 al 4.")

if __name__ == "__main__":
    menu_principal()
    # Agregamos esto para que la consola no se cierre inmediatamente en Windows
    input("\nPresiona ENTER para salir...")