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


def edit_post():
    markup = types.InlineKeyboardMarkup()
    add_img = types.InlineKeyboardButton(text='Прикрепить картинку', callback_data='add_img')
    add_url = types.InlineKeyboardButton(text='Добавить URL-кнопки', callback_data='add_url')
    save = types.InlineKeyboardButton(text='Сохранить', callback_data='save')
    run = types.InlineKeyboardButton(text='Выполнить', callback_data='run')
    set_delay = types.InlineKeyboardButton(text='Отложить', callback_data='delay')
    delete = types.InlineKeyboardButton(text='Удалить', callback_data='del')
    markup.add(add_img)
    markup.add(add_url)
    markup.add(save)
    markup.add(run)
    markup.add(set_delay)
    markup.add(delete)
    return markup


def action_post(status):
    markup = types.InlineKeyboardMarkup()
    delete = types.InlineKeyboardButton(text='Удалить', callback_data='del')
    if status == 'sleep':
        markup.add(types.InlineKeyboardButton(text='Выполнить', callback_data='run'))
    markup.add(delete)
    return markup
