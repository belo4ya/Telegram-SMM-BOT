from aiogram.dispatcher.filters.state import State, StatesGroup


class States(StatesGroup):

    OFFICE = State()

    # Task
    CREATE_TASK = State()
    CREATE_CONTENT = State()
    TASK_SETTINGS = State()

    # Header
    EDIT_CHANNELS = State()
    EDIT_COUNT = State()
    EDIT_INTERVAL = State()

    # Post
    EDIT_IMG = State()
    EDIT_URL = State()
    EDIT_DELAY = State()

    MY_TASKS = State()
    ARCHIVE_TASKS = State()
    SETTINGS = State()
