import logging
import traceback

import discord
import discord.utils
from discord.ext import commands
from wizard import *
import uuid

class TournamentCreationWizard(Wizard):
    def __init__(self, cog, person):
        self.cog = cog
        self.person = person
        self.stage = 0

        self.data = {'organizer': person}

    async def on_message(self, ctx):
        if self.stage == 0:
            await self.person.send("Hi, I can help you start a tournament on Angel Arena. Since you are not in the list of trusted TOs, this tournament will need to be accepted by an administrator before it goes live.\n\nYou can always go back one step by saying `!back` or cancel the tournament creation entirely by saying `!cancel`.\n\n**Step 1**\nWhat's the name of the tournament?")
            self.stage += 1

        elif self.stage == 1:
            self.data['title'] = ctx.content

            await self.person.send("Tournament name is:\n> {0[title]}\n\n**Step 2**\nWhat is the format of your tournament?".format(self.data))
            self.stage += 1

        elif self.stage == 2:
            self.data['format'] = ctx.content

            options = '\n'.join(["> `{0}` - {1}".format(k,v) for k,v in Tournament.SYSTEMS.items()])
            await self.person.send("Tournament format is:\n> {0[format]}\n\n**Step 3**\nWhat is the tournament system? Number of rounds will be determined by the number of participants and can be adjusted prior to the tournament start.\nOptions are:\n{1}".format(self.data, options))
            self.stage += 1

        elif self.stage == 3:
            if not ctx.content in Tournament.SYSTEMS:
                await self.person.send("Answer not recognized. Your options are:\n `SSS` - Single Sided Swiss\n`DSS` - Double Sided Swiss\n`DSS+Cut` - Double Sided Swiss + Top Cut")
            else:
                self.data['system'] = ctx.content

                await self.person.send("Tournament system is:\n> {1}\n\n**Step 4**\nPlease give us some additional information about your tournament.".format(self.data, Tournament.SYSTEMS[self.data['system']]))
                self.stage += 1

        elif self.stage == 4:
            self.data['desc'] = ctx.content

            t = Tournament.create_from_data(self.data)
            await self.person.send("The information you entered is:\n{0}\n\n If this is correct, answer `yes`.".format(t.description()))
            self.stage += 1

        elif self.stage == 5:
            if ctx.content == "yes":
                await self.create_tournament()
                await self.person.send("Your tournament has been submitted. Good luck and have fun!")
                del self.cog.wizards[ctx.channel]
            else:
                await self.person.send("Cancelling tournament creation.")
                del self.cog.wizards[ctx.channel]
        else:
            await self.person.send("This should not have happened... Please try again.")
            del self.cog.wizards[ctx.channel]

    async def create_tournament(self):
        t = Tournament.create_from_data(self.data)
        await self.cog.add_tournament(t)

class Tournament(object):
    SYSTEMS = {\
            'SSS': 'Single Sided Swiss',\
            'DSS': 'Double Sided Swiss (no cut)',\
            'DSS+Cut': 'Double Sided Swiss with a top cut',\
            }

    def __init__(self, title, organizer, desc, format, system):
        self.id = uuid.uuid4()
        self.title = title
        self.organizer = organizer
        self.desc = desc
        self.format = format
        self.system = system
        self.open_message = None
        self.participants = []
        self.message = None
        self.approval = False

    @staticmethod
    def create_from_data(data):
        return Tournament(data['title'], data['organizer'], data['desc'], data['format'], data['system'])

    def description(self):
        lines = self.desc.split('\n')
        desc = '\n'.join(['> %s'%x for x in lines])
        participants_text = ""
        if len(self.participants) > 0:
            participants_text = "\n**Participants ({0}):** {1}".format(len(self.participants), ', '.join([p.mention for p in self.participants]))

        return "**Title:** {0.title}\n**Organizer:** {0.organizer.mention}\n**Format:** {0.format}\n**System:** {1}\nAdditional information:\n{2}{3}".format(self, self.SYSTEMS[self.system], desc, participants_text)

    def __str__(self):
        return "{0.title} ({0.id})".format(self)

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

    async def approve_tournament(self, reaction, user):
        t = next(filter(lambda x: x.message.id == reaction.message.id, self.tournaments), None)

        if not t:
            logging.error("Could not find approval-awaiting tournament connected to this message: %s", reaction.message.content)
            return

        if reaction.emoji == '👍':
            t.approval = True
            await reaction.message.delete()
            await self.announce_tournament(t)
        elif reaction.emoji == '👎':
            t.approval = False
            await reaction.message.delete()
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

        if not ctx.author.id == t.organizer:
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

        if not ctx.author.id == t.organizer:
            await ctx.channel.send("You are not the TO for this tournament.")
            return

        if not ' '.join(args) == "I am really sure":
            await ctx.channel.send("If you are really sure, that you want to abort this tournament, type `!abort I am really sure`.")
            return

        await self.delete_tournament(t)

    async def tournament_registration(self, reaction, user, add):
        t = next(filter(lambda x: x.message.id == reaction.message.id, self.tournaments), None)

        if not t:
            logging.error("Could not find tournament connected to this message: %s", reaction.message.content)
            return

        p = next(filter(lambda x: x.id == user.id, t.participants), None)

        if add and not p:
            t.participants.append(user)
            await t.message.edit(content=t.description())
            logging.info("%s joined tournament '%s'", user, t)

        if not add and p:
            t.participants.remove(p)
            await t.message.edit(content=t.description())
            logging.info("%s left tournament '%s'", user, t)

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        if reaction.message.channel == self.open_tournament_channel:
            await self.tournament_registration(reaction, user, add=True)

        if reaction.message.channel == self.approve_tournament_channel:
            await self.approve_tournament(reaction, user)

    @commands.Cog.listener()
    async def on_reaction_remove(self, reaction, user):
        if reaction.message.channel == self.open_tournament_channel:
            await self.tournament_registration(reaction, user, add=False)

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
