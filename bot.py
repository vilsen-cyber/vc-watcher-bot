import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.types import Message, InputMediaPhoto, InputMediaVideo, InputMediaDocument
from aiogram.client.default import DefaultBotProperties
from config import API_TOKEN, WATCHLIST

# 📋 Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TelegramMonitorBot:
    def __init__(self):
        """Инициализация бота для мониторинга упоминаний агентств"""
        self.bot = Bot(
            token=API_TOKEN,
            default=DefaultBotProperties(parse_mode=None)
        )
        self.dp = Dispatcher()
        self.media_groups = {}  # Для хранения медиа-групп
        self.setup_handlers()

    def setup_handlers(self):
        """Настройка обработчиков сообщений"""
        @self.dp.message()
        async def handle_messages(message: Message):
            await self.process_message(message)

    async def process_message(self, message: Message):
        """
        Обработка входящих сообщений для поиска упоминаний агентств
        
        Args:
            message: Входящее сообщение из Telegram
        """
        try:
            # Если это медиа-группа, собираем все медиа перед обработкой
            if message.media_group_id:
                await self.handle_media_group(message)
                return
                
            # Получаем текст из сообщения или подписи к медиа
            full_text = (message.caption or message.text or "").strip()
            
            if not full_text:
                return
                
            lower_text = full_text.lower()
            logger.info(f"▶️ Получено сообщение: {full_text[:100]}...")

            # Поиск упоминаний агентств в тексте
            found_agencies = []
            for keyword, user_id in WATCHLIST.items():
                if keyword in lower_text:
                    # Специальное исключение: если нашли "sofi", но в тексте есть "sofi art", то не срабатываем
                    if keyword == "sofi" and "sofi art" in lower_text:
                        continue
                    found_agencies.append((keyword, user_id))

            # Отправка уведомлений для найденных агентств
            for keyword, user_id in found_agencies:
                await self.send_notification(message, keyword, user_id, full_text)

        except Exception as e:
            logger.error(f"❌ Ошибка при обработке сообщения: {e}")

    async def handle_media_group(self, message: Message):
        """
        Обработка группы медиа (несколько фото/видео в одном сообщении)
        """
        media_group_id = message.media_group_id
        
        # Инициализируем группу, если её ещё нет
        if media_group_id not in self.media_groups:
            self.media_groups[media_group_id] = {
                'messages': [],
                'caption': '',
                'processed': False
            }
        
        # Добавляем сообщение в группу
        self.media_groups[media_group_id]['messages'].append(message)
        
        # Сохраняем подпись (обычно только у первого сообщения)
        if message.caption and not self.media_groups[media_group_id]['caption']:
            self.media_groups[media_group_id]['caption'] = message.caption
        
        # Обрабатываем группу через небольшую задержку, чтобы собрать все сообщения
        import asyncio
        await asyncio.sleep(0.5)
        
        # Проверяем, не обработали ли уже эту группу
        if self.media_groups[media_group_id]['processed']:
            return
            
        # Помечаем как обработанную
        self.media_groups[media_group_id]['processed'] = True
        
        # Обрабатываем группу
        if media_group_id:
            await self.process_media_group(media_group_id)

    async def process_media_group(self, media_group_id: str):
        """
        Обработка собранной группы медиа
        """
        group_data = self.media_groups[media_group_id]
        messages = group_data['messages']
        full_text = group_data['caption'] or ''
        
        if not full_text.strip():
            # Удаляем обработанную группу
            del self.media_groups[media_group_id]
            return
            
        lower_text = full_text.lower()
        logger.info(f"▶️ Получена группа медиа с текстом: {full_text[:100]}...")

        # Поиск упоминаний агентств в тексте
        found_agencies = []
        for keyword, user_id in WATCHLIST.items():
            if keyword in lower_text:
                # Специальное исключение: если нашли "sofi", но в тексте есть "sofi art", то не срабатываем
                if keyword == "sofi" and "sofi art" in lower_text:
                    continue
                found_agencies.append((keyword, user_id))

        # Отправка уведомлений для найденных агентств
        for keyword, user_id in found_agencies:
            await self.send_media_group_notification(messages, keyword, user_id, full_text)
        
        # Удаляем обработанную группу
        del self.media_groups[media_group_id]

    async def send_notification(self, message: Message, keyword: str, user_id: int, full_text: str):
        """
        Отправка уведомления пользователю о найденном упоминании
        
        Args:
            message: Исходное сообщение
            keyword: Найденное ключевое слово агентства
            user_id: ID пользователя для отправки уведомления
            full_text: Полный текст сообщения
        """
        try:
            agency_display = keyword.title()
            
            # Формирование содержимого уведомления
            content = (
                f"🚨 Нарушение\n"
                f'"{full_text.strip()}"'
            )

            logger.info(f"📤 Отправляем уведомление {agency_display} → {user_id}")

            # Отправка в зависимости от типа контента
            if message.photo:
                # Отправляем фото с подписью
                await self.bot.send_photo(
                    chat_id=user_id,
                    photo=message.photo[-1].file_id,
                    caption=content
                )
            elif message.video:
                # Отправляем видео с подписью
                await self.bot.send_video(
                    chat_id=user_id,
                    video=message.video.file_id,
                    caption=content
                )
            elif message.document:
                # Отправляем документ с подписью
                await self.bot.send_document(
                    chat_id=user_id,
                    document=message.document.file_id,
                    caption=content
                )
            else:
                # Отправляем только текстовое сообщение
                await self.bot.send_message(
                    chat_id=user_id,
                    text=content
                )
                
            logger.info(f"✅ Уведомление успешно отправлено для {agency_display}")

        except Exception as e:
            logger.warning(f"❌ Ошибка при отправке уведомления для {keyword}: {e}")

    async def send_media_group_notification(self, messages: list, keyword: str, user_id: int, full_text: str):
        """
        Отправка уведомления с группой медиа
        """
        try:
            agency_display = keyword.title()
            
            # Формирование содержимого уведомления
            content = (
                f"🚨 Нарушение\n"
                f'"{full_text.strip()}"'
            )

            logger.info(f"📤 Отправляем уведомление (группа {len(messages)} медиа) {agency_display} → {user_id}")

            # Формируем группу медиа для отправки
            media_list = []
            for i, msg in enumerate(messages):
                if msg.photo:
                    media = InputMediaPhoto(
                        media=msg.photo[-1].file_id,
                        caption=content if i == 0 else None  # Подпись только к первому элементу
                    )
                    media_list.append(media)
                elif msg.video:
                    media = InputMediaVideo(
                        media=msg.video.file_id,
                        caption=content if i == 0 else None
                    )
                    media_list.append(media)
                elif msg.document:
                    media = InputMediaDocument(
                        media=msg.document.file_id,
                        caption=content if i == 0 else None
                    )
                    media_list.append(media)
            
            if media_list:
                # Отправляем группу медиа
                await self.bot.send_media_group(
                    chat_id=user_id,
                    media=media_list
                )
            else:
                # Если нет медиа, отправляем только текст
                await self.bot.send_message(
                    chat_id=user_id,
                    text=content
                )
                
            logger.info(f"✅ Уведомление с группой медиа успешно отправлено для {agency_display}")

        except Exception as e:
            logger.warning(f"❌ Ошибка при отправке группового уведомления для {keyword}: {e}")

    async def start_polling(self):
        """Запуск бота в режиме polling"""
        logger.info("🚀 Запуск Telegram бота...")
        try:
            await self.dp.start_polling(self.bot)
        except Exception as e:
            logger.error(f"❌ Ошибка при запуске бота: {e}")
            raise

    async def stop(self):
        """Остановка бота"""
        logger.info("🛑 Остановка Telegram бота...")
        await self.bot.session.close()