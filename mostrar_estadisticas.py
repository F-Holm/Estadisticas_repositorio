#!/usr/bin/env python3

import os
import shutil
import subprocess
import sys
import tempfile
from collections import defaultdict

def obtener_metricas_actuales_por_autor(repo_dir):
    """
    Ejecuta git blame sobre todos los archivos del repositorio para contar
    las líneas y los caracteres vigentes que le pertenecen actualmente a cada autor.
    """
    metricas_por_autor = defaultdict(lambda: {"lineas": 0, "caracteres": 0})
    
    # 1. Listar todos los archivos rastreados en el repositorio actual
    cmd_files = ["git", "-C", repo_dir, "ls-files"]
    try:
        res_files = subprocess.run(cmd_files, capture_output=True, text=True, check=True, encoding='utf-8')
    except subprocess.CalledProcessError:
        return metricas_por_autor

    archivos = res_files.stdout.splitlines()

    # 2. Correr git blame para cada archivo y extraer el autor y el contenido de la línea
    for archivo in archivos:
        # Usamos --line-porcelain para obtener el autor y el contenido original de la línea (antepuesto por un tabulador)
        cmd_blame = ["git", "-C", repo_dir, "blame", "--line-porcelain", archivo]
        try:
            res_blame = subprocess.run(cmd_blame, capture_output=True, text=True, check=True, encoding='utf-8', errors='ignore')
            
            autor_actual = None
            for linea in res_blame.stdout.splitlines():
                if linea.startswith("author "):
                    autor_actual = linea.replace("author ", "").strip()
                elif linea.startswith("\t") and autor_actual:
                    # Las líneas que empiezan con tabulador (`\t`) contienen el código/texto real
                    contenido_linea = linea[1:] # Quitamos el tabulador inicial
                    
                    metricas_por_autor[autor_actual]["lineas"] += 1
                    metricas_por_autor[autor_actual]["caracteres"] += len(contenido_linea)
        except subprocess.CalledProcessError:
            # Saltamos archivos que puedan dar problemas (ej. submódulos o binarios mal trackeados)
            continue

    return metricas_por_autor

def obtener_estadisticas_git(repo_dir):
    # Ejecuta el comando de git apuntando al directorio temporal
    comando = ["git", "-C", repo_dir, "log", "--use-mailmap", "--numstat", "--pretty=format:AUTOR:%aN"]
    
    try:
        resultado = subprocess.run(comando, capture_output=True, text=True, check=True, encoding='utf-8')
    except subprocess.CalledProcessError as e:
        print(f"\nError al procesar el historial de Git: {e.stderr}")
        return None

    stats = defaultdict(lambda: {"commits": 0, "lineas_agregadas": 0, "lineas_eliminadas": 0, "lineas_actuales": 0, "caracteres_actuales": 0})
    autor_actual = None

    for linea in resultado.stdout.splitlines():
        linea = linea.strip()
        if not linea:
            continue
        
        if linea.startswith("AUTOR:"):
            autor_actual = linea.replace("AUTOR:", "")
            stats[autor_actual]["commits"] += 1
        elif autor_actual:
            partes = linea.split('\t')
            if len(partes) >= 2:
                agregadas, eliminadas = partes[0], partes[1]
                if agregadas != '-' and eliminadas != '-':
                    stats[autor_actual]["lineas_agregadas"] += int(agregadas)
                    stats[autor_actual]["lineas_eliminadas"] += int(eliminadas)

    # Integrar el conteo de líneas y caracteres actuales (git blame avanzado)
    print("[+] Calculando propiedad de las líneas y caracteres actuales (git blame)...")
    metricas_actuales = obtener_metricas_actuales_por_autor(repo_dir)
    for autor, datos in metricas_actuales.items():
        stats[autor]["lineas_actuales"] = datos["lineas"]
        stats[autor]["caracteres_actuales"] = datos["caracteres"]

    return stats

