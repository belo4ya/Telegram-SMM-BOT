import logging
import configparser
import re
import datetime
import asyncio

from aiogram import Bot, Dispatcher, executor, types
from aiogram.dispatcher import FSMContext
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.utils.exceptions import ButtonURLInvalid, Unauthorized, ChatNotFound, MessageNotModified

import requests
from states import States
from markups import main_keyboard, back_keyboard, edit_post_keyboard, edit_header_keyboard, action_post_keyboard
from db import DataBase

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
IMGBB_API_URL = config['Imgbb']['api_url']
IMGBB_API_KEY = config['Imgbb']['api_key']
task_list = {}
header_template = '<b>{}</b>\n' \
                  '<code>Адресаты:</code>   {}\n' \
                  '<code>Количество:</code>   {}\n' \
                  '<code>Интервал:</code>   {}\n' \
                  '<code>Время выполнения:</code>   {} ч {} мин\n' \
                  '<code>Начало выполнения:</code>   {}'


async def shutdown(dispatcher: Dispatcher):
    await dispatcher.storage.close()
    await dispatcher.storage.wait_closed()


# =================================================================== #
#                                LOGIC                                #
# =================================================================== #
@dp.message_handler(commands=['start'], state='*')
async def cmd_start(message: types.Message, state: FSMContext):
    text = 'Главное меню'
    async with state.proxy() as data:
        data['message'] = [text]
        data['offset'] = 0
        data['post'] = {'user_id': '', 'channels': [],
                        'count': None, 'interval': None,
                        'time_start': None, 'flag': '',
                        'name': '', 'text': '',
                        'img': '', 'urls': None}

    await States.OFFICE.set()
    await message.answer(text, reply_markup=main_keyboard())


@dp.message_handler(commands=['help'], state='*')
async def cmd_help(message: types.Message):
    await message.answer('Вы ввели: /help')


@dp.message_handler(lambda message: message.text == '🔙Назад', state='*')
async def cmd_back(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state in [
        States.OFFICE.state,
        States.CREATE_TASK.state,
        States.MY_TASKS.state,
        States.ARCHIVE_TASKS.state,
        States.SETTINGS.state
    ]:
        await States.OFFICE.set()
        keyboard = main_keyboard()

    async with state.proxy() as data:
        if len(data['message']) > 1:
            data['message'].pop()
            text = data['message'].pop()
        else:
            text = 'Главное меню'

    await message.answer(text, reply_markup=keyboard)


# ------------------------------- OFFICE ------------------------------- #
@dp.message_handler(lambda message: message.text == 'Создать пост', state=States.OFFICE)
async def create_task(message: types.Message, state: FSMContext):
    text = 'Введите название Таска:'
    async with state.proxy() as data:
        data['message'].append(text)
        data['offset'] = 0
        data['post'] = {'user_id': '', 'channels': [],
                        'count': None, 'interval': None,
                        'time_start': None, 'flag': '',
                        'name': '', 'text': '',
                        'img': '', 'urls': None}

    await States.CREATE_TASK.set()
    await message.answer(text, reply_markup=back_keyboard())


@dp.message_handler(lambda message: message.text == 'Мои посты', state=States.OFFICE)
async def get_my_tasks(message: types.Message, state: FSMContext):
    text = 'Ваши Таски:'
    async with state.proxy() as data:
        data['message'].append(text)

    tasks = db.get_my_tasks(message.from_user.id)
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, selective=True)
    keyboard.add('🔙Назад')
    for task in tasks:
        if task.flag == 'sleep':
            keyboard.add('⏸' + task.name)
        elif task.flag == 'work':
            keyboard.add('▶' + task.name)
        elif task.flag == 'delay':
            keyboard.add('🕒' + task.name)

    await States.MY_TASKS.set()
    await message.answer(text, reply_markup=keyboard)


