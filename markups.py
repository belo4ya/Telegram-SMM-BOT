from aiogram import types


def office():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, selective=True)
    markup.row('Create Task', 'My Tasks')
    markup.row('Archive Tasks', 'Settings')
    return markup


def back():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, selective=True)
    markup.add('/back')
    return markup


def edit_post(data):
    markup = types.InlineKeyboardMarkup(row_width=1)
    if data['img']:
        img = types.InlineKeyboardButton(text='Открепить картинку', callback_data='del_img')
    else:
        img = types.InlineKeyboardButton(text='Прикрепить картинку', callback_data='add_img')

    if data['urls']:
        urls = []
        for btn in data['urls'].inline_keyboard:
            urls.append(types.InlineKeyboardButton(text=btn[0].text, url=btn[0].url))
        for btn in urls:
            markup.add(btn)
        url = types.InlineKeyboardButton(text='Удалить URL-кнопки', callback_data='del_url')
    else:
        url = types.InlineKeyboardButton(text='Добавить URL-кнопки', callback_data='add_url')

    if data['time_start']:
        delay = types.InlineKeyboardButton(text=data['time_start'].strftime('%H:%M %d.%m.%y'),
                                           callback_data='del_delay')
    else:
        delay = types.InlineKeyboardButton(text='Отложить', callback_data='add_delay')

    save = types.InlineKeyboardButton(text='Сохранить', callback_data='save')
    run = types.InlineKeyboardButton(text='Выполнить', callback_data='run')
    delete = types.InlineKeyboardButton(text='Удалить', callback_data='del')

    markup.add(img, url, delay)

    if not data['time_start']:
        markup.add(save)

    markup.add(run, delete)
    return markup


def action_post(data):
    markup = types.InlineKeyboardMarkup()
    run = types.InlineKeyboardButton(text='Выполнить', callback_data='run')
    delete = types.InlineKeyboardButton(text='Удалить', callback_data='del')

    if data['urls']:
        urls = []
        for btn in data['urls'].inline_keyboard:
            urls.append(types.InlineKeyboardButton(text=btn[0].text, url=btn[0].url))
        for btn in urls:
            markup.add(btn)

    if data['flag'] == 'sleep':
        markup.add(run)

    markup.add(delete)
    return markup
