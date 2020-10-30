import logging
import traceback
import discord
import discord.utils
from discord.ext import commands

from angelarena.tournament import *

class TournamentCog(commands.Cog):
    def __init__(self, bot, *args):
        super().__init__(*args)

        self.bot = bot
        self.wizards = {}
        self.tournaments = []
        self.guild = discord.utils.get(self.bot.guilds, name="Angel Arena")

        self.announcement_channel = discord.utils.get(self.bot.get_all_channels(), guild__name="Angel Arena", name='announcements')
        if not self.announcement_channel:
            logging.error("Channel #announcements not found.")

    async def init(self):
        await self.initiate_open_tournament_channel()
        await self.initiate_approve_tournament_channel()

    async def initiate_open_tournament_channel(self):
        ch = discord.utils.get(self.bot.get_all_channels(), guild__name='Angel Arena', name='open-tournaments')
        self.open_tournament_channel = ch

        if not ch:
            logging.error("Channel #open-tournaments not found.")

        # clear messages
        ms = await ch.history(limit=200).flatten()
        await ch.delete_messages(ms)

        if len(self.tournaments) == 0:
            await ch.send("There are no open tournaments. You can register a new tournament by sending me a DM with `!register_tournament`.")
        else:
            await ch.send("There are {0} open tournaments. Register for them by reacting with an emoji of your choice!".format(len(self.tournaments)))

    async def initiate_approve_tournament_channel(self):
        ch = discord.utils.get(self.bot.get_all_channels(), guild__name='Angel Arena', name='approve-tournaments')
        self.approve_tournament_channel = ch

        if not ch:
            logging.error("Channel #approve-tournaments not found.")

        # clear messages
        ms = await ch.history(limit=200).flatten()
        await ch.delete_messages(ms)

    async def update_open_tournament_top_message(self):
        m = (await self.open_tournament_channel.history(limit=1, oldest_first=True).flatten())[0]

        if len(self.tournaments) == 0:
            await m.edit(content="There are no open tournaments. You can register a new tournament by sending me a DM with `!register_tournament`.")
        else:
            await m.edit(content="There are {0} open tournaments. Register for them by reacting with an emoji of your choice!".format(len(self.tournaments)))

    async def announce_tournament(self, t):
        if not t.approval:
            t.message = await self.approve_tournament_channel.send("A new tournament was registered:\n{0}".format(t.description()))
        else:
            await self.announcement_channel.send("A new tournament was registered:\n{0}".format(t.description()))
            t.message = await self.open_tournament_channel.send(t.description())
            await self.update_open_tournament_top_message()

    async def add_tournament(self, t):
        # check if organizer is in the TO group
        role = discord.utils.find(lambda r: r.name == 'Tournament Organizer', self.announcement_channel.guild.roles)
        if next(filter(lambda x: x == role, t.organizer.roles), None):
            t.approval = True
        else:
            t.approval = False
        self.tournaments.append(t)
        await self.announce_tournament(t)

    async def approve_tournament(self, message_id, user_id, emoji):
        t = next(filter(lambda x: x.message.id == message_id, self.tournaments), None)

        if not t:
            logging.error(f"Could not find approval-awaiting tournament connected to this message: {message_id}")
            return

        user = self.guild.get_member(user_id)
        message = await self.approve_tournament_channel.fetch_message(message_id)

        if emoji.name == '👍':
            t.approval = True
            await message.delete()
            await self.announce_tournament(t)
        elif emoji.name == '👎':
            t.approval = False
            await message.delete()
            self.tournaments.remove(t)
            del t

    async def prepare_tournament(self, t):
        t.role = await self.guild.create_role(name=t.title, mentionable=True)
        t.category = await self.guild.create_category(t.title, position=10000, overwrites = {
            self.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            t.role: discord.PermissionOverwrite(read_messages=True)
            })
        t.lobby = await t.category.create_text_channel("Lobby")

        for p in t.participants:
            await p.add_roles(t.role)

        await t.lobby.send("{0} Welcome in this tournament lobby. We're in the check-in phase until ... (I need to implement this). React to this message with any emoji to check-in to this tournament.".format(t.role.mention))

    async def delete_tournament(self, t):
        for ch in t.category.channels:
            await ch.delete()
        await t.category.delete()
        await t.role.delete()
        self.tournaments.remove(t)
        del t

    @commands.command(name='update')
    @commands.has_role('Oversight AI')
    async def _update(self, ctx):
        await self.update_open_tournament_top_message()

    @commands.command(name='register_tournament', aliases=['new_tournament'])
    async def _register_tournament(self, ctx):
        dm_channel = await ctx.author.create_dm()

        self.wizards[dm_channel] = TournamentCreationWizard(self, ctx.author)

        ctx.content = ""
        if not isinstance(ctx.channel, discord.DMChannel):
            await self.wizards[dm_channel].on_message(ctx)
            await ctx.channel.send("{0}, I have sent you a DM!".format(ctx.author.mention))

    @commands.command(name='kickoff', aliases=['start'])
    async def _kickoff(self, ctx, *args):
        title = ' '.join(args)
        if len(title) == 0:
            await ctx.channel.send("No argument found. Usage: `!kickoff <tournament title>`")
            return

        t = next(filter(lambda x: x.title == title, self.tournaments), None)
        if not t:
            await ctx.channel.send("No tournament called `{0}` found.".format(title))
            return

        if not ctx.author.id == t.organizer.id:
            await ctx.channel.send("You are not the TO for this tournament.")
            return

        await self.prepare_tournament(t)
        await ctx.channel.send("Tournament lobby prepared. Good luck and have fun!")

    @commands.command(name='abort', aliases=['delete'])
    async def _abort(self, ctx, *args):
        t = next(filter(lambda x: x.category == ctx.channel.category, self.tournaments), None)
        if not t:
            await ctx.channel.send("Use this command only in a tournament lobby.")
            return

        if not ctx.author.id == t.organizer.id:
            await ctx.channel.send("You are not the TO for this tournament.")
            return

        if not ' '.join(args) == "I am really sure":
            await ctx.channel.send("If you are really sure, that you want to abort this tournament, type `!abort I am really sure`.")
            return

        await self.delete_tournament(t)

    async def tournament_registration(self, message_id, user_id, emoji, add=True):
        t = next(filter(lambda x: x.message.id == message_id, self.tournaments), None)

        if not t:
            logging.error(f"Could not find tournament connected to this message: {message_id}")
            return

        p = next(filter(lambda x: x.id == user_id, t.participants), None)
        user = self.guild.get_member(user_id)

        if add and not p:
            t.participants.append(user)
            await t.message.edit(content=t.description())
            logging.info("%s joined tournament '%s'", user, t)

        if not add and p:
            t.participants.remove(p)
            await t.message.edit(content=t.description())
            logging.info("%s left tournament '%s'", user, t)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        if payload.channel_id == self.open_tournament_channel.id:
            await self.tournament_registration(payload.message_id, payload.user_id, payload.emoji, add=True)

        if payload.channel_id == self.approve_tournament_channel.id:
            await self.approve_tournament(payload.message_id, payload.user_id, payload.emoji)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        if payload.channel_id == self.open_tournament_channel.id:
            await self.tournament_registration(payload.message_id, payload.user_id, payload.emoji, add=False)

    @commands.Cog.listener()
    async def on_message(self, ctx):
        if ctx.author == self.bot.user:
            return

        if ctx.channel in self.wizards:
            try:
                await self.wizards[ctx.channel].on_message(ctx)
            except:
                logging.error("Wizard failed in channel %s. Removing wizard. Traceback: \n%s", ctx.channel, traceback.format_exc())
                del self.wizards[ctx.channel]

    @commands.command()
    async def test(self, ctx):
        t = Tournament("Test tournament", ctx.author, "Description", "Standard", "SSS")
        await self.add_tournament(t)

def setup(bot):
    cog = TournamentCog(bot)
    bot.add_cog(cog)
    logging.info('Tournament cog loaded.')

def teardown(bot):
    bot.remove_cog("TournamentCog")
    logging.info('Tournament cog unloaded.')
