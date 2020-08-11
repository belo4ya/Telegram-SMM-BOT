import logging
import configparser
import re
import datetime
import time
import os
from copy import copy
import asyncio

from aiogram import Bot, Dispatcher, executor, types
from aiogram.dispatcher import FSMContext
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.utils.exceptions import ButtonURLInvalid, Unauthorized, ChatNotFound
import requests
import pytz

from states import MenuStates
from markups import office, back, edit_post
from db import DataBase

# Timezone
os.environ['TZ'] = 'Europe/Moscow'
TIMEZONE = pytz.timezone('Europe/Moscow')

# API token
config = configparser.ConfigParser()
config.read('config.ini')
API_TOKEN = config['Telegram']['token']

# DataBase and Logging
logging.basicConfig(level=logging.INFO)
db = DataBase()

# Bot
bot = Bot(token=API_TOKEN, parse_mode='HTML')
dp = Dispatcher(bot, storage=MemoryStorage())

# Tools
TEST_CHANNEL = config['Test']['test_channel']
IMGBB_API_URL = config['Imgbb']['api_url']
IMGBB_API_KEY = config['Imgbb']['api_key']
task_list = {}
header_template = '<b>{}</b>\n' \
                  '<code>Адресаты:</code>   {}\n' \
                  '<code>Количество:</code>   {}\n' \
                  '<code>Интервал:</code>   {}\n' \
                  '<code>Время выполнения:</code>   {} ч {} мин'


async def shutdown(dispatcher: Dispatcher):
    await dispatcher.storage.close()
    await dispatcher.storage.wait_closed()


# =================================================================== #
#                                LOGIC                                #
# =================================================================== #
@dp.message_handler(commands=['start'], state='*')
async def cmd_start(message: types.Message, state: FSMContext):
    text = 'Главное меню'
    await state.update_data(message=[text])
    await MenuStates.OFFICE.set()
    await message.answer(text, reply_markup=office())


@dp.message_handler(commands=['help'], state='*')
async def cmd_help(message: types.Message):
    await message.answer('Вы ввели: /help')


@dp.message_handler(commands=['back'], state='*')
async def cmd_back(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state in [
        MenuStates.OFFICE.state,
        MenuStates.CREATE_NAME.state,
        MenuStates.MY_TASKS.state,
        MenuStates.ARCHIVE_TASKS.state,
        MenuStates.SETTINGS.state
    ]:
        await MenuStates.OFFICE.set()
        markup = office()
    elif current_state in [
        MenuStates.CREATE_CHANNEL.state,

    ]:
        await MenuStates.CREATE_NAME.set()
        markup = back()
    elif current_state in [
        MenuStates.CREATE_TIME_PARAMS.state,

    ]:
        await MenuStates.CREATE_CHANNEL.set()
        markup = back()
    elif current_state in [
        MenuStates.CREATE_CONTENT.state,

    ]:
        await MenuStates.CREATE_TIME_PARAMS.set()
        markup = back()

    async with state.proxy() as data:
        if len(data['message']) > 1:
            data['message'].pop()
            text = data['message'].pop()
        else:
            text = 'Главное меню'

    await message.answer(text, reply_markup=markup)


# ------------------------------- OFFICE ------------------------------- #
@dp.message_handler(lambda message: message.text == 'Create Task', state=MenuStates.OFFICE)
async def create_task(message: types.Message, state: FSMContext):
    text = 'Введите название Таска:'
    async with state.proxy() as data:
        data['post'] = {'text': '', 'img': '', 'urls': '', 'markup': ''}
        data['header'] = {'name': '', 'channels': '', 'count': '', 'interval': '', 'text': ''}
        data['message'].append(text)

    await MenuStates.CREATE_NAME.set()
    await message.answer(text, reply_markup=back())


@dp.message_handler(lambda message: message.text == 'My Tasks', state=MenuStates.OFFICE)
async def get_my_tasks(message: types.Message, state: FSMContext):
    text = 'Ваши Таски:'
    async with state.proxy() as data:
        data['message'].append(text)

    tasks = db.get_my_tasks(message.from_user.id)
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, selective=True)
    markup.add('/back')
    for task in tasks:
        if task.flag == 'sleep':
            markup.add('⏸' + task.name)
        elif task.flag == 'work':
            markup.add('▶' + task.name)
        elif task.flag == 'delay':
            markup.add('🕒' + task.name)

    await MenuStates.MY_TASKS.set()
    await message.answer(text, reply_markup=markup)


