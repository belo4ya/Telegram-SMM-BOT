from sqlalchemy import create_engine
from sqlalchemy.orm.session import sessionmaker

import pickle
import configparser
from datetime import timedelta
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
        self.engine = create_engine(f"{self.DATABASE}://{self.USER}:{self.PASSWORD}@{self.HOST}/{self.DB_NAME}")
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
        return self.session.query(Task).filter(Task.user_id == user_id, Task.flag != 'archived').\
            order_by(Task.date_add.desc()).all()

    def get_archived_tasks(self, user_id):
        return self.session.query(Task).filter(Task.user_id == user_id, Task.flag == 'archived').\
            order_by(Task.date_add.desc()).all()[:10]

    def get_task_data(self, user_id, name=None):
        task = self._get_task(user_id, name)
        if task:
            data = {
                'user_id': task.user_id,
                'channels': pickle.loads(task.channels),
                'count': task.count,
                'interval': task.interval,
                'time_start': task.time_start + timedelta(hours=3),
                'flag': task.flag,

                'name': task.name,
                'text': task.text,
                'img': task.img,
                'urls': pickle.loads(task.urls)
            }
            return data
        return None

    def edit_task(self, **kwargs):
        task = self._get_task(kwargs['user_id'], kwargs['name'])
        try:
            kwargs['channels'] = pickle.dumps(kwargs['channels'])
        except KeyError:
            pass
        try:
            kwargs['urls'] = pickle.dumps(kwargs['urls'])
        except KeyError:
            pass
        for k, v in kwargs.items():
            setattr(task, k, v)
        self.session.commit()

    def decrement_counter(self, user_id, name):
        task = self._get_task(user_id, name)
        task.count -= 1
        self.session.commit()
        return task.count

    def task_in(self, user_id, name):
        if self.session.query(Task.name).filter_by(user_id=user_id, name=name).first():
            return True
        return False

    def get_last_task_id(self, user_id):
        return self.session.query(Task.id).filter_by(user_id=user_id).order_by(Task.id.desc()).first()

    def remove_task(self, user_id,  name):
        self.session.query(Task).filter_by(user_id=user_id, name=name).delete()
        self.session.commit()

    def cleaning(self):
        users = self.session.query(Task.user_id.distinct()).all()
        for user in users:
            tasks = self.session.query(Task.name).filter_by(user_id=user[0], flag='archived').\
                order_by(Task.date_add.desc()).offset(10).all()
            if tasks:
                for task in tasks:
                    self.session.query(Task).filter_by(name=task[0]).delete()

        self.session.commit()

    def show_table(self):
        print(self.session.query(Task).all())


if __name__ == '__main__':
    db = DataBase()
    # db._create_tables_from_models()
    print(db.show_table())
