import re
from loguru import logger
from config import BASE_PATH
from database.create_engine import sessionmaker
from sqlalchemy.ext.asyncio.session import AsyncSession
from sqlalchemy import and_, func, select
from sqlalchemy.orm import selectinload
from create_bot import dp
from database.models import User
import os
import importlib.util
from create_bot import bot
from aiogram.types.user import User as TgUser


async def get_user_by_username(username: str,
                               session: AsyncSession = None) -> User:
    if session is None:
        async with sessionmaker() as session:
            q = await session.execute(
                select(User).where(User.username == username))
            user = q.scalar_one_or_none()
    else:
        q = await session.execute(
            select(User).where(User.username == username))
        user = q.scalar_one_or_none()

    return user


async def get_user_by_id(tg_id, session: AsyncSession = None):
    tg_id = str(id)
    if session is None:
        async with sessionmaker() as session:
            q = await session.execute(select(User).where(User.tg_id == tg_id))
            user = q.scalar_one_or_none()
    else:
        q = await session.execute(select(User).where(User.tg_id == tg_id))
        user = q.scalar_one_or_none()

    return user


def register_routers():
    # Путь к папке с файлами
    routes_folder = 'routes'

    # Список для хранения всех переменных route
    all_routes = []

    # Проходимся по всем файлам в папке
    for filename in os.listdir(routes_folder):
        if filename.endswith('.py'):
            file_path = os.path.join(routes_folder, filename)

            # Импортируем модуль
            spec = importlib.util.spec_from_file_location(
                filename[:-3], file_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # Получаем переменную route, если она существует
            if hasattr(module, 'router'):
                all_routes.append(module.router)

    # Вывод всех найденных переменных route
    for router in all_routes:
        dp.include_router(router)


async def pagination(limit, offset, enity):
    async with sessionmaker() as session:
        # q = select(func.count(Services.id))
        # count = await session.scalar(q)
        # if offset + limit > count:

        q = await session.execute(select(enity).offset(offset).limit(limit))
        # page = SqlalchemyOrmPage(q, page=5, items_per_page=8)
        services = q.scalars().all()

        return services


async def register_user(tg_user: TgUser):
    async with sessionmaker() as session:
        user = User()
        user.username = tg_user.username
        user.first_name = tg_user.first_name
        if tg_user.last_name:
            user.last_name = tg_user.last_name
        user.tg_id = str(tg_user.id)

        session.add(user)

        await session.commit()
        await session.refresh(user)

        return user


async def download_photo(file_id):
    file = await bot.get_file(file_id)
    ext = file.file_path.split(".")[1]
    path = BASE_PATH + "\\images\\" + file_id + "." + ext

    await bot.download_file(file.file_path, path)

    return path


async def multi_user_mailing(data):
    async with sessionmaker() as session:
        q = await session.execute(select(User))
        users = q.scalars().all()

        for user in users:
            if "file" in data:
                await bot.send_document(user.tg_id,
                                        data["file"],
                                        caption=data["text"])
            elif "photo" in data:
                await bot.send_photo(
                    user.tg_id,
                    data["photo"],
                    caption=data["text"],
                    parse_mode="Markdown",
                )
            else:
                await bot.send_message(user.tg_id,
                                       text=data["text"],
                                       parse_mode="Markdown")


async def get_user_by_link_or_id(data, session) -> User:
    if re.match(r"^@?[A-Za-z0-9._]{3,32}$", data):
        # username
        if data.startswith("@"):
            data = data.replace("@", "")

        user = await get_user_by_username(data, session)
    elif re.match(r"https://t.me/[A-Za-z0-9._]{3,32}", data):
        # Ссылка на пользователя
        username = data.replace("https://t.me/", "")
        user = await get_user_by_username(username, session)
    else:
        # id пользователя
        q = await session.execute(select(User).where(User.tg_id == data))
        user = q.scalar_one_or_none()

    return user


async def call_admins(text):
    async with sessionmaker() as session:
        q = await session.execute(select(User).where(User.is_admin))
        admins = q.scalars().all()

        for admin in admins:
            await bot.send_message(admin.tg_id, text)


async def phone_validate(message: Message):
    if message.contact is not None:
        number = message.contact.phone_number
    else:
        number = message.text
        result = re.match(
            r'^(\+7|7|8)?[\s\-]?\(?[489][0-9]{2}\)?[\s\-]?[0-9]{3}[\s\-]?[0-9]{2}[\s\-]?[0-9]{2}$',
            number)
        if result is None:
            kb = Keyboard.send_phone()
            await message.answer(texts.pls_send_phone, reply_markup=kb)

            return None

    return number
