import asyncio
import logging
import time
from threading import Thread
from flask import Flask, jsonify
from bot import TelegramMonitorBot
from config import WEB_HOST, WEB_PORT, LOG_LEVEL, WATCHLIST

# 📋 Настройка логирования
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class WebServer:
    """Flask веб-сервер для health checks и мониторинга"""
    
    def __init__(self):
        self.app = Flask(__name__)
        self.setup_routes()
    
    def setup_routes(self):
        """Настройка маршрутов веб-сервера"""
        
        @self.app.route('/')
        def health_check():
            """Проверка состояния сервиса"""
            return jsonify({
                "status": "alive",
                "service": "Telegram Agency Monitor Bot",
                "message": "Bot is running and monitoring messages"
            })
        
        @self.app.route('/health')
        def detailed_health():
            """Детальная проверка состояния"""
            return jsonify({
                "status": "healthy",
                "service": "Telegram Agency Monitor Bot",
                "uptime": "running",
                "monitoring": "active"
            })
    
    def run(self):
        """Запуск веб-сервера"""
        logger.info(f"🌐 Запуск веб-сервера на {WEB_HOST}:{WEB_PORT}")
        
        # Отключаем логи werkzeug для чистого вывода
        logging.getLogger('werkzeug').setLevel(logging.ERROR)
        
        self.app.run(
            host=WEB_HOST,
            port=WEB_PORT,
            debug=False,
            use_reloader=False
        )

class BotManager:
    """Менеджер для управления ботом и веб-сервером"""
    
    def __init__(self):
        self.bot = TelegramMonitorBot()
        self.web_server = WebServer()
        self.web_thread = None
    
    def start_web_server(self):
        """Запуск веб-сервера в отдельном потоке"""
        self.web_thread = Thread(target=self.web_server.run, daemon=True)
        self.web_thread.start()
        logger.info("✅ Веб-сервер запущен в отдельном потоке")
    
    async def start_bot_with_recovery(self):
        """Запуск бота с автоматическим восстановлением"""
        max_retries = 3
        retry_delay = 10
        
        for attempt in range(max_retries):
            try:
                logger.info(f"🚀 Попытка запуска бота #{attempt + 1}")
                await self.bot.start_polling()
                break
            except Exception as e:
                logger.error(f"❌ Ошибка запуска попытка {attempt + 1}: {e}")
                if attempt < max_retries - 1:
                    logger.info(f"⏱️ Ожидание {retry_delay} секунд перед повторной попыткой...")
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2  # Экспоненциальная задержка
                else:
                    logger.error("💥 Все попытки запуска исчерпаны")
                    raise
    
    async def run(self):
        """Главная функция запуска всех сервисов с автоматическим перезапуском"""
        # Запускаем веб-сервер один раз
        self.start_web_server()
        
        while True:
            try:
                logger.info("🤖 Инициализация Telegram бота...")
                # Создаем новый экземпляр бота для каждой попытки
                self.bot = TelegramMonitorBot()
                await self.bot.start_polling()
                
            except KeyboardInterrupt:
                logger.info("🛑 Получен сигнал завершения")
                break
            except Exception as e:
                logger.error(f"❌ Ошибка в работе бота: {e}")
                logger.info("🔄 Перезапуск через 5 секунд...")
                try:
                    await self.bot.stop()
                except:
                    pass
                await asyncio.sleep(5)
                continue
        
        # Финальная очистка
        try:
            await self.bot.stop()
        except:
            pass
        logger.info("🏁 Все сервисы остановлены")

async def main():
    """Точка входа в приложение с бесконечным перезапуском"""
    logger.info("🚀 Запуск Telegram Agency Monitor Bot...")
    logger.info("♻️ Режим автоматического перезапуска активен")
    
    # Информация о конфигурации
    logger.info("📋 Конфигурация:")
    logger.info(f"  - Веб-сервер: {WEB_HOST}:{WEB_PORT}")
    logger.info(f"  - Уровень логирования: {LOG_LEVEL}")
    logger.info(f"  - Количество отслеживаемых агентств: {len(WATCHLIST)}")
    
    # Создаем и запускаем менеджер
    manager = BotManager()
    await manager.run()

def run_with_restart():
    """Запуск с автоматическим перезапуском на верхнем уровне"""
    restart_count = 0
    while True:
        try:
            restart_count += 1
            if restart_count > 1:
                logger.info(f"🔄 Перезапуск #{restart_count}")
            
            asyncio.run(main())
            break  # Нормальное завершение
            
        except KeyboardInterrupt:
            logger.info("👋 Программа завершена пользователем")
            break
        except Exception as e:
            logger.error(f"💥 Критическая ошибка: {e}")
            logger.info("⏱️ Перезапуск через 10 секунд...")
            time.sleep(10)
            continue

if __name__ == "__main__":
    run_with_restart()