@dp.message_handler(lambda message: message.text == 'Архив постов', state=States.OFFICE)
async def get_archive_tasks(message: types.Message, state: FSMContext):
    text = 'Архив Тасков:'
    async with state.proxy() as data:
        data['message'].append(text)

    tasks = db.get_archived_tasks(message.from_user.id)
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, selective=True)
    keyboard.add('🔙Назад')
    for task in tasks:
        keyboard.add(task.name)

    await States.ARCHIVE_TASKS.set()
    await message.answer(text, reply_markup=keyboard)


@dp.message_handler(lambda message: message.text == 'Настройки', state=States.OFFICE)
async def get_settings(message: types.Message):
    text = 'Раздел в разработке...'
    await message.answer(text)


# ================================ CREATE =================================== #
@dp.message_handler(content_types=types.ContentType.TEXT, state=States.CREATE_TASK)
async def create_name(message: types.Message, state: FSMContext):
    text = 'Пришлите текст поста (без картинки)'
    async with state.proxy() as data:
        if db.task_in(message.from_user.id, message.text[:16]):
            data['post']['name'] = message.text[:16] + f'_{db.get_last_task_id(message.from_user.id)[0]}'
        else:
            data['post']['name'] = message.text[:16]

        header = get_header(data['post'])

    await States.CREATE_CONTENT.set()
    await message.answer(header)
    await message.answer(text, reply_markup=types.ReplyKeyboardRemove())


@dp.message_handler(content_types=types.ContentType.TEXT, state=States.CREATE_CONTENT)
async def create_content(message: types.Message, state: FSMContext):
    text = message.text
    async with state.proxy() as data:
        data['post']['text'] = text
        header = get_header(data['post'])
        header_keyboard = edit_header_keyboard((data['post']))
        post_keyboard = edit_post_keyboard(data['post'])

    await States.TASK_SETTINGS.set()
    await bot.delete_message(chat_id=message.chat.id, message_id=message.message_id - 4)
    await bot.delete_message(chat_id=message.chat.id, message_id=message.message_id - 3)
    await bot.delete_message(chat_id=message.chat.id, message_id=message.message_id - 2)
    await bot.delete_message(chat_id=message.chat.id, message_id=message.message_id - 1)
    await message.answer(text=header, reply_markup=header_keyboard)
    await message.answer(text=text, reply_markup=post_keyboard)


