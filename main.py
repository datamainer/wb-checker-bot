import asyncio
import json
import os
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

API_TOKEN = '6598642246:AAEfliH50ZFn7Yto4X_bvlInrsQs1N6Jyro'
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

DATA_DIR = 'data'


async def parse_link(url):
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


async def write_data(user_id, data):
    filename = os.path.join(DATA_DIR, f'{user_id}.json')
    with open(filename, 'w', encoding='utf-8') as file:
        json.dump(data, file, ensure_ascii=False)


async def read_data(user_id):
    filename = os.path.join(DATA_DIR, f'{user_id}.json')
    if os.path.exists(filename):
        with open(filename, 'r', encoding='utf-8') as file:
            return json.load(file)
    else:
        return {}


@dp.message_handler(commands=['start'])
async def start_command(message: types.Message):
    user_id = message.from_user.id
    await write_data(user_id, {})  # Создаем или перезаписываем файл данных для пользователя
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(KeyboardButton("Мои ссылки"))
    await message.reply("Привет! Отправь мне ссылку на товар на сайте Wildberries.", reply_markup=keyboard)


@dp.message_handler(regexp=r'^https://www.wildberries.ru/.+$')
async def handle_link(message: types.Message):
    url = message.text
    user_id = message.from_user.id
    await message.reply("Принял, обрабатываю...")
    data = await read_data(user_id)
    title, price = await parse_link(url)
    if 'items' not in data:
        data['items'] = {}
    data['items'][title] = [url, price]
    await write_data(user_id, data)
    await message.reply(f"Цена товара **'{title}'** записана: **{price}**")


@dp.message_handler(lambda message: message.text == "Мои ссылки")
async def show_links(message: types.Message):
    user_id = message.from_user.id
    data = await read_data(user_id)
    if 'items' in data:
        links = data['items']
        if links:
            response = "Список добавленных ссылок:\n\n"
            for idx, (name, info) in enumerate(links.items(), start=1):
                response += f"{idx}. {name} - {info[0]}, Цена: {info[1]}\n\n"
            keyboard_markup = InlineKeyboardMarkup(row_width=1)
            for idx, (name, _) in enumerate(links.items(), start=1):
                button = InlineKeyboardButton(f"Удалить {idx}", callback_data=f"delete_{idx}")
                keyboard_markup.add(button)
            await message.reply(response, reply_markup=keyboard_markup)
        else:
            await message.reply("Вы еще не добавили ни одной ссылки.")
    else:
        await message.reply("Вы еще не добавили ни одной ссылки.")


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
                                        text=f"Ссылка '{item_to_delete}' успешно удалена.")
        else:
            await bot.answer_callback_query(callback_query.id, text="Этот товар не найден в вашем списке.")
    else:
        await bot.answer_callback_query(callback_query.id, text="У вас еще нет добавленных ссылок.")

if __name__ == '__main__':
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
    asyncio.run(dp.start_polling())
