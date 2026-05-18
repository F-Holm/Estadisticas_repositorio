#!/usr/bin/env python3
import os
import shutil
import subprocess
import sys
import tempfile
from collections import defaultdict

def obtener_estadisticas_git(repo_dir):
    # Ejecuta el comando de git apuntando al directorio temporal
    comando = ["git", "-C", repo_dir, "log", "--use-mailmap", "--numstat", "--pretty=format:AUTOR:%aN"]
    
    try:
        resultado = subprocess.run(comando, capture_output=True, text=True, check=True, encoding='utf-8')
    except subprocess.CalledProcessError as e:
        print(f"\nError al procesar el historial de Git: {e.stderr}")
        return None

    stats = defaultdict(lambda: {"commits": 0, "lineas_agregadas": 0, "lineas_eliminadas": 0})
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

    return stats

def mostrar_reporte(stats):
    if not stats:
        print("No se encontraron estadísticas o el repositorio está vacío.")
        return

    ancho_autor = max(max(len(autor) for autor in stats.keys()), 25)
    ancho_num = 12
    
    formato_cabecera = f"{{:<{ancho_autor}}} | {{:>{ancho_num}}} | {{:>{ancho_num}}} | {{:>{ancho_num}}} | {{:>{ancho_num}}}"
    
    def formatear_miles(valor):
        return f"{valor:,}".replace(",", ".")

    cabecera = formato_cabecera.format("Autor", "Commits", "Líneas +", "Líneas -", "Total Modif.")
    print(f"\n{cabecera}")
    print("-" * len(cabecera))
    
    autores_ordenados = sorted(stats.items(), key=lambda x: x[1]["commits"], reverse=True)
    
    for autor, datos in autores_ordenados:
        total_modificadas = datos["lineas_agregadas"] + datos["lineas_eliminadas"]
        
        c_str = formatear_miles(datos['commits'])
        pos_str = formatear_miles(datos['lineas_agregadas'])
        neg_str = formatear_miles(datos['lineas_eliminadas'])
        tot_str = formatear_miles(total_modificadas)
        
        print(f"{{:<{ancho_autor}}} | {{:>{ancho_num}}} | {{:>{ancho_num}}} | {{:>{ancho_num}}} | {{:>{ancho_num}}}".format(
            autor, c_str, pos_str, neg_str, tot_str
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
    # Verificar si git está instalado antes de hacer nada
    if shutil.which("git") is None:
        print("Error: El comando 'git' no está instalado o no se encuentra en el PATH.")
        sys.exit(1)

    url_repo = input("Ingresa la URL del repositorio de GitHub: ").strip()
    if not url_repo:
        print("URL no válida.")
        return

    # Creamos un directorio temporal seguro dentro de /tmp (o el equivalente del OS)
    print("\n[+] Creando entorno temporal...")
    temp_dir = tempfile.mkdtemp(prefix="git_analysis_")

    try:
        print(f"[+] Clonando el repositorio en una carpeta temporal...")
        # Clonamos con --bare ya que no necesitamos los archivos físicos de trabajo, solo el historial de Git.
        # Esto hace que la clonación sea muchísimo más rápida.
        subprocess.run(["git", "clone", "--bare", url_repo, temp_dir], check=True, capture_output=True)
        
        print("[+] Analizando el historial de commits...")
        estadisticas = obtener_estadisticas_git(temp_dir)
        
        if estadisticas:
            mostrar_reporte(estadisticas)

    except subprocess.CalledProcessError as e:
        print(f"\n[X] Error al clonar el repositorio. Verifica la URL y tus permisos de acceso.")
        print(f"Detalle del error: {e.stderr.decode('utf-8', errors='ignore').strip()}")
    finally:
        # Garantizamos la limpieza pase lo que pase en el bloque try
        print("\n[-] Iniciando limpieza del sistema...")
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
            print("[✓] Repositorio clonado temporal eliminado.")
        
        limpiar_cache_python()
        print("[✓] Proceso finalizado.")

if __name__ == "__main__":
    main()
