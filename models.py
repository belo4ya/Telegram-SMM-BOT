from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, Binary, DateTime
from datetime import datetime

Base = declarative_base()


class Task(Base):
    __tablename__ = 'task'
    id = Column(Integer, primary_key=True, autoincrement=True)
    date_add = Column(DateTime, default=datetime.utcnow())
    user_id = Column(Integer)

    channels = Column(Binary, comment='адресаты')
    count = Column(Integer, comment='кол-во')
    interval = Column(Integer, comment='интервал')
    time_start = Column(DateTime, comment='время отправки первого поста', default=datetime.utcnow())
    flag = Column(String, comment='sleep, work, delay, archived')

    name = Column(String, comment='имя поста', unique=True)
    text = Column(String, comment='текст поста')
    img = Column(String, comment='ссылка на картинку')
    urls = Column(Binary, comment='url-кнопки')

    def __repr__(self):
        return f'<Task(id="{self.id}", name="{self.name}", ' \
               f'user_id="{self.user_id}", text="{self.text}", flag="{self.flag}", ' \
               f'count="{self.count}")>'
