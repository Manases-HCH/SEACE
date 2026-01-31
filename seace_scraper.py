
import sys
import logging
from datetime import datetime
from time import sleep
import re

import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class SeaceScraperCompleto:
    
    def __init__(self, headless: bool = True):  # Cambiado de False a True
        self.headless = headless
        self.driver = None
        self.resultados = []
    
    def iniciar(self):
        """Inicia el navegador"""
        logger.info("🚀 Iniciando navegador...")
        
        options = Options()
        
        # CRITICAL: Opciones obligatorias para Cloud Run
        options.add_argument('--headless=new')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--disable-software-rasterizer')
        options.add_argument('--disable-extensions')
        
        # Optimizaciones
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--window-size=1920,1080')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        
        # Desactivar carga de imágenes
        prefs = {
            "profile.managed_default_content_settings.images": 2,
            "profile.default_content_setting_values.notifications": 2
        }
        options.add_experimental_option("prefs", prefs)
        
        # IMPORTANT: Usar Chrome del sistema (no ChromeDriverManager)
        try:
            # Intentar sin service (chromedriver en PATH)
            self.driver = webdriver.Chrome(options=options)
            logger.info("✅ Chrome iniciado desde PATH")
        except Exception as e:
            logger.info(f"⚠️ Intentando con ruta explícita: {e}")
            # Fallback: ruta explícita
            service = Service('/usr/local/bin/chromedriver')
            self.driver = webdriver.Chrome(service=service, options=options)
            logger.info("✅ Chrome iniciado con ruta explícita")
        
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        logger.info("✅ Navegador iniciado\n")
    
    def cerrar(self):
        """Cierra el navegador"""
        if self.driver:
            self.driver.quit()
    
    def click(self, xpath: str, wait_after: float = 0.3):
        """Hace clic usando JavaScript con espera configurable"""
        elem = self.driver.find_element(By.XPATH, xpath)
        self.driver.execute_script("arguments[0].scrollIntoView(true);", elem)
        sleep(0.2)  # Reducido de 0.5
        self.driver.execute_script("arguments[0].click();", elem)
        sleep(wait_after)  # Configurable
    
    def escribir(self, xpath: str, texto: str):
        """Escribe en un campo"""
        elem = self.driver.find_element(By.XPATH, xpath)
        self.driver.execute_script("arguments[0].value = '';", elem)
        self.driver.execute_script("arguments[0].value = arguments[1];", elem, texto)
        self.driver.execute_script("arguments[0].dispatchEvent(new Event('change'));", elem)
        sleep(0.2)  # Reducido de 0.3
    
    def buscar_y_extraer(self, fecha_inicio: datetime, fecha_fin: datetime):
        """Ejecuta la búsqueda y extrae los datos"""
        
        logger.info(f"📅 Rango: {fecha_inicio.strftime('%d/%m/%Y')} → {fecha_fin.strftime('%d/%m/%Y')}")
        
        # Cargar página
        self.driver.get("https://prod2.seace.gob.pe/seacebus-uiwd-pub/buscadorPublico/buscadorPublico.xhtml")
        logger.info("📄 Página cargada")
        sleep(2)  # Reducido de 3 a 2
        
        # Pestaña correcta
        logger.info("🔖 Seleccionando pestaña...")
        self.click('//a[@href="#tbBuscador:tab1"]')
        sleep(1)  # Reducido de 2 a 1
        
        # Búsqueda avanzada
        logger.info("🔽 Abriendo búsqueda avanzada...")
        self.click('//fieldset/legend')
        sleep(1)  # Reducido de 2 a 1
        
        # Año
        logger.info(f"📅 Seleccionando año: {fecha_inicio.year}")
        self.click('//*[@id="tbBuscador:idFormBuscarProceso:anioConvocatoria_label"]')
        sleep(0.5)  # Reducido de 1 a 0.5
        self.click(f'//*[@id="tbBuscador:idFormBuscarProceso:anioConvocatoria_panel"]/div/ul/li[@data-label="{fecha_inicio.year}"]')
        sleep(0.5)  # Reducido de 1 a 0.5
        
        # Fechas
        logger.info("📝 Llenando fechas...")
        self.escribir('//*[@id="tbBuscador:idFormBuscarProceso:dfechaInicio_input"]', fecha_inicio.strftime('%d/%m/%Y'))
        self.escribir('//*[@id="tbBuscador:idFormBuscarProceso:dfechaFin_input"]', fecha_fin.strftime('%d/%m/%Y'))
        
        # Buscar
        logger.info("🔎 Buscando...")
        self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        sleep(0.5)  # Reducido de 1 a 0.5
        self.click('//*[@id="tbBuscador:idFormBuscarProceso:btnBuscarSelToken"]')
        logger.info("⏳ Esperando resultados...")
        
        # Esperar con WebDriverWait en lugar de sleep fijo
        try:
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, '//*[@id="tbBuscador:idFormBuscarProceso:dtProcesos_data"]'))
            )
            sleep(2)  # Pequeña espera adicional para estabilidad
        except TimeoutException:
            sleep(5)  # Si falla, esperar un poco más
        
        # Verificar si hay mensaje de "no hay datos"
        try:
            msg = self.driver.find_element(By.XPATH, '//td[contains(text(), "No se encontraron")]')
            if msg.is_displayed():
                logger.info("ℹ️  No hay datos para estas fechas")
                return False
        except NoSuchElementException:
            pass
        
        # Extraer datos de la tabla con paginación
        logger.info("📊 Extrayendo datos de la tabla...")
        self.extraer_datos_con_paginacion()
        
        if self.resultados:
            logger.info(f"✅ Se extrajeron {len(self.resultados)} registros en total")
            return True
        else:
            logger.info("⚠️  No se encontraron datos")
            return False
    
    def extraer_datos_con_paginacion(self):
        """Extrae datos de todas las páginas"""
        pagina_actual = 1
        
        while True:
            try:
                logger.info(f"📄 Procesando página {pagina_actual}...")
                
                # Obtener total de páginas solo la primera vez
                if pagina_actual == 1:
                    total_paginas = self.obtener_total_paginas()
                
                # Extraer datos de la página actual
                registros_pagina = self.extraer_datos_pagina_actual(pagina_actual)
                
                logger.info(f"   ✓ Extraídos {registros_pagina} registros de página {pagina_actual}")
                
                # Si no hay datos, detener
                if registros_pagina == 0:
                    logger.info(f"   ℹ️  Página {pagina_actual} sin datos, deteniendo...")
                    break
                
                # Intentar ir a la siguiente página
                if not self.ir_siguiente_pagina(pagina_actual):
                    logger.info(f"✅ Completado. Total de páginas procesadas: {pagina_actual}")
                    break
                
                pagina_actual += 1
                sleep(2)  # Reducido de 3 a 2
                
            except Exception as e:
                logger.error(f"❌ Error en página {pagina_actual}: {e}")
                break
    
    def extraer_datos_pagina_actual(self, pagina_num: int) -> int:
        """Extrae datos de la página actual y entra a cada ficha - SIN STALE ELEMENT"""
        registros_extraidos = 0
        
        try:
            # Primero contar cuántas filas válidas hay
            filas = self.driver.find_elements(
                By.XPATH,
                '//*[@id="tbBuscador:idFormBuscarProceso:dtProcesos_data"]/tr'
            )
            
            # Filtrar filas válidas (excluir mensajes de error)
            total_filas = 0
            for fila in filas:
                class_attr = fila.get_attribute("class") or ""
                if "ui-datatable-empty-message" not in class_attr:
                    try:
                        celdas = fila.find_elements(By.TAG_NAME, "td")
                        if len(celdas) >= 11:
                            total_filas += 1
                    except:
                        pass
            
            logger.info(f"   📋 Encontradas {total_filas} filas válidas en página {pagina_num}")
            
            # Iterar por índice (SOLUCIÓN AL STALE ELEMENT)
            idx_fila = 0
            while idx_fila < total_filas:
                try:
                    # ⚠️ IMPORTANTE: RE-OBTENER todas las filas en cada iteración
                    filas = self.driver.find_elements(
                        By.XPATH,
                        '//*[@id="tbBuscador:idFormBuscarProceso:dtProcesos_data"]/tr'
                    )
                    
                    # Encontrar la fila válida en la posición idx_fila
                    filas_validas = []
                    for fila in filas:
                        class_attr = fila.get_attribute("class") or ""
                        if "ui-datatable-empty-message" not in class_attr:
                            celdas = fila.find_elements(By.TAG_NAME, "td")
                            if len(celdas) >= 11:
                                filas_validas.append(fila)
                    
                    if idx_fila >= len(filas_validas):
                        break
                    
                    fila = filas_validas[idx_fila]
                    celdas = fila.find_elements(By.TAG_NAME, "td")
                    
                    # ⚠️ CRÍTICO: Extraer TODO el texto ANTES de hacer clic
                    # (para evitar stale elements después de volver)
                    try:
                        texto_celdas = [celda.text.strip() for celda in celdas]
                    except:
                        idx_fila += 1
                        continue
                    
                    # Extraer datos básicos usando el texto ya obtenido
                    datos_basicos = {
                        'N°': texto_celdas[0] if len(texto_celdas) > 0 else '',
                        'Nombre o Sigla de la Entidad': texto_celdas[1] if len(texto_celdas) > 1 else '',
                        'Fecha y Hora de Publicacion': texto_celdas[2] if len(texto_celdas) > 2 else '',
                        'Nomenclatura': texto_celdas[3] if len(texto_celdas) > 3 else '',
                        'Objeto de Contratación': texto_celdas[5] if len(texto_celdas) > 5 else '',
                        'Descripción de Objeto': texto_celdas[6] if len(texto_celdas) > 6 else '',
                        'VR / VE / Cuantía de la contratación': texto_celdas[9] if len(texto_celdas) > 9 else '',
                        'Moneda': texto_celdas[10] if len(texto_celdas) > 10 else ''
                    }
                    
                    # Verificar que no esté vacío
                    if not datos_basicos['Nombre o Sigla de la Entidad']:
                        idx_fila += 1
                        continue
                    
                    logger.info(f"      → Procesando fila {idx_fila + 1}/{total_filas}: N°{datos_basicos['N°']} - {datos_basicos['Nomenclatura']}")
                    
                    # Buscar el botón de ficha en esta fila
                    try:
                        boton_ficha = fila.find_element(
                            By.XPATH,
                            './/img[contains(@id, "grafichaSel")]'
                        )
                        
                        # Hacer clic en el botón de ficha
                        self.driver.execute_script("arguments[0].scrollIntoView(true);", boton_ficha)
                        sleep(0.3)
                        self.driver.execute_script("arguments[0].click();", boton_ficha)
                        
                        # Esperar con WebDriverWait
                        try:
                            WebDriverWait(self.driver, 5).until(
                                EC.presence_of_element_located((By.XPATH, '//legend[contains(text(), "Ver listado de ítem")]'))
                            )
                            sleep(1)
                        except TimeoutException:
                            sleep(2)
                        
                        # Extraer datos de la ficha
                        datos_ficha = self.extraer_datos_ficha()
                        
                        # Combinar datos básicos + datos de ficha
                        registro_completo = {**datos_basicos, **datos_ficha}
                        self.resultados.append(registro_completo)
                        registros_extraidos += 1
                        
                        # Volver a la lista
                        self.volver_a_lista()
                        
                        # Esperar a que se recargue
                        try:
                            WebDriverWait(self.driver, 5).until(
                                EC.presence_of_element_located((By.XPATH, '//*[@id="tbBuscador:idFormBuscarProceso:dtProcesos_data"]'))
                            )
                            sleep(1)
                        except TimeoutException:
                            sleep(2)
                        
                    except Exception as e:
                        logger.warning(f"         ⚠️  No se pudo entrar a la ficha: {e}")
                        # Si no se puede entrar a la ficha, guardar solo datos básicos
                        datos_completos = {
                            **datos_basicos,
                            'Fecha Inicio': '',
                            'Fecha Fin': '',
                            'Region': '',
                            'Codigo CUBSO': ''
                        }
                        self.resultados.append(datos_completos)
                        registros_extraidos += 1
                    
                    idx_fila += 1
                    
                except Exception as e:
                    logger.warning(f"      ⚠️  Error en fila {idx_fila + 1}: {e}")
                    idx_fila += 1
                    continue
            
            return registros_extraidos
            
        except Exception as e:
            logger.error(f"❌ Error extrayendo datos de página: {e}")
            return registros_extraidos
            
            return registros_extraidos
            
        except Exception as e:
            logger.error(f"❌ Error extrayendo datos de página: {e}")
            return registros_extraidos
    
    def extraer_datos_ficha(self) -> dict:
        """Extrae los datos adicionales de la ficha de selección - OPTIMIZADO"""
        datos = {
            'Fecha Inicio': '',
            'Fecha Fin': '',
            'Region': '',
            'Codigo CUBSO': ''
        }
        
        try:
            # 1. Extraer Fecha Inicio y Fecha Fin del cronograma
            logger.info("         📅 Extrayendo fechas...")
            try:
                primera_fila_cronograma = WebDriverWait(self.driver, 3).until(
                    EC.presence_of_element_located((By.XPATH, '//td[contains(text(), "Registro de participantes")]/parent::tr'))
                )
                
                celdas_cronograma = primera_fila_cronograma.find_elements(By.TAG_NAME, "td")
                
                if len(celdas_cronograma) >= 3:
                    datos['Fecha Inicio'] = celdas_cronograma[1].text.strip()
                    datos['Fecha Fin'] = celdas_cronograma[2].text.strip()
                    logger.info(f"            ✓ {datos['Fecha Inicio']} - {datos['Fecha Fin']}")
                    
            except (NoSuchElementException, TimeoutException):
                logger.warning("            ⚠️  Sin cronograma")
            
            # 2. Extraer Región de la Dirección Legal
            logger.info("         🗺️  Extrayendo región...")
            try:
                direccion_cell = self.driver.find_element(
                    By.XPATH,
                    '//span[contains(text(), "Direccion Legal:")]/parent::td/following-sibling::td'
                )
                
                direccion_text = direccion_cell.text.strip()
                match = re.search(r'\(([^-]+)-', direccion_text)
                if match:
                    datos['Region'] = match.group(1).strip().upper()
                    logger.info(f"            ✓ {datos['Region']}")
                    
            except NoSuchElementException:
                logger.warning("            ⚠️  Sin dirección")
            
            # 3. Hacer clic en "Ver listado de ítem" para extraer CUBSO
            logger.info("         📦 Extrayendo CUBSO...")
            try:
                legend_items = self.driver.find_element(
                    By.XPATH,
                    '//legend[contains(text(), "Ver listado de ítem")]'
                )
                
                self.driver.execute_script("arguments[0].scrollIntoView(true);", legend_items)
                sleep(0.2)  # Reducido de 0.5
                self.driver.execute_script("arguments[0].click();", legend_items)
                sleep(1)  # Reducido de 2 a 1
                
                # Extraer Código CUBSO
                try:
                    cubso_cell = self.driver.find_element(
                        By.XPATH,
                        '//span[contains(text(), "Codigo CUBSO:")]/parent::td/following-sibling::td'
                    )
                    datos['Codigo CUBSO'] = cubso_cell.text.strip()
                    logger.info(f"            ✓ {datos['Codigo CUBSO']}")
                    
                except NoSuchElementException:
                    logger.warning("            ⚠️  Sin CUBSO")
                
            except NoSuchElementException:
                logger.warning("            ⚠️  Sin listado de ítem")
            
        except Exception as e:
            logger.warning(f"         ⚠️  Error: {e}")
        
        return datos
    
    def volver_a_lista(self):
        """Vuelve a la lista de resultados desde la ficha"""
        try:
            # Buscar el botón de volver (puede variar, intenta varios selectores)
            xpaths_volver = [
                '//button[contains(., "Volver")]',
                '//button[contains(@id, "btnVolver")]',
                '//a[contains(., "Volver")]',
                '//button[contains(@class, "ui-button")][contains(., "Volver")]'
            ]
            
            for xpath in xpaths_volver:
                try:
                    boton_volver = self.driver.find_element(By.XPATH, xpath)
                    self.driver.execute_script("arguments[0].click();", boton_volver)
                    logger.info("         ← Volviendo a la lista")
                    return True
                except NoSuchElementException:
                    continue
            
            logger.warning("         ⚠️  No se encontró botón 'Volver'")
            return False
            
        except Exception as e:
            logger.warning(f"         ⚠️  Error volviendo a lista: {e}")
            return False
    
    def ir_siguiente_pagina(self, pagina_actual: int) -> bool:
        """Intenta ir a la siguiente página"""
        try:
            total_paginas = self.obtener_total_paginas()
            if total_paginas and pagina_actual >= total_paginas:
                logger.info(f"   ℹ️  Última página alcanzada ({pagina_actual}/{total_paginas})")
                return False
            
            siguiente_pagina = pagina_actual + 1
            xpath_siguiente = f'//span[@class="ui-paginator-page ui-state-default ui-corner-all" and text()="{siguiente_pagina}"]'
            
            try:
                boton_siguiente = self.driver.find_element(By.XPATH, xpath_siguiente)
                if boton_siguiente.is_displayed():
                    logger.info(f"   → Yendo a página {siguiente_pagina}...")
                    self.driver.execute_script("arguments[0].scrollIntoView(true);", boton_siguiente)
                    sleep(0.3)  # Reducido de 0.5
                    self.driver.execute_script("arguments[0].click();", boton_siguiente)
                    return True
            except NoSuchElementException:
                try:
                    xpath_siguiente_link = '//a[contains(@class, "ui-paginator-next")]'  # Corregido typo "xpathh"
                    boton_siguiente_link = self.driver.find_element(By.XPATH, xpath_siguiente_link)
                    class_attr = boton_siguiente_link.get_attribute('class')
                    
                    if 'ui-state-disabled' in class_attr:
                        logger.info(f"   ℹ️  Última página (botón deshabilitado)")
                        return False
                    
                    logger.info(f"   → Usando botón 'Siguiente'...")
                    self.driver.execute_script("arguments[0].click();", boton_siguiente_link)
                    return True
                except NoSuchElementException:
                    logger.info(f"   ℹ️  No hay botón siguiente")
                    return False
                
        except Exception as e:
            logger.warning(f"   ⚠️  No se pudo avanzar: {e}")
            return False
    
    def obtener_total_paginas(self) -> int:
        """Obtiene el número total de páginas"""
        try:
            botones_pagina = self.driver.find_elements(
                By.XPATH,
                '//span[@class="ui-paginator-page ui-state-default ui-corner-all"]'
            )
            
            if not botones_pagina:
                return 0
            
            numeros = []
            for boton in botones_pagina:
                try:
                    num = int(boton.text.strip())
                    numeros.append(num)
                except (ValueError, AttributeError):
                    continue
            
            if numeros:
                total = max(numeros)
                logger.info(f"   📊 Total de páginas: {total}")
                return total
            
            return 0
        except:
            return 0
    
    def guardar_excel(self, fecha_inicio: datetime, nombre_archivo: str = None):
        """Guarda los resultados en Excel"""
        if not self.resultados:
            logger.warning("⚠️  No hay datos para guardar")
            return False
        
        try:
            # Generar nombre con formato LICIT_PROD2_(AAMMDD).xlsx
            if nombre_archivo is None:
                fecha_formato = fecha_inicio.strftime('%y%m%d')  # AAMMDD
                nombre_archivo = f"LICIT_PROD2_{fecha_formato}.xlsx"
            
            df = pd.DataFrame(self.resultados)
            
            # Ordenar columnas
            columnas_orden = [
                'N°',
                'Fecha y Hora de Publicacion',
                'Nombre o Sigla de la Entidad',
                'Descripción de Objeto',
                'Nomenclatura',
                'Objeto de Contratación',
                'Region',
                'VR / VE / Cuantía de la contratación',
                'Moneda',
                'Codigo CUBSO',
                'Fecha Inicio',
                'Fecha Fin'
            ]
            
            # Reordenar si existen todas las columnas
            columnas_existentes = [col for col in columnas_orden if col in df.columns]
            df = df[columnas_existentes]
            
            df.to_excel(nombre_archivo, index=False, engine='openpyxl')
            logger.info(f"💾 Archivo guardado: {nombre_archivo}")
            return nombre_archivo  # Retornar el nombre del archivo
        except Exception as e:
            logger.error(f"❌ Error guardando archivo: {e}")
            return False


