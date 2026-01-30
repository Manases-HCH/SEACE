from flask import Flask, request, jsonify, send_file
from datetime import datetime
import os
import logging
from seace_scraper import SeaceScraperCompleto

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

@app.route('/')
def home():
    return jsonify({
        "status": "online",
        "endpoints": {
            "/scrape": "POST - Ejecutar scraping",
            "/health": "GET - Health check"
        }
    })

@app.route('/health')
def health():
    return jsonify({"status": "healthy"})

@app.route('/scrape', methods=['POST'])
def scrape():
    try:
        data = request.json
        fecha_inicio = datetime.strptime(data['fecha_inicio'], '%Y-%m-%d')
        fecha_fin = datetime.strptime(data['fecha_fin'], '%Y-%m-%d')
        
        # Ejecutar scraping
        scraper = SeaceScraperCompleto(headless=True)
        scraper.iniciar()
        exito = scraper.buscar_y_extraer(fecha_inicio, fecha_fin)
        
        if exito:
            nombre_archivo = f"licitaciones_{fecha_inicio.strftime('%Y%m%d')}_{fecha_fin.strftime('%Y%m%d')}.xlsx"
            scraper.guardar_excel(nombre_archivo)
            scraper.cerrar()
            
            return send_file(
                nombre_archivo,
                as_attachment=True,
                download_name=nombre_archivo
            )
        else:
            scraper.cerrar()
            return jsonify({"error": "No se encontraron resultados"}), 404
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)