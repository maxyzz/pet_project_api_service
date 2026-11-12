from typing import List, Optional
from psycopg2.extensions import connection
from psycopg2.extras import DictCursor

from models import User, Post, Feed


def get_user(conn: connection, user_id: int) -> Optional[User]:
    """
    Загружает одного пользователя из базы данных по его Id.

    Возвращает объект User, если пользователь найден.
    Если пользователь с таким id отсутствует — возвращает None.
    """

    query = f"select * from public.user where id= {user_id}"

    with conn.cursor(cursor_factory=DictCursor) as cur:
        cur.execute(query, (user_id,))
        row = cur.fetchone()

        if row is None:
            return None
        return User(**row)


def get_post(conn: connection, post_id: int) -> Optional[Post]:
    """
    Загружает один пост из базы данных по его Id.

    Возвращает объект Post, если пост найден.
    Если пост с таким id отсутствует — возвращает None.
    """

    query = f"select * from public.post where id= {post_id}"

    with conn.cursor(cursor_factory=DictCursor) as cur:
        cur.execute(query, (post_id,))
        row = cur.fetchone()

        if row is None:
                    return None
        return Post(**row)


def get_feed(
    conn: connection, user_id: int = None, post_id: int = None, limit: int = 10
) -> List[Feed]:
    """
    Получает список действий пользователей с постами, включая данные о пользователях и постах.

    - Необходимо указать хотя бы один фильтр: user_id или post_id.
    - Возвращает не более `limit` записей.
    - Действия сортируются по времени: от самых свежих к более старым.
    - Используется для получения последних активностей пользователя или взаимодействий с постом.
    """
    if user_id is None and post_id is None:
        raise ValueError("Необходимо указать хотя бы user_id или post_id")

    query = """
SELECT 
            fa.user_id,
            fa.post_id,
            fa.action,
            fa.time,
            
            u.id AS user__id,
            u.gender AS user__gender,
            u.age AS user__age,
            u.country AS user__country,
            u.city AS user__city,
            u.exp_group AS user__exp_group,
            u.os AS user__os,
            u.source AS user__source,
            
            p.id AS post__id,
            p.text AS post__text,
            p.topic AS post__topic
        FROM feed_action fa
        JOIN "user" u ON fa.user_id = u.id
        JOIN post p ON fa.post_id = p.id
        WHERE 1=1
"""
    params = {}
    if user_id is not None:
        query += " AND fa.user_id = %(user_id)s"
        params["user_id"] = user_id
    if post_id is not None:
        query += " AND fa.post_id = %(post_id)s"
        params["post_id"] = post_id

    query += " ORDER BY fa.time DESC LIMIT %(limit)s"
    params["limit"] = limit

    result = []
    with conn.cursor(cursor_factory=DictCursor) as cur:
        cur.execute(query, params)
        rows = cur.fetchall()
        
        # 3. Преобразуем каждую строку в связанные Pydantic-модели
        for row in rows:
            # Разворачиваем плоский словарь строки в древовидную структуру для Pydantic
            user_data = {key.replace("user__", ""): value for key, value in row.items() if key.startswith("user__")}
            post_data = {key.replace("post__", ""): value for key, value in row.items() if key.startswith("post__")}
            
            # Собираем вложенные объекты
            user_obj = User(**user_data)
            post_obj = Post(**post_data)
            
            # Создаем корневой объект Feed, передавая в него созданные user и post
            feed_item = Feed(
                user_id=row["user_id"],
                post_id=row["post_id"],
                action=row["action"],
                time=row["time"],
                user=user_obj,
                post=post_obj
            )
            result.append(feed_item)

    return result


def get_recommended_feed(conn: connection, id: int, limit: int) -> List[Post]:
    """
    Возвращает список top-N постов с наибольшим числом лайков.

    Это базовая реализация рекомендательной системы (baseline),
    которая не учитывает индивидуальные предпочтения, а показывает
    одинаковые популярные посты всем пользователям.

    Параметры:
        conn (connection): подключение к базе данных.
        id (int): ID пользователя (в этой версии не используется,
                  но оставлен для совместимости с будущей логикой).
        limit (int): количество постов в выдаче.

    Возвращает:
        List[Post]: список объектов Post, отсортированных по убыванию популярности.
    """
    query = """
        select p.id,p.text,p.topic from public.post p
        join public.feed_action f on f.post_id = p.id
        where f.action='like'
        group by p.id,p.text,p.topic
        order by count(f.post_id) desc
        limit %s
        """

    with conn.cursor(cursor_factory=DictCursor) as cur:
        cur.execute(query, (limit,))
        rows = cur.fetchall()
        return [Post(**row) for row in rows]