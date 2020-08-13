from aiogram.dispatcher.filters.state import State, StatesGroup


class MenuStates(StatesGroup):

    OFFICE = State()

    CREATE_NAME = State()
    CREATE_CHANNEL = State()
    CREATE_TIME_PARAMS = State()
    CREATE_CONTENT = State()
    CONTENT_SETTINGS = State()
    EDIT_IMG = State()
    EDIT_URL = State()
    EDIT_DELAY = State()

    MY_TASKS = State()

    ARCHIVE_TASKS = State()
    SETTINGS = State()