@dp.edited_message_handler(content_types=types.ContentType.TEXT, state=States.TASK_SETTINGS)
async def edited_content(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['post']['text'] = message.text
        text = get_text_with_img(data['post'])
        post_keyboard = edit_post_keyboard(data['post'])

    await bot.edit_message_text(text=text, chat_id=message.chat.id,
                                message_id=message.message_id + 2, reply_markup=post_keyboard)
# ================================ CREATE =================================== #


# -------------------------------- HEADER -------------------------------- #
# ================================ CHANNELS =================================== #
@dp.callback_query_handler(lambda callback: callback.data in ['add_channels', 'edit_channels'],
                           state=States.TASK_SETTINGS)
async def edit_channels(callback: types.CallbackQuery):
    text = 'Отправьте @channel_name или ссылки на каналы/чаты (разделитель - ПРОБЕЛ)'
    await States.EDIT_CHANNELS.set()
    await callback.message.edit_text(text)


@dp.message_handler(content_types=types.ContentType.TEXT, state=States.EDIT_CHANNELS)
async def set_channels(message: types.Message, state: FSMContext):
    channels = []
    channels.extend(list(set(re.findall(r'@\w{5,}\b', message.text))))
    channels.extend(list(set(re.findall(r't.me/\w{5,}\b', message.text))))
    if channels:
        async with state.proxy() as data:
            offset = data['offset']
            data['offset'] += 1
            data['post']['channels'] = channels
            text = get_text_with_img(data['post'])
            header = get_header(data['post'])
            post_keyboard = edit_post_keyboard(data['post'])
            header_keyboard = edit_header_keyboard(data['post'])

        await message.delete()
        await States.TASK_SETTINGS.set()
        await bot.edit_message_text(text=header, chat_id=message.chat.id,
                                    message_id=message.message_id - (2 + offset), reply_markup=header_keyboard)
        try:
            await bot.edit_message_text(text=text, chat_id=message.chat.id,
                                        message_id=message.message_id - (1 + offset), reply_markup=post_keyboard)
        except MessageNotModified:
            return
    else:
        await error_channel(message, state)


@dp.message_handler(state=States.EDIT_CHANNELS)
async def error_channel(message: types.Message, state: FSMContext):
    text = 'Отправьте @channel_name или ссылки на канлы/чаты (разделитель - ПРОБЕЛ)\n\n' \
           'Некорректные идентификаторы каналов/чатов\nПопробуйте ещё раз!'
    async with state.proxy() as data:
        offset = data['offset']
        data['offset'] += 1
    await message.delete()
    try:
        await bot.edit_message_text(text=text, chat_id=message.chat.id,
                                    message_id=message.message_id - (2 + offset))
    except MessageNotModified:
        return
# ================================ CHANNELS =================================== #


# ================================ COUNT =================================== #
@dp.callback_query_handler(lambda callback: callback.data in ['add_count', 'edit_count'], state=States.TASK_SETTINGS)
async def edit_count(callback: types.CallbackQuery):
    text = r'Отправьте целое число x:  <code>0 &#60; x &#60; 31</code>'
    await States.EDIT_COUNT.set()
    await callback.message.edit_text(text)


@dp.message_handler(regexp=r'\d\d?', state=States.EDIT_COUNT)
async def set_count(message: types.Message, state: FSMContext):
    count = int(re.search(r'\d\d?', message.text).group())
    if 0 < count < 31:
        async with state.proxy() as data:
            data['post']['count'] = count
            offset = data['offset']
            data['offset'] += 1
            text = get_text_with_img(data['post'])
            header = get_header(data['post'])
            post_keyboard = edit_post_keyboard(data['post'])
            header_keyboard = edit_header_keyboard(data['post'])

        await message.delete()
        await States.TASK_SETTINGS.set()
        await bot.edit_message_text(text=header, chat_id=message.chat.id,
                                    message_id=message.message_id - (2 + offset), reply_markup=header_keyboard)
        try:
            await bot.edit_message_text(text=text, chat_id=message.chat.id,
                                        message_id=message.message_id - (1 + offset), reply_markup=post_keyboard)
        except MessageNotModified:
            return
    else:
        await error_count(message, state)


@dp.message_handler(state=States.EDIT_COUNT)
async def error_count(message: types.Message, state: FSMContext):
    text = 'Отправьте целое число <code>0 &#60; x &#60; 31</code>\n\n' \
           'Некорректные данные, попробуйте ещё раз!'
    async with state.proxy() as data:
        offset = data['offset']
        data['offset'] += 1
    await message.delete()
    try:
        await bot.edit_message_text(text=text, chat_id=message.chat.id,
                                    message_id=message.message_id - (2 + offset))
    except MessageNotModified:
        return
# ================================ COUNT =================================== #


# ================================ INTERVAL =================================== #
@dp.callback_query_handler(lambda callback: callback.data in ['add_interval', 'edit_interval'],
                           state=States.TASK_SETTINGS)
async def edit_interval(callback: types.CallbackQuery):
    text = r'Отправьте целое число минут x:  <code>9 &#60; x &#60; 1441</code>'
    await States.EDIT_INTERVAL.set()
    await callback.message.edit_text(text)


@dp.message_handler(regexp=r'\d{2,4}', state=States.EDIT_INTERVAL)
async def set_interval(message: types.Message, state: FSMContext):
    interval = int(re.search(r'\d{2,4}', message.text).group())
    if 9 < interval < 1441:
        async with state.proxy() as data:
            data['post']['interval'] = interval
            offset = data['offset']
            data['offset'] += 1
            text = get_text_with_img(data['post'])
            header = get_header(data['post'])
            post_keyboard = edit_post_keyboard(data['post'])
            header_keyboard = edit_header_keyboard(data['post'])

        await message.delete()
        await States.TASK_SETTINGS.set()
        await bot.edit_message_text(text=header, chat_id=message.chat.id,
                                    message_id=message.message_id - (2 + offset), reply_markup=header_keyboard)
        try:
            await bot.edit_message_text(text=text, chat_id=message.chat.id,
                                        message_id=message.message_id - (1 + offset), reply_markup=post_keyboard)
        except MessageNotModified:
            return
    else:
        await error_interval(message, state)


@dp.message_handler(state=States.EDIT_INTERVAL)
async def error_interval(message: types.Message, state: FSMContext):
    text = 'Отправьте целое число минут x:  <code>9 &#60; x &#60; 1381</code>\n\n' \
           'Некорректные данные, попробуйте ещё раз!'
    async with state.proxy() as data:
        offset = data['offset']
        data['offset'] += 1
    await message.delete()
    try:
        await bot.edit_message_text(text=text, chat_id=message.chat.id,
                                    message_id=message.message_id - (2 + offset))
    except MessageNotModified:
        return
# ================================ INTERVAL =================================== #
# -------------------------------- HEADER -------------------------------- #


# -------------------------------- POST -------------------------------- #
# ================================ IMG =================================== #
@dp.callback_query_handler(lambda callback: callback.data == 'add_img', state=States.TASK_SETTINGS)
async def add_image(callback: types.CallbackQuery):
    text = 'Пришлите картинку (до 5 Мб)'
    await States.EDIT_IMG.set()
    await callback.message.edit_text(text)


@dp.callback_query_handler(lambda callback: callback.data == 'del_img', state=States.TASK_SETTINGS)
async def del_image(callback: types.CallbackQuery, state: FSMContext):
    async with state.proxy() as data:
        data['post']['img'] = ''
        text = data['post']['text']
        post_keyboard = edit_post_keyboard(data['post'])

    await callback.message.edit_text(text, reply_markup=post_keyboard)


@dp.message_handler(content_types=types.ContentType.PHOTO, state=States.EDIT_IMG)
async def set_image(message: types.Message, state: FSMContext):
    tg_url = await message.photo[-1].get_url()
    img_url = get_img_url(tg_url)
    async with state.proxy() as data:
        data['post']['img'] = f'<a href="{img_url}">&#8205;</a>'  # f'[⁠]({img_url})'
        offset = data['offset']
        data['offset'] += 1
        text = get_text_with_img(data['post'])
        post_keyboard = edit_post_keyboard(data['post'])

    await message.delete()
    await States.TASK_SETTINGS.set()
    await bot.edit_message_text(text=text, chat_id=message.chat.id,
                                message_id=message.message_id - (1 + offset), reply_markup=post_keyboard)


@dp.message_handler(state=States.EDIT_IMG)
async def error_img(message: types.Message, state: FSMContext):
    text = 'Пришлите картинку (до 5 Мб)\n\n' \
           'Не могу распознать картинку, попробуйте ещё раз!'
    async with state.proxy() as data:
        offset = data['offset']
        data['offset'] += 1
    await message.delete()
    try:
        await bot.edit_message_text(text=text, chat_id=message.chat.id,
                                    message_id=message.message_id - (1 + offset))
    except MessageNotModified:
        return
# ================================ IMG =================================== #


# ================================ LINK =================================== #
@dp.callback_query_handler(lambda callback: callback.data == 'add_url', state=States.TASK_SETTINGS)
async def add_url(callback: types.CallbackQuery):
    text = 'Пришлите URL-кнопки в формате:\n' \
           '<code>Ссылка 1 - https://www.google.ru/\n' \
           'Ссылка 2 - https://yandex.ru/\n' \
           '...</code>'
    await States.EDIT_URL.set()
    await callback.message.edit_text(text)


@dp.callback_query_handler(lambda callback: callback.data == 'del_url', state=States.TASK_SETTINGS)
async def del_url(callback: types.CallbackQuery, state: FSMContext):
    async with state.proxy() as data:
        data['post']['urls'] = ''
        text = get_text_with_img(data['post'])
        post_keyboard = edit_post_keyboard(data['post'])

    await callback.message.edit_text(text, reply_markup=post_keyboard)


@dp.message_handler(regexp=r'[^`*-]+ - https?://[^\s]+', state=States.EDIT_URL)
async def set_url(message: types.Message, state: FSMContext):
    url_markup = types.InlineKeyboardMarkup()
    urls = re.findall(r'[^`*-]+ - https?://[^\s]+', message.text)
    for i in urls:
        button = types.InlineKeyboardButton(text=i.split(' - ')[0], url=i.split(' - ')[1])
        url_markup.add(button)

    async with state.proxy() as data:
        data['post']['urls'] = url_markup
        offset = data['offset']
        data['offset'] += 1
        text = get_text_with_img(data['post'])
        post_keyboard = edit_post_keyboard(data['post'])

    await message.delete()
    await States.TASK_SETTINGS.set()

    try:
        await bot.edit_message_text(text=text, chat_id=message.chat.id,
                                    message_id=message.message_id - (1 + offset), reply_markup=post_keyboard)
    except ButtonURLInvalid:
        data['post']['urls'] = ''
        post_keyboard = edit_post_keyboard(data['post'])
        await bot.edit_message_text(text=text, chat_id=message.chat.id,
                                    message_id=message.message_id - (1 + offset), reply_markup=post_keyboard)


@dp.message_handler(state=States.EDIT_URL)
async def error_url(message: types.Message, state: FSMContext):
    text = 'Пришлите URL-кнопки в формате:\n' \
           '<code>Ссылка 1 - https://www.google.ru/\n' \
           'Ссылка 2 - https://yandex.ru/\n' \
           '...</code>\n\n' \
           'Некорректные данные, попробуйте ещё раз!'
    async with state.proxy() as data:
        offset = data['offset']
        data['offset'] += 1
    await message.delete()
    try:
        await bot.edit_message_text(text=text, chat_id=message.chat.id,
                                    message_id=message.message_id - (1 + offset))
    except MessageNotModified:
        return
# ================================ LINK =================================== #


# ================================ DELAY =================================== #
@dp.callback_query_handler(lambda callback: callback.data == 'add_delay', state=States.TASK_SETTINGS)
async def add_delay(callback: types.CallbackQuery):
    text = 'Пришлите дату и время, когда Task должен начать исполняться:\n' \
           'Формат сообщения: <code>HH:MM dd.mm.yy</code>'
    await States.EDIT_DELAY.set()
    await bot.edit_message_text(text=text, chat_id=callback.message.chat.id,
                                message_id=callback.message.message_id - 1)


@dp.callback_query_handler(lambda callback: callback.data == 'del_delay', state=States.TASK_SETTINGS)
async def del_delay(callback: types.CallbackQuery, state: FSMContext):
    async with state.proxy() as data:
        data['post']['time_start'] = ''
        data['post']['flag'] = ''
        header = get_header(data['post'])
        header_keyboard = edit_header_keyboard(data['post'])
        text = get_text_with_img(data['post'])
        post_keyboard = edit_post_keyboard(data['post'])

    await bot.edit_message_text(text=header, chat_id=callback.message.chat.id,
                                message_id=callback.message.message_id - 1, reply_markup=header_keyboard)
    await bot.edit_message_text(text=text, chat_id=callback.message.chat.id,
                                message_id=callback.message.message_id, reply_markup=post_keyboard)


@dp.message_handler(regexp=r'^\d{1,2}:\d{1,2} \d{1,2}.\d{1,2}.\d{2}$', state=States.EDIT_DELAY)
async def set_delay(message: types.Message, state: FSMContext):
    try:
        time_start = datetime.datetime.strptime(message.text, '%H:%M %d.%m.%y')
    except ValueError:
        return await error_delay(message, state)

    now_today = datetime.datetime.utcnow() + datetime.timedelta(hours=3)
    if time_start < now_today:
        return await error_delay(message, state)
    elif time_start - now_today < datetime.timedelta(minutes=10):
        return await error_delay(message, state)

    async with state.proxy() as data:
        data['post']['time_start'] = time_start
        data['post']['flag'] = 'delay'
        offset = data['offset']
        data['offset'] += 1
        header = get_header(data['post'])
        header_keyboard = edit_header_keyboard(data['post'])
        text = get_text_with_img(data['post'])
        post_keyboard = edit_post_keyboard(data['post'])

    await message.delete()
    await States.TASK_SETTINGS.set()

    await bot.edit_message_text(text=header, chat_id=message.chat.id,
                                message_id=message.message_id - (2 + offset), reply_markup=header_keyboard)
    await bot.edit_message_text(text=text, chat_id=message.chat.id,
                                message_id=message.message_id - (1 + offset), reply_markup=post_keyboard)


@dp.message_handler(state=States.EDIT_DELAY)
async def error_delay(message: types.Message, state: FSMContext):
    text = 'Пришлите дату и время, когда Task должен начать исполняться:\n' \
           'Формат сообщения: <code>HH:MM dd.mm.yy</code>\n\n' \
           'Некорректные данные, попробуйте ещё раз!'
    async with state.proxy() as data:
        offset = data['offset']
        data['offset'] += 1
    await message.delete()
    try:
        await bot.edit_message_text(text=text, chat_id=message.chat.id,
                                    message_id=message.message_id - (2 + offset))
    except MessageNotModified:
        return
# ================================ DELAY =================================== #
# -------------------------------- POST -------------------------------- #


# ================================ SAVE =================================== #
@dp.callback_query_handler(lambda callback: callback.data == 'save', state=States.TASK_SETTINGS)
async def save_post(callback: types.CallbackQuery, state: FSMContext):
    text = 'Task сохранён. Вы можете найти его в разделе My Tasks'
    async with state.proxy() as data:
        data['post']['user_id'] = callback.from_user.id
        data['post']['flag'] = 'sleep'
        db.add_task(**data['post'])

    await state.reset_data()
    await state.update_data(message=[])
    await States.OFFICE.set()
    await bot.delete_message(chat_id=callback.message.chat.id, message_id=callback.message.message_id - 1)
    await bot.delete_message(chat_id=callback.message.chat.id, message_id=callback.message.message_id)
    await callback.message.answer(text, reply_markup=main_keyboard())
# ================================ SAVE =================================== #


# ================================ RUN =================================== #
@dp.callback_query_handler(lambda callback: callback.data == 'run',
                           state=[States.TASK_SETTINGS, States.MY_TASKS])
async def run_post(callback: types.CallbackQuery, state: FSMContext):
    text = 'Task выполняется. Следить за его прогрессом можно в разделе My Tasks'
    async with state.proxy() as data:
        data['post']['user_id'] = callback.from_user.id
        if data['post']['flag'] == 'sleep' or not data['post']['flag']:
            data['post']['time_start'] = datetime.datetime.utcnow() + datetime.timedelta(hours=3)

            if data['post']['flag'] == 'sleep':
                data['post']['flag'] = 'work'
                db.edit_task(**data['post'])
            else:
                data['post']['flag'] = 'work'
                db.add_task(**data['post'])

            t = bot.loop.create_task(launch_posting(data['post']))
            task_list[data['post']['name']] = t

        elif data['post']['flag'] == 'delay':
            db.add_task(**data['post'])
            t = bot.loop.create_task(delay_posting(data['post']))
            task_list[data['post']['name']] = t

    await state.reset_data()
    await state.update_data(message=[])
    await States.OFFICE.set()
    await bot.delete_message(chat_id=callback.message.chat.id, message_id=callback.message.message_id - 1)
    await bot.delete_message(chat_id=callback.message.chat.id, message_id=callback.message.message_id)
    await callback.message.answer(text, reply_markup=main_keyboard())
# ================================ RUN =================================== #


# ================================ DELETE =================================== #
@dp.callback_query_handler(lambda callback: callback.data == 'del',
                           state=[States.TASK_SETTINGS, States.MY_TASKS])
async def del_post(callback: types.CallbackQuery, state: FSMContext):
    async with state.proxy() as data:
        text = f'Task <b>{data["post"]["name"]}</b> успешно удалён!'
        if data['post']['user_id']:
            db.remove_task(data['post']['user_id'], data['post']['name'])
            t = task_list.pop(data['post']['name'], None)
            if t:
                t.cancel()

    await state.reset_data()
    await state.update_data(message=[])
    await States.OFFICE.set()
    await bot.delete_message(chat_id=callback.message.chat.id, message_id=callback.message.message_id - 1)
    await bot.delete_message(chat_id=callback.message.chat.id, message_id=callback.message.message_id)
    await callback.message.answer(text, reply_markup=main_keyboard())
# ================================ DELETE =================================== #


# ================================ MY TASKS =================================== #
@dp.message_handler(lambda message: message.text, state=States.MY_TASKS)
async def show_task(message: types.Message, state: FSMContext):
    task_data = db.get_task_data(message.from_user.id, name=message.text[1:])
    async with state.proxy() as data:
        data['post'] = task_data
        text = get_text_with_img(data['post'])
        post_keyboard = action_post_keyboard(data['post'])
        header = get_header(data['post'])

    await message.answer(header)
    await message.answer(text, reply_markup=post_keyboard)
# ================================ MY TASKS =================================== #


# ================================ ARCHIVE TASKS =================================== #
@dp.message_handler(lambda message: message.text, state=States.ARCHIVE_TASKS)
async def show_task(message: types.Message):
    data = db.get_task_data(message.from_user.id, name=message.text)
    header = header_template[:37].format(data["name"].upper(), ', '.join(data["channels"]))
    text = get_text_with_img(data)

    await message.answer(header)
    await message.answer(text)
# ================================ ARCHIVE TASKS =================================== #


@dp.message_handler(state='*')
async def del_any_message(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        try:
            data['offset'] += 1
        except KeyError:
            data['offset'] = 0
        await message.delete()


# =================================================================== #
def get_img_url(tg_url):
    url = requests.get('https://api.imgbb.com/1/upload',
                       params={
                           'key': '8f2a824bd7668ecdd86f6f0b7405acef',
                           'image': tg_url,
                           'expiration': '864000'
                       }).json()
    return url['data']['url']


def get_header(data):
    name = data['name'].upper()
    channels = ', '.join(data['channels']) if data['channels'] else '-'
    count = data['count'] if data['count'] else '-'
    interval = data['interval'] if data['interval'] else '-'
    hh = (data['count'] - 1) * data['interval'] // 60 if data['count'] and data['interval'] else '-'
    mm = (data['count'] - 1) * data['interval'] % 60 if data['count'] and data['interval'] else '-'
    time_start = data['time_start'].strftime('%H:%M %d.%m.%y') if data['time_start'] else '-'
    return header_template.format(name, channels, count, interval, hh, mm, time_start)


def get_text_with_img(data):
    return data['text'] + data['img']


async def settings_error_input(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        text = get_text_with_img(data['post'])
        post_keyboard = edit_post_keyboard(data['post'])
        header = get_header(data['post'])

    await States.TASK_SETTINGS.set()
    await message.answer(header)
    await message.answer(text, reply_markup=post_keyboard)


async def launch_posting(data):
    user_id = data['user_id']
    name = data['name']
    count = data['count']
    interval = data['interval']
    channels = data['channels']
    text = get_text_with_img(data)
    urls = data['urls'] or None
    while count:
        for channel in channels:
            try:
                await bot.send_message(channel, text, reply_markup=urls)
            except (Unauthorized, ChatNotFound):
                pass
        if count != 1:
            await asyncio.sleep(interval * 60 - 3)
        db.decrement_counter(user_id, name)
        count -= 1

    task_list.pop(name)
    db.edit_task(user_id=user_id, name=name, flag='archived')


async def delay_posting(data):
    now_today = datetime.datetime.utcnow() + datetime.timedelta(hours=3)
    time_start = data['time_start']
    delay = (time_start - now_today).seconds
    await asyncio.sleep(delay)

    db.edit_task(user_id=data['user_id'], name=data['name'], flag='work')
    t = bot.loop.create_task(launch_posting(data))
    task_list[data['name']] = t


async def database_cleaner():
    while True:
        db.cleaning()
        await asyncio.sleep(12 * 3600)


if __name__ == '__main__':
    bot.loop.create_task(database_cleaner())
    executor.start_polling(dp, skip_updates=True, on_shutdown=shutdown)
