from common import *
from use_mysql import UseMySQL
from crawler import Crawler


intent = discord.Intents.default()
intent.message_content = True
client = commands.Bot(command_prefix="-", intents=intent)
task = None


class UCGInformation:
    @staticmethod
    async def register_tweet(tweet: dict):
        tweet_text = tweet["text"]
        tweet_id = tweet["id"]
        tweet_url = f"https://x.com/{ENVIRONMENT_USER_ID}/status/{tweet_id}"
        is_retweet = tweet_text.startswith("RT @")
        await UseMySQL.run_sql(
            "INSERT INTO tweets (text, tweet_id, url, is_retweet) VALUES (%s, %s, %s, %s)",
            (tweet_text, tweet_id, tweet_url, is_retweet),
        )

    @staticmethod
    async def send_new_environment_tweets(latest_tweets: list):
        channel = client.get_channel(ENVIRONMENT_CHANNEL_ID)
        for tweet in latest_tweets:
            tweet_id = tweet["id"]
            tweet_url = f"https://x.com/{ENVIRONMENT_USER_ID}/status/{tweet_id}"
            existing = (
                await UseMySQL.run_sql(
                    "SELECT id FROM tweets WHERE tweet_id = %s", (tweet_id,)
                )
                != []
            )
            if existing:
                continue
            await channel.send(f"{tweet_url}")
            await UCGInformation.register_tweet(tweet)

    @staticmethod
    async def send_new_official_tweets(latest_tweets: list):
        for tweet in latest_tweets:
            tweet_text = tweet["text"]
            tweet_id = tweet["id"]
            tweet_url = f"https://x.com/{OFFICIAL_USER_ID}/status/{tweet_id}"
            existing = (
                await UseMySQL.run_sql(
                    "SELECT id FROM tweets WHERE tweet_id = %s", (tweet_id,)
                )
                != []
            )
            if existing:
                continue
            # カード関連の情報かどうかで送信先チャンネルを分ける
            if any(
                x in tweet_text
                for x in (
                    "カードデザイン公開",
                    "全カードリスト公開",
                    "パラレルカード公開",
                    "PRカード",
                )
            ):
                channel_id = NEW_CARD_CHANNEL_ID
            else:
                channel_id = OFFICIAL_INFO_CHANNEL_ID
            channel = client.get_channel(channel_id)
            await channel.send(f"{tweet_url}")
            await UCGInformation.register_tweet(tweet)

    @staticmethod
    async def send_new_articles(new_articles: list):
        channel = client.get_channel(OFFICIAL_INFO_CHANNEL_ID)
        for article in new_articles:
            sent = (
                await UseMySQL.run_sql(
                    "SELECT url FROM sent_urls WHERE service = %s AND url = %s",
                    (SERVICE_NAME, article),
                )
                != []
            )
            if sent:
                continue
            await channel.send(article)
            while True:
                title = await Crawler.get_article_title(article)
                if title != "ERROR":
                    break
            await UseMySQL.run_sql(
                "INSERT INTO sent_urls (url, title, category, service) VALUES (%s,  %s, %s, %s)",
                (article, title, "new_article", SERVICE_NAME),
            )


async def main():
    while True:
        try:
            # API系は15分に1回のみ実行
            if await Crawler.check_latest_api_crawl_time():
                new_official_tweets = reversed(
                    await Crawler.fetch_latest_tweets(
                        OFFICIAL_BEARER_TOKEN, OFFICIAL_USER_ID
                    )
                )
                await UCGInformation.send_new_official_tweets(new_official_tweets)
                new_environment_tweets = reversed(
                    await Crawler.fetch_latest_tweets(
                        ENVIRONMENT_BEARER_TOKEN, ENVIRONMENT_USER_ID
                    )
                )
                await UCGInformation.send_new_environment_tweets(new_environment_tweets)
            new_articles = await Crawler.get_new_articles()
            await UCGInformation.send_new_articles(new_articles)
        except Exception as e:
            print(f"Error: {e}")
            traceback.print_exc()
        await asyncio.sleep(60)


@client.command()
async def test(ctx):
    if ctx.channel.id in [
        OFFICIAL_INFO_CHANNEL_ID,
        ENVIRONMENT_CHANNEL_ID,
        NEW_CARD_CHANNEL_ID,
    ]:
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
