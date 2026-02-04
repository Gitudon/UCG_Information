import datetime
import os
import asyncio
import traceback
import discord
from discord.ext import commands
import aiohttp
from bs4 import BeautifulSoup
import aiomysql

SERVICE_NAME = "UCG_Information"
TOKEN = os.getenv("TOKEN")
OFFICIAL_INFO_CHANNEL_ID = int(os.environ.get("OFFICIAL_INFO_CHANNEL_ID"))
ENVIRONMENT_CHANNEL_ID = int(os.environ.get("ENVIRONMENT_CHANNEL_ID"))
NEW_CARD_CHANNEL_ID = int(os.environ.get("NEW_CARD_CHANNEL_ID"))
OFFICIAL_USER_ID = os.getenv("OFFICIAL_USER_ID")
OFFICIAL_BEARER_TOKEN = os.getenv("OFFICIAL_BEARER_TOKEN")
ENVIRONMENT_USER_ID = os.getenv("ENVIRONMENT_USER_ID")
ENVIRONMENT_BEARER_TOKEN = os.getenv("ENVIRONMENT_BEARER_TOKEN")
TARGET_URL = "https://ultraman-cardgame.com/page/jp/news/news-list"
GET_TWEET_NUMBER = 5
