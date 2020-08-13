import logging
import configparser
import re
import datetime
import asyncio

from aiogram import Bot, Dispatcher, executor, types
from aiogram.dispatcher import FSMContext
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.utils.exceptions import ButtonURLInvalid, Unauthorized, ChatNotFound
import requests

from states import MenuStates
from markups import office, back, edit_post, action_post
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
TEST_CHANNEL = config['Test']['test_channel']
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
        data['post'] = {'user_id': '',
                        'channels': [],
                        'count': None,
                        'interval': None,
                        'time_start': None,
                        'flag': '',
                        'name': '',
                        'text': '',
                        'img': '',
                        'urls': None}
        data['message'] = [text]
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
        data['post'] = {'user_id': '',
                        'channels': [],
                        'count': None,
                        'interval': None,
                        'time_start': None,
                        'flag': '',
                        'name': '',
                        'text': '',
                        'img': '',
                        'urls': None}
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
    async with state.proxy() as data:
        if db.task_in(message.from_user.id, message.text[:16]):
            data['post']['name'] = message.text[:16] + f'_{db.get_last_task_id(message.from_user.id)[0]}'
        else:
            data['post']['name'] = message.text[:16]

        text = f'<b>{data["post"]["name"].upper()}</b>\nВведите каналы через пробел:\n' \
               f'(@channel_1 @channel_2 @channel_3 ... @channel_51)\n'
        data['message'].append(text)

    await MenuStates.CREATE_CHANNEL.set()
    await message.answer(text)


@dp.message_handler(regexp=r'@\w{5,}\b', state=MenuStates.CREATE_CHANNEL)
async def create_channel_with_message(message: types.Message, state: FSMContext):
    channels = list(sorted(set(re.findall(r'@\w{5,}\b', message.text))))
    text = 'Для установки настроек отправьте строку формата:\n' \
           '<code>M-N</code>, где <code>M</code> - временной ' \
           'интервал в минутах, <code>N</code> - кол-во постов\n\n' \
           'Например: <code>150-6</code> - каждые 2 ч 30 мин ' \
           'во все указанные каналы будет отпраляться один пост, всего таких' \
           'операций будет 6. Время исполнения: <code>150 * (6 - 1) = 12 ч 30 мин</code>'
    async with state.proxy() as data:
        data['message'].append(text)
        data['post']['channels'] = channels
        header = get_header(data['post'])

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
            data['message'].append(text)
            data['post']['count'] = int(count)
            data['post']['interval'] = int(interval)
            header = get_header(data['post'])

        await MenuStates.CREATE_CONTENT.set()
        await message.answer(header)
        return await message.answer(text)

    await error_set_time_params(message, state)


@dp.message_handler(state=MenuStates.CREATE_TIME_PARAMS)
async def error_set_time_params(message: types.Message):
    await message.answer('Некорректный формат данных\nПопробуйте ещё раз')


@dp.message_handler(content_types=types.ContentType.TEXT, state=MenuStates.CREATE_CONTENT)
async def create_content(message: types.Message, state: FSMContext):
    text = message.text
    async with state.proxy() as data:
        data['post']['text'] = text
        markup = edit_post(data['post'])
        header = get_header(data['post'])

        await MenuStates.CONTENT_SETTINGS.set()
        await message.answer(header, reply_markup=types.ReplyKeyboardRemove())
        await message.answer(text, reply_markup=markup)