def pedir_fecha(texto: str) -> datetime:
    """Pide una fecha al usuario"""
    while True:
        try:
            entrada = input(texto).strip()
            for sep in ['/', '-', '.']:
                if sep in entrada:
                    partes = entrada.split(sep)
                    if len(partes) == 3:
                        dia, mes, anio = int(partes[0]), int(partes[1]), int(partes[2])
                        if 1 <= dia <= 31 and 1 <= mes <= 12 and 2000 <= anio <= 2030:
                            return datetime(anio, mes, dia)
            print("❌ Formato: DD/MM/YYYY (ej: 25/12/2025)")
        except ValueError as e:
            print(f"❌ Error: {e}")


def main():
    print("\n" + "=" * 70)
    print("🚀 SEACE SCRAPER COMPLETO - MODO INVISIBLE")
    print("=" * 70)
    print("ℹ️  El navegador se ejecutará en segundo plano (sin ventana)")
    print("=" * 70)
    
    # Modo headless por defecto
    modo_headless = True
    
    # Verificar si el usuario quiere ver el navegador
    if '--visible' in sys.argv:
        modo_headless = False
        sys.argv.remove('--visible')
        print("\n⚠️  Modo VISIBLE activado (verás el navegador)")
    
    # Verificar si hay argumentos de línea de comandos
    if len(sys.argv) >= 3:
        try:
            fecha_inicio = datetime.strptime(sys.argv[1], '%Y-%m-%d')
            fecha_fin = datetime.strptime(sys.argv[2], '%Y-%m-%d')
            print(f"\n📅 Fechas desde argumentos:")
        except ValueError:
            print("\n❌ Error: Formato incorrecto")
            print("   Uso: python seace_completo.py YYYY-MM-DD YYYY-MM-DD")
            return
    else:
        print("\n📅 Formato: DD/MM/YYYY (ejemplo: 25/01/2026)\n")
        fecha_inicio = pedir_fecha("📅 Fecha inicio: ")
        fecha_fin = pedir_fecha("📅 Fecha fin:    ")
    
    if fecha_fin < fecha_inicio:
        print("\n❌ La fecha fin debe ser posterior")
        return
    
    print("\n" + "-" * 70)
    print(f"✓ Inicio: {fecha_inicio.strftime('%d/%m/%Y')}")
    print(f"✓ Fin:    {fecha_fin.strftime('%d/%m/%Y')}")
    print(f"✓ Días:   {(fecha_fin - fecha_inicio).days + 1}")
    print("-" * 70)
    
    nombre_archivo = f"licitaciones_completo_{fecha_inicio.strftime('%Y%m%d')}_{fecha_fin.strftime('%Y%m%d')}.xlsx"
    print(f"📄 Archivo: {nombre_archivo}")
    
    if len(sys.argv) < 3:
        conf = input("\n¿Continuar? (s/n): ").strip().lower()
        if conf not in ['s', 'si', 'sí', 'yes', 'y']:
            print("\n❌ Cancelado")
            return
    
    print("\n" + "=" * 70)
    print("🚀 INICIANDO EXTRACCIÓN COMPLETA...")
    print("=" * 70 + "\n")
    
    scraper = SeaceScraperCompleto(headless=modo_headless)
    
    try:
        scraper.iniciar()
        exito = scraper.buscar_y_extraer(fecha_inicio, fecha_fin)
        
        if exito:
            scraper.guardar_excel(fecha_inicio)
        
        logger.info("⏳ Esperando antes de cerrar...")
        sleep(5)
        
        print("\n" + "=" * 70)
        if exito and scraper.resultados:
            print("✅ ¡EXTRACCIÓN COMPLETADA!")
            print("=" * 70)
            print(f"\n📊 Total de registros: {len(scraper.resultados)}")
            print(f"💾 Archivo: {nombre_archivo}")
        else:
            print("⚠️  SIN RESULTADOS")
            print("=" * 70)
        print("\n")
            
    except Exception as e:
        print(f"\n❌ ERROR: {e}\n")
        import traceback
        traceback.print_exc()
    finally:
        scraper.cerrar()
