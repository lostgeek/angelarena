import discord
from discord.ext import commands
import requests
import random
import logging

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

import redis
redis_server = redis.Redis()
AUTH_TOKEN = str(redis_server.get('DISCORD_AUTH_TOKEN').decode('utf-8'))

intents = discord.Intents.default()
intents.members = True

bot = commands.Bot(command_prefix=commands.when_mentioned_or("!"),
                   description='Angel Arena Bot',
                   intents=intents)

@bot.event
async def on_ready():
    logging.info('Bot ready. Loading tournament extension.')
    bot.load_extension('angelarena.cog')
    await bot.get_cog("TournamentCog").init()

@bot.command()
@commands.has_permissions(administrator=True)
async def reload(ctx):
    bot.reload_extension('angelarena.cog')
    await bot.get_cog("TournamentCog").init()
    await ctx.channel.send('I feel renewed!')

bot.run(AUTH_TOKEN)