def mostrar_reporte(stats):
    if not stats:
        print("No se encontraron estadísticas o el repositorio está vacío.")
        return

    # Calcular totales generales para obtener los porcentajes
    total_commits = 0
    total_agregadas = 0
    total_eliminadas = 0
    total_modificadas_global = 0
    total_actuales = 0
    total_caracteres = 0

    for datos in stats.values():
        total_commits += datos["commits"]
        total_agregadas += datos["lineas_agregadas"]
        total_eliminadas += datos["lineas_eliminadas"]
        total_modificadas_global += (datos["lineas_agregadas"] + datos["lineas_eliminadas"])
        total_actuales += datos["lineas_actuales"]
        total_caracteres += datos["caracteres_actuales"]

    # Ajustamos el ancho para dar suficiente espacio a las columnas descriptivas
    ancho_autor = max(max(len(autor) for autor in stats.keys()), 25)
    ancho_num = 23 # Se aumentó un poco para que entren bien los nombres de columnas más largos
    
    formato_cabecera = f"{{:<{ancho_autor}}} | {{:>{ancho_num}}} | {{:>{ancho_num}}} | {{:>{ancho_num}}} | {{:>{ancho_num}}} | {{:>{ancho_num}}} | {{:>{ancho_num}}}"
    
    def formatear_miles(valor):
        return f"{valor:,}".replace(",", ".")

    def generar_celda(valor, total):
        str_cant = formatear_miles(valor)
        porcentaje = (valor / total * 100) if total > 0 else 0
        str_porcentaje = f"{porcentaje:>5.1f}"
        return f"{str_cant} ({str_porcentaje}%)"

    cabecera = formato_cabecera.format("Autor", "Commits (%)", "Líneas + (%)", "Líneas - (%)", "Total Modif. (%)", "Líneas en main (%)", "Caracteres en main (%)")
    print(f"\n{cabecera}")
    print("-" * len(cabecera))
    
    autores_ordenados = sorted(stats.items(), key=lambda x: x[1]["commits"], reverse=True)
    
    for autor, datos in autores_ordenados:
        total_modificadas = datos["lineas_agregadas"] + datos["lineas_eliminadas"]
        
        c_str = generar_celda(datos['commits'], total_commits)
        pos_str = generar_celda(datos['lineas_agregadas'], total_agregadas)
        neg_str = generar_celda(datos['lineas_eliminadas'], total_eliminadas)
        tot_str = generar_celda(total_modificadas, total_modificadas_global)
        act_str = generar_celda(datos['lineas_actuales'], total_actuales)
        char_str = generar_celda(datos['caracteres_actuales'], total_caracteres)
        
        print(formato_cabecera.format(
            autor, c_str, pos_str, neg_str, tot_str, act_str, char_str
        ))

def limpiar_cache_python():
    """Busca y elimina carpetas __pycache__ en el directorio del script actual"""
    dir_actual = os.path.dirname(os.path.abspath(__file__))
    eliminado = False
    
    for raiz, dirs, _ in os.walk(dir_actual):
        if "__pycache__" in dirs:
            ruta_cache = os.path.join(raiz, "__pycache__")
            try:
                shutil.rmtree(ruta_cache)
                eliminado = True
            except Exception as e:
                print(f"No se pudo eliminar {ruta_cache}: {e}")
    
    if eliminado:
        print("[✓] Caché de Python (__pycache__) eliminada con éxito.")

def main():
    if shutil.which("git") is None:
        print("Error: El comando 'git' no está instalado o no se encuentra en el PATH.")
        sys.exit(1)

    if len(sys.argv) > 1:
        url_repo = sys.argv[1].strip()
    else:
        url_repo = input("Ingresa la URL del repositorio de GitHub: ").strip()

    if not url_repo:
        print("URL no válida.")
        return

    print(f"\n[+] Repositorio a analizar: {url_repo}")
    print("[+] Creando entorno temporal...")
    temp_dir = tempfile.mkdtemp(prefix="git_analysis_")

    try:
        print(f"[+] Clonando el repositorio en una carpeta temporal...")
        subprocess.run(["git", "clone", url_repo, temp_dir], check=True, capture_output=True)
        
        print("[+] Analizando el historial de commits...")
        estadisticas = obtener_estadisticas_git(temp_dir)
        
        if estadisticas:
            mostrar_reporte(estadisticas)

    except subprocess.CalledProcessError as e:
        print(f"\n[X] Error al clonar el repositorio. Verifica la URL y tus permisos de acceso.")
        print(f"Detalle del error: {e.stderr.decode('utf-8', errors='ignore').strip()}")
    finally:
        print("\n[-] Iniciando limpieza del sistema...")
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
            print("[✓] Repositorio clonado temporal eliminado.")
        
        limpiar_cache_python()
        print("[✓] Proceso finalizado.")

if __name__ == "__main__":
    main()
