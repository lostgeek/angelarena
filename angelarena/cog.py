import logging
import traceback
import sys
import imp
import pickle

import discord
import discord.utils
from discord.ext import commands

from angelarena import tournament

class TournamentCog(commands.Cog):
    def __init__(self, bot, *args):
        super().__init__(*args)

        self.bot = bot
        self.wizards = {}
        self.tournaments = []

        self.load()

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

        number_of_open_tournaments = sum(1 for _ in filter(lambda t: t.approval and not t.running, self.tournaments))
        if number_of_open_tournaments == 0:
            await ch.send(content="There are no open tournaments. You can register a new tournament by sending me a DM with `!register_tournament`.")
        elif number_of_open_tournaments == 1:
            await ch.send(content="There is one open tournament. Register for it by reacting with an emoji of your choice!")
        else:
            await ch.send(content=f"There are {number_of_open_tournaments} open tournaments. Register for them by reacting with an emoji of your choice!")

        for t in filter(lambda t: t.approval and not t.running, self.tournaments):
            try:
                message = await self.open_tournament_channel.fetch_message(t.message_id)
            except:
                message = await self.open_tournament_channel.send(self.tournament_description(t))
                t.message_id = message.id

        await self.update_open_tournament_top_message()

    async def initiate_approve_tournament_channel(self):
        ch = discord.utils.get(self.bot.get_all_channels(), guild__name='Angel Arena', name='approve-tournaments')
        self.approve_tournament_channel = ch

        if not ch:
            logging.error("Channel #approve-tournaments not found.")

        # clear messages
        ms = await ch.history(limit=200).flatten()
        await ch.delete_messages(ms)

        for t in filter(lambda t: not t.approval and not t.running, self.tournaments):
            try:
                message = await self.approve_tournament_channel.fetch_message(t.message_id)
            except:
                message = await self.approve_tournament_channel.send("A new tournament was registered:\n{0}".format(self.tournament_description(t)))
                t.message_id = message.id

    async def update_open_tournament_top_message(self):
        m = (await self.open_tournament_channel.history(limit=1, oldest_first=True).flatten())[0]

        number_of_open_tournaments = sum(1 for _ in filter(lambda t: t.approval and not t.running, self.tournaments))
        if number_of_open_tournaments == 0:
            await m.edit(content="There are no open tournaments. You can register a new tournament by sending me a DM with `!register_tournament`.")
        elif number_of_open_tournaments == 1:
            await m.edit(content="There is one open tournament. Register for it by reacting with an emoji of your choice!")
        else:
            await m.edit(content=f"There are {number_of_open_tournaments} open tournaments. Register for them by reacting with an emoji of your choice!")

    async def announce_tournament(self, t):
        if not t.approval:
            message = await self.approve_tournament_channel.send("A new tournament was registered:\n{0}".format(self.tournament_description(t)))
            t.message_id = message.id
        else:
            await self.announcement_channel.send("A new tournament was registered:\n{0}".format(self.tournament_description(t)))
            message = await self.open_tournament_channel.send(self.tournament_description(t))
            t.message_id = message.id
            await self.update_open_tournament_top_message()

    async def add_tournament(self, t):
        # check if organizer is in the TO group
        role = discord.utils.find(lambda r: r.name == 'Tournament Organizer', self.announcement_channel.guild.roles)
        organizer = self.guild.get_member(t.organizer_id)

        if next(filter(lambda x: x == role, organizer.roles), None):
            t.approval = True
        else:
            t.approval = False
        self.tournaments.append(t)
        await self.announce_tournament(t)

    async def approve_tournament(self, message_id, user_id, emoji):
        t = next(filter(lambda t: t.message_id == message_id, self.tournaments), None)

        if not t:
            logging.error(f"Could not find approval-awaiting tournament connected to this message_id: {message_id}")
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
        role = await self.guild.create_role(name=t.title, mentionable=True)
        t.role_id = role.id
        category = await self.guild.create_category(t.title, position=10000, overwrites = {
            self.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            role: discord.PermissionOverwrite(read_messages=True)
            })
        t.category_id = category.id
        lobby = await category.create_text_channel("Lobby")
        t.lobby_id = lobby.id
        results = await category.create_text_channel("Results")
        t.results_id = results.id
        check_in = await category.create_text_channel("Check-in")
        t.check_in_id = check_in.id
        bot_commands = await category.create_text_channel("Bot-commands")
        t.bot_commands_id = bot_commands.id

        for p_id in t.participants:
            p = self.guild.get_member(p_id)
            await p.add_roles(role)

        t.running = True
        message = await self.open_tournament_channel.fetch_message(t.message_id)
        await message.delete()

        await lobby.send("{0} Welcome in this tournament lobby. We're in the check-in phase until ... (I need to implement this).".format(role.mention))

        for p_id in t.participants:
            p = self.guild.get_member(p_id)
            dm_channel = await p.create_dm()
            self.wizards[dm_channel] = tournament.TournamentCheckInWizard(self, t, p)
            await self.wizards[dm_channel].on_message(None)

    async def delete_tournament(self, t):
        category = self.guild.get_channel(t.category_id)
        role = self.guild.get_role(t.role_id)

        for ch in category.channels:
            await ch.delete()
        await category.delete()
        await role.delete()
        self.tournaments.remove(t)
        del t

    @commands.command(name='update')
    @commands.has_role('Oversight AI')
    async def _update(self, ctx):
        await self.update_open_tournament_top_message()

    @commands.command(name='register_tournament', aliases=['new_tournament'])
    async def _register_tournament(self, ctx):
        dm_channel = await ctx.author.create_dm()

        self.wizards[dm_channel] = tournament.TournamentCreationWizard(self, ctx.author)

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

        if not ctx.author.id == t.organizer_id:
            await ctx.channel.send("You are not the TO for this tournament.")
            return

        await self.prepare_tournament(t)
        await ctx.channel.send("Tournament lobby prepared. Good luck and have fun!")

    @commands.command(name='abort', aliases=['delete'])
    async def _abort(self, ctx, *args):
        t = next(filter(lambda t: t.category_id == ctx.channel.category.id, self.tournaments), None)
        if not t:
            await ctx.channel.send("Use this command only in a tournament lobby.")
            return

        if not ctx.author.id == t.organizer_id:
            await ctx.channel.send("You are not the TO for this tournament.")
            return

        if not ' '.join(args) == "I am really sure":
            await ctx.channel.send("If you are really sure, that you want to abort this tournament, type `!abort I am really sure`.")
            return

        await self.delete_tournament(t)

    @commands.command(name='checkin', aliases=['check-in', 'check'])
    async def _checkin(self, ctx, *args):
        t = next(filter(lambda t: t.category_id == ctx.message.channel.category_id, self.tournaments), None)
        if not t:
            await ctx.channel.send("Please use this command in a tournament channel")
            return

        dm_channel = await ctx.author.create_dm()
        self.wizards[dm_channel] = tournament.TournamentCheckInWizard(self, t, ctx.author)
        await self.wizards[dm_channel].on_message(None)

    async def tournament_registration(self, message_id, user_id, emoji, add=True):
        t = next(filter(lambda x: x.message_id == message_id, self.tournaments), None)

        if not t:
            logging.error(f"Could not find tournament connected to this message_id: {message_id}")
            return

        message = await self.open_tournament_channel.fetch_message(t.message_id)

        if add and not user_id in t.participants:
            t.participants.append(user_id)
            await message.edit(content=self.tournament_description(t))
            logging.info(f"{user_id} joined tournament '{t}'")

        if not add and user_id in t.participants:
            t.participants.remove(user_id)
            await message.edit(content=self.tournament_description(t))
            logging.info(f"{user_id} left tournament '{t}'")

    def tournament_description(self, tournament):
        lines = tournament.desc.split('\n')
        desc = '\n'.join(['> %s'%x for x in lines])
        participants_text = ""
        if len(tournament.participants) > 0:
            participants_text = "\n**Participants ({0}):** {1}".format(len(tournament.participants), ', '.join([self.guild.get_member(p_id).mention for p_id in tournament.participants]))

        return f"**Title:** {tournament.title}\n**Organizer:** {self.guild.get_member(tournament.organizer_id).mention}\n**Format:** {tournament.format}\n**Tournament system:** {tournament.system_text}\nAdditional information:\n{desc}{participants_text}"

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
    @commands.has_permissions(administrator=True)
    async def test(self, ctx):
        t = tournament.SSSTournament("Test tournament", ctx.author.id, "Description", "Standard")
        await self.add_tournament(t)

    @commands.command(name='save')
    @commands.has_permissions(administrator=True)
    async def _save(self, ctx):
        self.save()
        await ctx.channel.send("Saved state!")

    @commands.command(name='load')
    @commands.has_permissions(administrator=True)
    async def _load(self, ctx):
        self.load()
        await ctx.channel.send("Loaded previous state!")

    def save(self):
        logging.info("Saving bot data")
        f = open('tournaments.p', 'wb')
        pickle.dump(self.tournaments, f)
        f.close()

    def load(self):
        logging.info("Loading bot data")
        try:
            f = open('tournaments.p', 'rb')
            self.tournaments = pickle.load(f)
            f.close()
        except:
            logging.info("Loading bot data failed")

def setup(bot):
    imp.reload(tournament)
    cog = TournamentCog(bot)
    bot.add_cog(cog)
    logging.info('Tournament cog loaded.')

def teardown(bot):
    bot.get_cog("TournamentCog").save()
    bot.remove_cog("TournamentCog")
    logging.info('Tournament cog unloaded.')
