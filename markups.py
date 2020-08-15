from aiogram import types


def main_keyboard():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, selective=True)
    keyboard.row('Создать пост', 'Мои посты')
    keyboard.row('Архив постов', 'Настройки')
    return keyboard


def back_keyboard():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, selective=True)
    keyboard.add('🔙Назад')
    return keyboard


def edit_header_keyboard(data):
    keyboard = types.InlineKeyboardMarkup()
    if data['channels']:
        channels = types.InlineKeyboardButton(text='✅Изменить каналы/чаты', callback_data='edit_channels')
    else:
        channels = types.InlineKeyboardButton(text='❌Добавить каналы/чаты', callback_data='add_channels')
    if data['count']:
        count = types.InlineKeyboardButton(text='✅Изменить кол-во выполнений', callback_data='edit_count')
    else:
        count = types.InlineKeyboardButton(text='❌Добавить кол-во выполнений', callback_data='add_count')
    if data['interval']:
        interval = types.InlineKeyboardButton(text='✅Изменить интервал', callback_data='edit_interval')
    else:
        interval = types.InlineKeyboardButton(text='❌Добавить интервал', callback_data='add_interval')

    keyboard.add(channels)
    keyboard.add(count)
    keyboard.add(interval)
    return keyboard


def edit_post_keyboard(data):
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    if data['img']:
        img = types.InlineKeyboardButton(text='Открепить картинку', callback_data='del_img')
    else:
        img = types.InlineKeyboardButton(text='Прикрепить картинку', callback_data='add_img')

    if data['urls']:
        urls = []
        for btn in data['urls'].inline_keyboard:
            urls.append(types.InlineKeyboardButton(text=btn[0].text, url=btn[0].url))
        for btn in urls:
            keyboard.add(btn)
        url = types.InlineKeyboardButton(text='Удалить URL-кнопки', callback_data='del_url')
    else:
        url = types.InlineKeyboardButton(text='Добавить URL-кнопки', callback_data='add_url')

    if not (data['channels'] and data['count'] and data['interval']):
        keyboard.add(img, url)
        return keyboard

    if data['time_start']:
        delay = types.InlineKeyboardButton(text=data['time_start'].strftime('%H:%M %d.%m.%y'),
                                           callback_data='del_delay')
    else:
        delay = types.InlineKeyboardButton(text='Отложить', callback_data='add_delay')

    save = types.InlineKeyboardButton(text='Сохранить', callback_data='save')
    run = types.InlineKeyboardButton(text='Выполнить', callback_data='run')
    delete = types.InlineKeyboardButton(text='Удалить', callback_data='del')

    keyboard.add(img, url, delay)

    if not data['time_start']:
        keyboard.add(save)

    keyboard.add(run, delete)
    return keyboard


def action_post_keyboard(data):
    keyboard = types.InlineKeyboardMarkup()
    run = types.InlineKeyboardButton(text='Выполнить', callback_data='run')
    stop = types.InlineKeyboardButton(text='Остановить', callback_data='stop')
    delete = types.InlineKeyboardButton(text='Удалить', callback_data='del')

    if data['urls']:
        urls = []
        for btn in data['urls'].inline_keyboard:
            urls.append(types.InlineKeyboardButton(text=btn[0].text, url=btn[0].url))
        for btn in urls:
            keyboard.add(btn)

    if data['flag'] == 'sleep':
        keyboard.add(run)
    elif data['flag'] in ['delay', 'work']:
        keyboard.add(stop)

    keyboard.add(delete)
    return keyboard
