from sqlalchemy import create_engine
from sqlalchemy.orm.session import sessionmaker

import pickle
import configparser
import datetime
from models import Task

config = configparser.ConfigParser()
config.read('config.ini')


class DataBase:
    DATABASE = config['DataBase']['type_database']
    DB_NAME = config['DataBase']['database']
    HOST = config['DataBase']['host']
    PORT = config['DataBase']['port']
    USER = config['DataBase']['user']
    PASSWORD = config['DataBase']['password']

    def __init__(self):
        self.engine = create_engine(
            f"{self.DATABASE}://{self.USER}:{self.PASSWORD}@{self.HOST}/{self.DB_NAME}",
            echo=True
        )
        self.session = sessionmaker(bind=self.engine)()

    def _create_tables_from_models(self):
        from models import Base
        Base.metadata.create_all(self.engine)

    def _get_task(self, user_id, name=None):
        if name:
            return self.session.query(Task).filter_by(name=name, user_id=user_id).first()
        return self.session.query(Task).filter_by(user_id=user_id).order_by(Task.date_add.desc()).first()

    def add_task(self, **kwargs):
        kwargs['channels'] = pickle.dumps(kwargs['channels'])
        kwargs['urls'] = pickle.dumps(kwargs['urls'])
        task = Task(**kwargs)
        self.session.add(task)
        self.session.commit()

    def get_my_tasks(self, user_id):
        return self.session.query(Task).filter(Task.user_id == user_id, Task.flag.in_(['sleep', 'work'])).\
            order_by(Task.date_add.desc()).all()

    def get_archived_tasks(self, user_id):
        return self.session.query(Task).filter(Task.user_id == user_id, Task.flag == 'archived').\
            order_by(Task.date_add.desc()).all()

    def get_task_data(self, user_id, name=None):
        task = self._get_task(user_id, name)
        data = {
            'user_id': task.user_id,
            'channels': pickle.loads(task.channels),
            'count': task.count,
            'interval': task.interval,
            'time_start': task.time_start,
            'flag': task.flag,

            'name': task.name,
            'text': task.text,
            'img': task.img,
            'urls': pickle.loads(task.urls)
        }
        return data

    def edit_task(self, user_id, name=None, **kwargs):
        task = self._get_task(user_id, name)
        for k, v in kwargs.items():
            setattr(task, k, v)
        self.session.commit()

    def decrement_counter(self, user_id, name):
        task = self._get_task(user_id, name)
        task.count -= 1
        self.session.commit()
        return task.count

    def remove_task(self, name):
        self.session.query(Task).filter_by(name=name).delete()
        self.session.commit()

    def show_table(self):
        print(self.session.query(Task).all())


if __name__ == '__main__':
    db = DataBase()
    test_name = 'Task 6'
    test_channels = ['@channel1, @channel2, @channel3']
    test_count = 10
    test_interval = 30
    test_time_start = datetime.datetime.now()
    test_text = 'Very long long long text'
    test_img = 'https://img.com/my_image.png'
    test_urls = {'url_1': 'https://url1.com',
                 'url_2': 'https://url2.com',
                 'url_3': 'https://url3.com'}
    # db.add_task(name=test_name, channels=test_channels,
    #             count=test_count, interval=test_interval,
    #             time_start=test_time_start, text=test_text,
    #             img=test_img, urls=test_urls)
    db._create_tables_from_models()
    print(db.show_table())