@dp.message_handler(lambda message: message.text == 'Archive Tasks', state=MenuStates.OFFICE)
async def get_archive_tasks(message: types.Message, state: FSMContext):
    text = 'Архив Тасков:'
    async with state.proxy() as data:
        data['message'].append(text)

    tasks = db.get_archived_tasks(message.from_user.id)
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, selective=True)
    markup.add('/back')
    for task in tasks:
        markup.add(task.name)

    await MenuStates.ARCHIVE_TASKS.set()
    await message.answer(text, reply_markup=markup)


@dp.message_handler(lambda message: message.text == 'Settings', state=MenuStates.OFFICE)
async def get_settings(message: types.Message):
    text = 'Раздел в разработке...'
    await message.answer(text)


# ================================ CREATE =================================== #
@dp.message_handler(content_types=types.ContentType.TEXT, state=MenuStates.CREATE_NAME)
async def create_name(message: types.Message, state: FSMContext):
    text = f'<b>{message.text[:16]}</b>\nВведите каналы через пробел:\n' \
           f'(@channel_1 @channel_2 @channel_3 ... @channel_51)\n'
    async with state.proxy() as data:
        data['message'].append(text)
        data['header']['name'] = message.text[:16]

    await MenuStates.CREATE_CHANNEL.set()
    await message.answer(text)


@dp.message_handler(regexp=r'@\w{5,}\b', state=MenuStates.CREATE_CHANNEL)
async def create_channel_with_message(message: types.Message, state: FSMContext):
    channel_names = list(sorted(set(re.findall(r'@\w{5,}\b', message.text))))
    await state.update_data(channel_names=list(channel_names))
    async with state.proxy() as data:
        header = header_template.format(data["header"]["name"], ', '.join(channel_names), '-', '-', '-', '-')
        text = 'Для установки настроек отправьте строку формата:\n' \
               '<code>M-N</code>, где <code>M</code> - временной ' \
               'интервал в минутах, <code>N</code> - кол-во постов\n\n' \
               'Например: <code>150-6</code> - каждые 2 ч 30 мин ' \
               'во все указанные каналы будет отпраляться один пост, всего таких' \
               'операций будет 6. Время исполнения: <code>150 * (6 - 1) = 12 ч 30 мин</code>'
        data['message'].append(text)
        data['header']['channels'] = channel_names

    await MenuStates.CREATE_TIME_PARAMS.set()
    await message.answer(header)
    await message.answer(text)


@dp.message_handler(state=MenuStates.CREATE_CHANNEL)
async def error_channel(message: types.Message):
    await message.answer('Некорректные идентификаторы каналов/чатов\nПопробуйте ещё раз')


@dp.message_handler(regexp=r'^\d{1,3}-\d{1,2}$', state=MenuStates.CREATE_TIME_PARAMS)
async def set_time_params(message: types.Message, state: FSMContext):
    interval, count = message.text.split('-')
    if 9 < int(interval) < 601 and 0 < int(count) < 31:
        text = 'Пришлите текст поста (без картинки)'
        async with state.proxy() as data:
            data['header']['count'] = int(count)
            data['header']['interval'] = int(interval)
            data['message'].append(text)
            header = header_template.format(data["header"]["name"],
                                            ', '.join(data["header"]["channels"]),
                                            data["header"]["count"],
                                            data["header"]["interval"],
                                            (data["header"]["count"] - 1) * data["header"]["interval"] // 60,
                                            (data["header"]["count"] - 1) * data["header"]["interval"] % 60)
            data['header']['text'] = header

        await MenuStates.CREATE_CONTENT.set()
        await message.answer(header)
        return await message.answer(text)

    return await error_set_time_params(message, state)


@dp.message_handler(state=MenuStates.CREATE_TIME_PARAMS)
async def error_set_time_params(message: types.Message):
    await message.answer('Некорректный формат данных\nПопробуйте ещё раз')


