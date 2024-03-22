import asyncio
import json
import os
import logging  
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_TOKEN = '6598642246:AAEfliH50ZFn7Yto4X_bvlInrsQs1N6Jyro'
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

DATA_DIR = 'data'

async def parse_link(url):
    try:
        user_agent = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                       '(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')
        options = Options()
        options.add_argument(f'user-agent={user_agent}')
        options.add_argument('--headless')
        driver = webdriver.Chrome(options=options)
        driver.get(url)
        await asyncio.sleep(5)
        driver.save_screenshot('screen.png')
        title = driver.find_element(By.CLASS_NAME, 'product-page__title').text
        price = driver.find_element(By.CLASS_NAME, 'price-block__final-price').text
        driver.quit()
        return title, price
    except Exception as e:
        logger.error(f"Ошибка при парсинге ссылки: {url}")
        logger.exception(e)
        return None, None

async def write_data(user_id, data):
    filename = os.path.join(DATA_DIR, f'{user_id}.json')
    try:
        with open(filename, 'w', encoding='utf-8') as file:
            json.dump(data, file, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Ошибка при записи данных: {data}")
        logger.exception(e)

async def read_data(user_id):
    filename = os.path.join(DATA_DIR, f'{user_id}.json')
    if os.path.exists(filename):
        try:
            with open(filename, 'r', encoding='utf-8') as file:
                return json.load(file)
        except Exception as e:
            logger.error(f"Ошибка при чтении данных: {filename}")
            logger.exception(e)
    return {}

@dp.message_handler(commands=['start'])
async def start_command(message: types.Message):
    user_id = message.from_user.id
    data = await read_data(user_id)
    if 'items' not in data:
        await write_data(user_id, {}) 
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(KeyboardButton("Мои ссылки"))
    await message.reply("Привет\nОтправь мне ссылку на товар на сайте Wildberries. \n"
                       "Я сообщу, когда на нее будет скидка ", reply_markup=keyboard)

@dp.message_handler(regexp=r'^https://www.wildberries.ru/.+$')
async def handle_link(message: types.Message):
    url = message.text
    user_id = message.from_user.id
    logger.info(f"Новая ссылка от пользователя {user_id}: {url}")
    await message.reply("Принял, обрабатываю... ")
    data = await read_data(user_id)
    title, price = await parse_link(url)
    if 'items' not in data:
        data['items'] = {}
    data['items'][title] = [url, price]
    await write_data(user_id, data)
    await message.reply(f"Цена товара '{title}'\n"
                       f"Записана: {price}")
    await message.reply(f'Буду за ней следить, если хочешь добавить что то еще \n'
                       f'просто пришли мне ссылку на wb ')

@dp.message_handler(lambda message: message.text == "Мои ссылки")
async def show_links(message: types.Message):
    user_id = message.from_user.id
    data = await read_data(user_id)
    if 'items' in data:
        links = data['items']
        if links:
            response = "Список добавленных товаров:\n\n"
            for idx, (name, info) in enumerate(links.items(), start=1):
                response += f"{idx}. {name} - {info[0]}, Цена: {info[1]}\n\n"
            keyboard_markup = InlineKeyboardMarkup(row_width=1)
            for idx, (name, _) in enumerate(links.items(), start=1):
                button = InlineKeyboardButton(f"Удалить {idx}", callback_data=f"delete_{idx}")
                keyboard_markup.add(button)
            await message.reply(response, reply_markup=keyboard_markup)
        else:
            await message.reply("Вы еще не добавили ни одного товара.")
    else:
        await message.reply("Вы еще не добавили ни одного товара.")

@dp.callback_query_handler(lambda c: c.data.startswith('delete_'))
async def process_callback_button(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    data = await read_data(user_id)
    idx = int(callback_query.data.split('_')[1])
    if 'items' in data:
        links = data['items']
        if len(links) >= idx:
            item_to_delete = list(links.keys())[idx - 1]
            del links[item_to_delete]
            await write_data(user_id, data)
            await bot.edit_message_text(chat_id=callback_query.message.chat.id,
                                         message_id=callback_query.message.message_id,
                                         text=f"Товар '{item_to_delete}' успешно удален.")
        else:
            await bot.answer_callback_query(callback_query.id, text="Этот товар не найден в вашем списке.")
    else:
        await bot.answer_callback_query(callback_query.id, text="У вас еще нет добавленных товаров.")

async def check_price_changes():
    while True:
        # Получаем список пользователей
        users = [f for f in os.listdir(DATA_DIR) if os.path.isfile(os.path.join(DATA_DIR, f))]
        print('OK')
        for user_id_file in users:
            user_id = user_id_file.split('.')[0]
            data = await read_data(user_id)
            if 'items' in data and data['items']:
                for title, info in data['items'].items():
                    print('OK')
                    old_price = info[1]  # Сохраняем старую цену
                    new_title, new_price = await parse_link(info[0])
                    if new_price != old_price:  # Сравниваем цены
                        if float(new_price) > float(old_price):
                            message = f"Цена товара '{title}' выросла!\nСтарая цена: {old_price}\nНовая цена: {new_price}"
                        else:
                            message = f"Цена товара '{title}' упала!\nСтарая цена: {old_price}\nНовая цена: {new_price}"
                        await bot.send_message(user_id, message)
                    data['items'][title] = [info[0], new_price]
                    await write_data(user_id, data)
        await asyncio.sleep(12 * 60 * 60)
        print('OK')

if __name__ == '__main__':
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
    loop = asyncio.get_event_loop()
    loop.create_task(check_price_changes())
    asyncio.run(dp.start_polling())

