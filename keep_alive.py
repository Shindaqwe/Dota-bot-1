from flask import Flask, jsonify
from threading import Thread
import os
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

@app.route('/')
def home():
    """Основная страница для Railway health check"""
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Dota2 Bot Status</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 20px;
            }
            .container {
                background: rgba(255, 255, 255, 0.1);
                backdrop-filter: blur(10px);
                border-radius: 20px;
                padding: 40px;
                text-align: center;
                max-width: 600px;
                width: 100%;
                box-shadow: 0 20px 40px rgba(0,0,0,0.2);
                border: 1px solid rgba(255,255,255,0.2);
            }
            h1 {
                color: white;
                font-size: 2.5em;
                margin-bottom: 20px;
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 15px;
            }
            .status {
                background: rgba(76, 175, 80, 0.2);
                border: 2px solid #4CAF50;
                color: #4CAF50;
                padding: 15px 30px;
                border-radius: 50px;
                font-size: 1.5em;
                font-weight: bold;
                margin: 20px 0;
                display: inline-block;
            }
            .info {
                background: rgba(255, 255, 255, 0.1);
                border-radius: 15px;
                padding: 20px;
                margin: 20px 0;
                text-align: left;
            }
            .info p {
                color: rgba(255, 255, 255, 0.9);
                margin: 10px 0;
                font-size: 1.1em;
            }
            .endpoints {
                margin-top: 30px;
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 15px;
            }
            .endpoint {
                background: rgba(255, 255, 255, 0.15);
                padding: 15px;
                border-radius: 10px;
                transition: transform 0.3s;
            }
            .endpoint:hover {
                transform: translateY(-5px);
                background: rgba(255, 255, 255, 0.2);
            }
            .endpoint a {
                color: #fff;
                text-decoration: none;
                display: block;
            }
            .endpoint .method {
                font-weight: bold;
                color: #4CAF50;
            }
            .footer {
                margin-top: 30px;
                color: rgba(255, 255, 255, 0.7);
                font-size: 0.9em;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🤖 Dota2 Stats Bot</h1>
            
            <div class="status">✅ Бот активен и работает</div>
            
            <div class="info">
                <p><strong>📍 Статус:</strong> <span style="color: #4CAF50;">Online</span></p>
                <p><strong>🚀 Сервис:</strong> Telegram бот для статистики Dota 2</p>
                <p><strong>⚡ Платформа:</strong> Railway.app</p>
                <p><strong>📊 Функции:</strong> Профиль, анализ, викторина, друзья</p>
            </div>
            
            <div class="endpoints">
                <div class="endpoint">
                    <a href="/health">
                        <div class="method">GET /health</div>
                        <div>Проверка здоровья сервиса</div>
                    </a>
                </div>
                <div class="endpoint">
                    <a href="/status">
                        <div class="method">GET /status</div>
                        <div>Статус сервера</div>
                    </a>
                </div>
            </div>
            
            <div class="footer">
                Этот сервер поддерживает работу Telegram бота 24/7<br>
                Powered by Flask & Railway
            </div>
        </div>
    </body>
    </html>
    '''

@app.route('/health')
def health():
    """Health check endpoint для Railway"""
    return jsonify({
        "status": "healthy",
        "service": "dota2-telegram-bot",
        "timestamp": "online"
    }), 200

@app.route('/status')
def status():
    """Статус сервера"""
    import datetime
    import psutil
    import socket
    
    # Получаем информацию о системе
    memory = psutil.virtual_memory()
    cpu_percent = psutil.cpu_percent(interval=1)
    
    return jsonify({
        "status": "running",
        "service": "Dota2 Telegram Bot",
        "timestamp": datetime.datetime.now().isoformat(),
        "hostname": socket.gethostname(),
        "system": {
            "cpu_percent": cpu_percent,
            "memory_percent": memory.percent,
            "memory_available_gb": round(memory.available / (1024**3), 2)
        },
        "environment": {
            "python_version": "3.11.x",
            "platform": "Railway"
        }
    }), 200

@app.route('/ping')
def ping():