@dp.edited_message_handler(content_types=types.ContentType.TEXT, state=MenuStates.CONTENT_SETTINGS)
async def edited_post(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['post']['text'] = message.text
        text = get_text_with_img(data['post'])
        markup = edit_post(data['post'])

    await bot.edit_message_text(text=text, chat_id=message.chat.id,
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
        markup = edit_post(data['post'])

    await callback.message.edit_text(text, reply_markup=markup)


@dp.message_handler(content_types=types.ContentType.PHOTO, state=MenuStates.EDIT_IMG)
async def set_image(message: types.Message, state: FSMContext):
    tg_url = await message.photo[-1].get_url()
    img_url = get_img_url(tg_url)
    async with state.proxy() as data:
        data['post']['img'] = f'<a href="{img_url}">&#8205;</a>'  # f'[⁠]({img_url})'
        post = data['post']['img'] + data['post']['text']
        markup = edit_post(data['post'])
        header = get_header(data['post'])

    await MenuStates.CONTENT_SETTINGS.set()
    await message.answer(header)
    await message.answer(post, reply_markup=markup)


@dp.message_handler(state=MenuStates.EDIT_IMG)
async def error_img(message: types.Message, state: FSMContext):
    await settings_error_input(message, state)
# ================================ IMG =================================== #


# ================================ LINK =================================== #
@dp.callback_query_handler(lambda callback: callback.data == 'add_url', state=MenuStates.CONTENT_SETTINGS)
async def add_url(callback: types.CallbackQuery):
    text = 'Пришлите URL-кнопки в формате:\n' \
           '<code>Ссылка 1 - https://www.google.ru/\n' \
           'Ссылка 2 - https://yandex.ru/\n' \
           '...</code>'
    await MenuStates.EDIT_URL.set()
    await callback.message.edit_text(text)


@dp.callback_query_handler(lambda callback: callback.data == 'del_url', state=MenuStates.CONTENT_SETTINGS)
async def del_url(callback: types.CallbackQuery, state: FSMContext):
    async with state.proxy() as data:
        data['post']['urls'] = ''
        text = get_text_with_img(data['post'])
        markup = edit_post(data['post'])

    await callback.message.edit_text(text, reply_markup=markup)


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
        markup = edit_post(data['post'])
        header = get_header(data['post'])

    await MenuStates.CONTENT_SETTINGS.set()
    await message.answer(header)

    try:
        await message.answer(post, reply_markup=markup)

    except ButtonURLInvalid:
        data['post']['urls'] = ''
        markup = edit_post(data['post'])
        await message.answer(post, reply_markup=markup)


@dp.message_handler(state=MenuStates.EDIT_URL)
async def error_url(message: types.Message, state: FSMContext):
    await settings_error_input(message, state)
# ================================ LINK =================================== #


# ================================ DELAY =================================== #
@dp.callback_query_handler(lambda callback: callback.data == 'add_delay', state=MenuStates.CONTENT_SETTINGS)
async def delay_post(callback: types.CallbackQuery):
    text = 'Пришлите дату и время, когда Task должен начать исполняться:\n\n' \
           'Формат сообщения: <code>HH:MM dd.mm.yy</code>'
    await MenuStates.EDIT_DELAY.set()
    await callback.message.edit_text(text)


@dp.callback_query_handler(lambda callback: callback.data == 'del_delay', state=MenuStates.CONTENT_SETTINGS)
async def del_delay(callback: types.CallbackQuery, state: FSMContext):
    async with state.proxy() as data:
        data['post']['time_start'] = ''
        data['post']['flag'] = ''
        text = get_text_with_img(data['post'])
        markup = edit_post(data['post'])

    await callback.message.edit_text(text, reply_markup=markup)


@dp.message_handler(regexp=r'^\d{1,2}:\d{1,2} \d{1,2}.\d{1,2}.\d{2}$', state=MenuStates.EDIT_DELAY)
async def set_delay(message: types.Message, state: FSMContext):
    try:
        time_start = datetime.datetime.strptime(message.text, '%H:%M %d.%m.%y')
    except ValueError:
        return await error_delay(message, state)

    now_today = datetime.datetime.utcnow() + datetime.timedelta(hours=3)
    if time_start < now_today:
        return await error_delay(message, state)
    elif time_start - now_today < datetime.timedelta(minutes=10):  # TEMP
        return await error_delay(message, state)

    async with state.proxy() as data:
        data['post']['time_start'] = time_start
        data['post']['flag'] = 'delay'
        text = get_text_with_img(data['post'])
        markup = edit_post(data['post'])
        header = get_header(data['post'])

    await MenuStates.CONTENT_SETTINGS.set()
    await message.answer(header)
    await message.answer(text, reply_markup=markup)


@dp.message_handler(state=MenuStates.EDIT_DELAY)
async def error_delay(message: types.Message, state: FSMContext):
    await settings_error_input(message, state)
# ================================ DELAY =================================== #


# ================================ SAVE =================================== #
@dp.callback_query_handler(lambda callback: callback.data == 'save', state=MenuStates.CONTENT_SETTINGS)
async def save_post(callback: types.CallbackQuery, state: FSMContext):
    text = 'Task сохранён. Вы можете найти его в разделе My Tasks'
    async with state.proxy() as data:
        data['post']['user_id'] = callback.from_user.id
        data['post']['flag'] = 'sleep'
        db.add_task(**data['post'])

    await state.reset_data()
    await state.update_data(message=[])
    await MenuStates.OFFICE.set()
    await bot.delete_message(chat_id=callback.message.chat.id, message_id=callback.message.message_id - 1)
    await bot.delete_message(chat_id=callback.message.chat.id, message_id=callback.message.message_id)
    await callback.message.answer(text, reply_markup=office())
# ================================ SAVE =================================== #


# ================================ RUN =================================== #
@dp.callback_query_handler(lambda callback: callback.data == 'run',
                           state=[MenuStates.CONTENT_SETTINGS, MenuStates.MY_TASKS])
async def run_post(callback: types.CallbackQuery, state: FSMContext):
    text = 'Task выполняется. Следить за его прогрессом можно в разделе My Tasks'
    async with state.proxy() as data:
        data['post']['user_id'] = callback.from_user.id
        if data['post']['flag'] == 'sleep' or not data['post']['flag']:
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
    await MenuStates.OFFICE.set()
    await bot.delete_message(chat_id=callback.message.chat.id, message_id=callback.message.message_id - 1)
    await bot.delete_message(chat_id=callback.message.chat.id, message_id=callback.message.message_id)
    await callback.message.answer(text, reply_markup=office())
# ================================ RUN =================================== #


# ================================ DELETE =================================== #
@dp.callback_query_handler(lambda callback: callback.data == 'del',
                           state=[MenuStates.CONTENT_SETTINGS, MenuStates.MY_TASKS])
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
    await MenuStates.OFFICE.set()
    await bot.delete_message(chat_id=callback.message.chat.id, message_id=callback.message.message_id - 1)
    await bot.delete_message(chat_id=callback.message.chat.id, message_id=callback.message.message_id)
    await callback.message.answer(text, reply_markup=office())
# ================================ DELETE =================================== #


# ================================ MY TASKS =================================== #
@dp.message_handler(lambda message: message.text, state=MenuStates.MY_TASKS)
async def show_task(message: types.Message, state: FSMContext):
    task_data = db.get_task_data(message.from_user.id, name=message.text[1:])
    async with state.proxy() as data:
        data['post'] = task_data
        text = get_text_with_img(data['post'])
        markup = action_post(data['post'])
        header = get_header(data['post'])

    await message.answer(header)
    await message.answer(text, reply_markup=markup)
# ================================ MY TASKS =================================== #


# ================================ ARCHIVE TASKS =================================== #
@dp.message_handler(lambda message: message.text, state=MenuStates.ARCHIVE_TASKS)
async def show_task(message: types.Message):
    data = db.get_task_data(message.from_user.id, name=message.text)
    header = header_template[:37].format(data["name"].upper(), ', '.join(data["channels"]))
    text = get_text_with_img(data)

    await message.answer(header)
    await message.answer(text)
# ================================ ARCHIVE TASKS =================================== #


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
    channels = ', '.join(data['channels'])
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
        markup = edit_post(data['post'])
        header = get_header(data['post'])

    await MenuStates.CONTENT_SETTINGS.set()
    await message.answer(header)
    await message.answer(text, reply_markup=markup)


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
            await asyncio.sleep((interval - 3) * 60)
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
