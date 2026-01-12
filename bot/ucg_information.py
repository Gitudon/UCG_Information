import os
import asyncio
import traceback
import discord
from discord.ext import commands
import aiohttp
from bs4 import BeautifulSoup
import aiomysql

TOKEN = os.getenv("TOKEN")
intent = discord.Intents.default()
intent.message_content = True
client = commands.Bot(command_prefix="-", intents=intent)
official_info_channel_id = int(os.environ.get("OFFICIAL_INFO_CHANNEL_ID"))
ranking_channel_id = int(os.environ.get("RANKING_CHANNEL_ID"))
new_card_channel_id = int(os.environ.get("NEW_CARD_CHANNEL_ID"))
official_info_user_id = os.getenv("OFFICIAL_INFO_USER_ID")
ranking_user_id = os.getenv("RANKING_USER_ID")
target_url = "https://ultraman-cardgame.com/page/jp/news/news-list"
task = None


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
    async def run_sql(cls, sql: str, params: tuple = ()):
        async with cls.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, params)
                if sql.strip().upper().startswith("SELECT"):
                    rows = await cur.fetchall()
                    return [r[0] if isinstance(r, tuple) else r for r in rows]


class Crawler:
    session: aiohttp.ClientSession | None = None

    @classmethod
    async def init_session(cls):
        if cls.session is None:
            timeout = aiohttp.ClientTimeout(total=30)
            cls.session = aiohttp.ClientSession(timeout=timeout)

    @classmethod
    async def close_session(cls):
        if cls.session:
            await cls.session.close()
            cls.session = None

    @staticmethod
    def make_dummy_public_metrics() -> dict:
        return {
            "retweet_count": -1,
            "reply_count": -1,
            "like_count": -1,
            "quote_count": -1,
        }

    @classmethod
    async def fetch_latest_tweets(cls, max_results: int) -> list:
        retries = 5
        bearer_token = os.getenv("BEARER_TOKEN")
        user_id = os.getenv("TWITTER_USER_ID")
        if not user_id:
            return []
        url = f"https://api.twitter.com/2/users/{user_id}/tweets"
        headers = {
            "Authorization": f"Bearer {bearer_token}",
            "User-Agent": "v2UserTweetsPython",
        }
        # params = {"max_results": max_results, "tweet.fields": "text,public_metrics"}
        params = {"max_results": max_results, "tweet.fields": "text"}
        for attempt in range(retries):
            await asyncio.sleep(1)
            response = await cls.session.get(url, headers=headers, params=params)
            if response.status == 200:
                return (await response.json()).get("data", [])
            elif response.status == 429:
                print(f"レート制限に到達しました。")
                await asyncio.sleep(200 * (attempt + 1))
            else:
                print(
                    f"ツイートの取得に失敗: {response.status}, {await response.text()}"
                )
        return []

    @classmethod
    async def get_soup(cls, url: str) -> BeautifulSoup | str:
        try:
            await asyncio.sleep(1)
            async with cls.session.get(url) as resp:
                if resp.status != 200:
                    return "ERROR"
                text = await resp.text()
                return BeautifulSoup(text, "html.parser")
        except Exception:
            return "ERROR"

    @classmethod
    async def try_to_get_soup(cls, url: str, retries: int = 5) -> BeautifulSoup | str:
        for _ in range(retries):
            soup = await cls.get_soup(url)
            if soup != "ERROR":
                return soup
        return "FAILED"

    @classmethod
    async def get_new_articles(cls) -> list | str:
        try:
            soup = await cls.try_to_get_soup(target_url)
            if soup == "FAILED":
                return "ERROR"
            targets = soup.find_all("div", class_="text-content")
            new_articles = []
            for target in targets:
                new_articles.append(target.find("a").get("href"))
            return new_articles
        except Exception as e:
            print(e)
            return "ERROR"

    @classmethod
    async def get_article_title(cls, url: str) -> str:
        try:
            soup = await cls.try_to_get_soup(url)
            if soup == "FAILED":
                return "ERROR"
            title = soup.find("title").text.strip()
            return title
        except Exception as e:
            print(e)
            return "ERROR"


async def main():
    get_tweet_number = 5
    while True:
        try:
            latest_tweets = reversed(
                await Crawler.fetch_latest_tweets(get_tweet_number)
            )
            if not latest_tweets:
                return
            for tweet in latest_tweets:
                # 仮のpublic_metricsを使用
                public_metrics = tweet.get(
                    "public_metrics", Crawler.make_dummy_public_metrics()
                )
                tweet_text = tweet["text"]
                tweet_id = tweet["id"]
                tweet_url = f"https://x.com/{user_name}/status/{tweet_id}"
                is_retweet = tweet_text.startswith("RT @")
                existing = await UseMySQL.run_sql(
                    "SELECT id FROM tweets WHERE tweet_id = %s", (tweet_id,)
                )
                if existing:
                    continue
                channel = client.get_channel(channel_id)
                await channel.send(
                    f"新しい投稿です！拡散よろしくお願いします！\n{tweet_url}"
                )
                await UseMySQL.run_sql(
                    "INSERT INTO tweets (text, tweet_id, url, is_retweet) VALUES (%s, %s, %s, %s)",
                    (tweet_text, tweet_id, tweet_url, is_retweet),
                )
                await UseMySQL.run_sql(
                    "INSERT INTO public_metrics (tweet_id, retweet_count, reply_count, like_count, quote_count) VALUES (%s, %s, %s, %s, %s)",
                    (
                        tweet_id,
                        public_metrics["retweet_count"],
                        public_metrics["reply_count"],
                        public_metrics["like_count"],
                        public_metrics["quote_count"],
                    ),
                )
        except Exception as e:
            print(f"Error: {e}")
            traceback.print_exc()
        await asyncio.sleep(1000)


def is_correct_channel(ctx) -> bool:
    return ctx.channel.id in [
        official_info_channel_id,
        ranking_channel_id,
        new_card_channel_id,
    ]


@client.event
async def test(ctx):
    if is_correct_channel(ctx):
        await ctx.channel.send("UCG Information Bot is Working!")


@client.event
async def on_ready():
    global task
    await UseMySQL.init_pool()
    await Crawler.init_session()
    print("Bot is ready!")
    if task is None or task.done():
        task = asyncio.create_task(main())


client.run(TOKEN)
