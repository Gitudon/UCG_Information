from common import *
from use_mysql import UseMySQL


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

    @classmethod
    async def fetch_latest_tweets(cls, bearer_token: str, user_id: str) -> list:
        retries = 5
        if not user_id:
            return []
        target_url = f"https://api.twitter.com/2/users/{user_id}/tweets"
        headers = {
            "Authorization": f"Bearer {bearer_token}",
            "User-Agent": "v2UserTweetsPython",
        }
        params = {"max_results": GET_TWEET_NUMBER, "tweet.fields": "text"}
        for attempt in range(retries):
            await asyncio.sleep(1)
            response = await cls.session.get(target_url, headers=headers, params=params)
            await cls.register_crawl(target_url, "X_API")
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

    @staticmethod
    async def register_crawl(target_url: str, method: str):
        await UseMySQL.run_sql(
            "INSERT INTO crawls (target_url, method, service) VALUES (%s, %s, %s)",
            (target_url, method, SERVICE_NAME),
        )

    @staticmethod
    async def check_latest_api_crawl_time() -> bool:
        result = await UseMySQL.run_sql(
            "SELECT created_at FROM crawls WHERE method = %s AND service = %s ORDER BY created_at DESC LIMIT 1",
            ("X_API", SERVICE_NAME),
        )
        # 初回クロールの場合はTrueを返す
        if not result:
            return True
        latest_clawl_time = result[0].timestamp()
        current_time = datetime.datetime.now().timestamp()
        # 最後のAPIを用いたクロールから15分経過しているか返す
        return current_time - latest_clawl_time > 60 * 15

    @classmethod
    async def get_new_articles(cls) -> list | str:
        try:
            soup = await cls.try_to_get_soup(TARGET_URL)
            if soup == "FAILED":
                return []
            await cls.register_crawl(TARGET_URL, "HTTP_GET")
            targets = soup.find_all("div", class_="content")
            new_articles = []
            for target in targets:
                new_articles.append(target.find("a").get("href"))
            return new_articles
        except Exception as e:
            print(e)
            return []

    @classmethod
    async def get_article_title(cls, url: str) -> str:
        try:
            soup = await cls.try_to_get_soup(url)
            if soup == "FAILED":
                return "ERROR"
            await cls.register_crawl(TARGET_URL, "HTTP_GET")
            title = soup.find("title").text.strip()
            return title
        except Exception as e:
            print(e)
            return "ERROR"
