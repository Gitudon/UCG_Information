from common import *


class UseMySQL:
    pool: aiomysql.Pool | None = None

    @classmethod
    async def init_pool(cls):
        if cls.pool is None:
            cls.pool = await aiomysql.create_pool(
                host=os.getenv("DB_HOST"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
                db=os.getenv("DB_NAME"),
                autocommit=True,
                minsize=1,
                maxsize=5,
            )

    @classmethod
    async def close_pool(cls):
        if cls.pool:
            cls.pool.close()
            await cls.pool.wait_closed()
            cls.pool = None

    @classmethod
    async def run_sql(cls, sql: str, params: tuple = ()) -> list | None:
        async with cls.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, params)
                if sql.strip().upper().startswith("SELECT"):
                    rows = await cur.fetchall()
                    return [r[0] if isinstance(r, tuple) else r for r in rows]
                return None