@dp.message_handler(content_types=types.ContentType.TEXT, state=MenuStates.CREATE_CONTENT)
async def create_content(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['post']['text'] = message.text
        markup = edit_post()
        data['post']['markup'] = markup

        await MenuStates.CONTENT_SETTINGS.set()
        await message.answer(data['header']['text'], reply_markup=types.ReplyKeyboardRemove())
        await message.answer(message.text, reply_markup=markup)


@dp.edited_message_handler(content_types=types.ContentType.TEXT, state=MenuStates.CONTENT_SETTINGS)
async def edited_post(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['post']['text'] = message.text
        markup = data['post']['markup']

    await bot.edit_message_text(text=message.text, chat_id=message.chat.id,
                                message_id=message.message_id + 2, reply_markup=markup)
# ================================ CREATE =================================== #


# ================================ IMG =================================== #
@dp.callback_query_handler(lambda callback: callback.data == 'add_img', state=MenuStates.CONTENT_SETTINGS)
async def add_image(callback: types.CallbackQuery):
    text = 'Пришлите картинку (до 5 Мб)'
    await MenuStates.EDIT_IMG.set()
    await callback.message.edit_text(text)


@dp.callback_query_handler(lambda callback: callback.data == 'del_img', state=MenuStates.CONTENT_SETTINGS)
async def del_image(callback: types.CallbackQuery, state: FSMContext):
    async with state.proxy() as data:
        data['post']['img'] = ''
        text = data['post']['text']
        markup = data['post']['markup']

        for i in markup.inline_keyboard:
            if i[0].callback_data == 'del_img':
                i[0].text = 'Прикрепить картинку'
                i[0].callback_data = 'add_img'
                break

        data['post']['markup'] = markup

    await callback.message.edit_text(text, reply_markup=markup)


@dp.message_handler(content_types=types.ContentType.PHOTO, state=MenuStates.EDIT_IMG)
async def set_image(message: types.Message, state: FSMContext):
    tg_url = await message.photo[-1].get_url()
    img_url = await get_img_url(tg_url)
    async with state.proxy() as data:
        data['post']['img'] = f'<a href="{img_url}">&#8205;</a>'  # f'[⁠]({img_url})'
        post = data['post']['img'] + data['post']['text']
        header = data['header']['text']
        markup = data['post']['markup']

        for i in markup.inline_keyboard:
            if i[0].callback_data == 'add_img':
                i[0].text = 'Открепить картинку'
                i[0].callback_data = 'del_img'
                break

        data['post']['markup'] = markup

    await MenuStates.CONTENT_SETTINGS.set()
    await message.answer(header)
    await message.answer(post, reply_markup=markup)
# ================================ IMG =================================== #


# ================================ LINK =================================== #
@dp.callback_query_handler(lambda callback: callback.data == 'add_url', state=MenuStates.CONTENT_SETTINGS)
async def add_url(callback: types.CallbackQuery, state: FSMContext):
    text = 'Пришлите URL-кнопки в формате:\n' \
           '`Ссылка 1 - https://www.google.ru/`\n' \
           '`Ссылка 2 - https://yandex.ru/`\n' \
           '`...`'
    await MenuStates.EDIT_URL.set()
    await callback.message.edit_text(text)


@dp.callback_query_handler(lambda callback: callback.data == 'del_url', state=MenuStates.CONTENT_SETTINGS)
async def del_url(callback: types.CallbackQuery, state: FSMContext):
    async with state.proxy() as data:
        data['post']['urls'] = ''
        text = data['post']['text'] + data['post']['img']
        markup = data['post']['markup']

        last_url = 0
        for i in range(len(markup.inline_keyboard)):
            if markup.inline_keyboard[i][0].callback_data == 'del_url':
                markup.inline_keyboard[i][0].text = 'Добавить URL-кнопки'
                markup.inline_keyboard[i][0].callback_data = 'add_url'
            if markup.inline_keyboard[i][0].url:
                last_url += 1

        if last_url:
            new_markup = types.InlineKeyboardMarkup()
            for i in range(last_url, len(markup.inline_keyboard)):
                new_markup.add(markup.inline_keyboard[i][0])
            data['post']['markup'] = new_markup
        else:
            new_markup = data['post']['markup']

    await callback.message.edit_text(text, reply_markup=new_markup)


@dp.message_handler(regexp=r'[^`*-]+ - https?://[^\s]+', state=MenuStates.EDIT_URL)
async def set_url(message: types.Message, state: FSMContext):
    url_markup = types.InlineKeyboardMarkup()
    urls = re.findall(r'[^`*-]+ - https?://[^\s]+', message.text)
    for i in urls:
        button = types.InlineKeyboardButton(text=i.split(' - ')[0], url=i.split(' - ')[1])
        url_markup.add(button)

    async with state.proxy() as data:
        data['post']['urls'] = url_markup
        post = data['post']['text'] + data['post']['img']
        header = data['header']['text']
        markup = await join_markups(url_markup, data['post']['markup'])

        for i in markup.inline_keyboard:
            if i[0].callback_data == 'add_url':
                i[0].text = 'Удалить URL-кнопки'
                i[0].callback_data = 'del_url'
                break

    await MenuStates.CONTENT_SETTINGS.set()
    await message.answer(header)

    try:
        await message.answer(post, reply_markup=markup)
        async with state.proxy() as data:
            data['post']['markup'] = markup

    except ButtonURLInvalid:
        data['post']['urls'] = ''
        markup = data['post']['markup']
        await message.answer(post, reply_markup=markup)


@dp.message_handler(state=MenuStates.EDIT_URL)
async def error_url(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        post = data['post']['text'] + data['post']['img']
        markup = data['post']['markup']
        header = data['header']['text']

    await MenuStates.CONTENT_SETTINGS.set()
    await message.answer(header)
    await message.answer(post, reply_markup=markup)
# ================================ LINK =================================== #


# ================================ SAVE =================================== #
@dp.callback_query_handler(lambda callback: callback.data == 'save', state=MenuStates.CONTENT_SETTINGS)
async def save_post(callback: types.CallbackQuery, state: FSMContext):
    text = 'Task сохранён. Вы можете найти его в разделе My Tasks'

    data = await state.get_data()
    await save_task_to_database(data, callback)

    await state.reset_data()
    await state.update_data(message=[text])
    await MenuStates.OFFICE.set()
    await bot.delete_message(chat_id=callback.message.chat.id, message_id=callback.message.message_id - 1)
    await bot.delete_message(chat_id=callback.message.chat.id, message_id=callback.message.message_id)
    await callback.message.answer(text, reply_markup=office())
# ================================ SAVE =================================== #


# ================================ RUN =================================== #
@dp.callback_query_handler(lambda callback: callback.data == 'run', state=MenuStates.CONTENT_SETTINGS)
async def run_post(callback: types.CallbackQuery, state: FSMContext):
    text = 'Task выполняется. Следить за его прогрессом можно в разделе My Tasks'

    data = await state.get_data()
    task_data = await save_task_to_database(data, callback, flag='work')

    t = bot.loop.create_task(launch_posting(task_data['name'], task_data))
    task_list[task_data['name']] = t

    await state.reset_data()
    await state.update_data(message=[text])
    await MenuStates.OFFICE.set()
    await bot.delete_message(chat_id=callback.message.chat.id, message_id=callback.message.message_id - 1)
    await bot.delete_message(chat_id=callback.message.chat.id, message_id=callback.message.message_id)
    await callback.message.answer(text, reply_markup=office())
# ================================ RUN =================================== #


# =================================================================== #
async def get_img_url(tg_url):
    url = requests.get('https://api.imgbb.com/1/upload',
                       params={
                           'key': '8f2a824bd7668ecdd86f6f0b7405acef',
                           'image': tg_url,
                           'expiration': '864000'
                       }).json()
    return url['data']['url']


async def join_markups(markup_1, markup_2):
    new_markup = types.InlineKeyboardMarkup()
    for i in markup_1.inline_keyboard:
        new_markup.add(i[0])
    for i in markup_2.inline_keyboard:
        new_markup.add(i[0])
    return new_markup


async def save_task_to_database(data, callback, flag='sleep'):
    data['post'].pop('markup')
    data['header'].pop('text')
    task_data = dict(list(data['header'].items()) + list(data['post'].items()))
    task_data['user_id'] = callback.from_user.id
    task_data['flag'] = flag
    db.add_task(**task_data)
    return task_data


async def launch_posting(name, data=None):
    if data is None:
        data = db.get_task_data(name)
    count = data['count']
    interval = data['interval']
    channels = data['channels']
    text = data['text'] + data['img']
    markup = data['urls'] or None
    while count:
        for channel in channels:
            try:
                await bot.send_message(channel, text, reply_markup=markup)
            except (Unauthorized, ChatNotFound):
                pass
        if count != 1:
            await asyncio.sleep(interval - 3)
        db.decrement_counter(data['user_id'], data['name'])
        count -= 1

    task_list.pop(name)
    db.edit_task(data['user_id'], data['name'], flag='archived')


async def delay_posting(name, data=None):
    pass


if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True, on_shutdown=shutdown)
