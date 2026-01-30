from flask import Flask, request, jsonify, send_file
from datetime import datetime
import os
import logging
from seace_scraper import SeaceScraperCompleto

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.route('/')
def home():
    return jsonify({
        "status": "online",
        "service": "SEACE Scraper API",
        "endpoints": {
            "/health": "GET - Health check",
            "/scrape": "POST - Ejecutar scraping (params: fecha_inicio, fecha_fin)"
        }
    })

@app.route('/health')
def health():
    return jsonify({"status": "healthy"})

@app.route('/scrape', methods=['POST'])
def scrape():
    try:
        logger.info("📥 Recibida solicitud de scraping")
        data = request.json
        
        if not data:
            return jsonify({"error": "No se envió JSON en el body"}), 400
        
        if 'fecha_inicio' not in data or 'fecha_fin' not in data:
            return jsonify({"error": "Faltan parámetros: fecha_inicio y fecha_fin"}), 400
        
        fecha_inicio = datetime.strptime(data['fecha_inicio'], '%Y-%m-%d')
        fecha_fin = datetime.strptime(data['fecha_fin'], '%Y-%m-%d')
        
        logger.info(f"📅 Fechas: {fecha_inicio} → {fecha_fin}")
        
        scraper = SeaceScraperCompleto(headless=True)
        scraper.iniciar()
        exito = scraper.buscar_y_extraer(fecha_inicio, fecha_fin)
        
        if exito:
            nombre = f"licitaciones_{fecha_inicio.strftime('%Y%m%d')}_{fecha_fin.strftime('%Y%m%d')}.xlsx"
            scraper.guardar_excel(nombre)
            scraper.cerrar()
            
            logger.info(f"✅ Scraping exitoso: {len(scraper.resultados)} registros")
            return send_file(nombre, as_attachment=True, download_name=nombre)
        else:
            scraper.cerrar()
            logger.warning("⚠️ No se encontraron resultados")
            return jsonify({"error": "No se encontraron resultados"}), 404
            
    except Exception as e:
        logger.error(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    logger.info(f"🚀 Iniciando servidor en puerto {port}")
    app.run(host='0.0.0.0', port=port)
