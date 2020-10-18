import logging
import traceback

import discord
import discord.utils
from discord.ext import commands
from wizard import *

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
        self.title = title
        self.organizer = organizer
        self.desc = desc
        self.format = format
        self.system = system
        self.open_message = None
        self.participants = []
        self.message = None

    @staticmethod
    def create_from_data(data):
        return Tournament(data['title'], data['organizer'], data['desc'], data['format'], data['system'])

    def description(self):
        lines = self.desc.split('\n')
        desc = '\n'.join(['> %s'%x for x in lines])
        participants_text = ""
        if len(self.participants) > 0:
            participants_text = "\n**Participants:** " + ', '.join([p.mention for p in self.participants])
        return "**Title:** {0.title}\n**Organizer:** {0.organizer.mention}\n**Format:** {0.format}\n**System:** {1}\nAdditional information:\n{2}{3}".format(self, self.SYSTEMS[self.system], desc, participants_text)

class TournamentCog(commands.Cog):
    def __init__(self, bot, *args):
        super().__init__(*args)

        self.bot = bot
        self.wizards = {}
        self.tournaments = []

        self.announcement_channel = discord.utils.get(self.bot.get_all_channels(), guild__name='Angel Arena', name='announcements')
        if not self.announcement_channel:
            logging.error("Channel #announcements not found.")

    async def init(self):
        await self.initiate_open_tournament_channel()

    async def initiate_open_tournament_channel(self):
        ch = discord.utils.get(self.bot.get_all_channels(), guild__name='Angel Arena', name='open-tournaments')
        self.open_tournament_channel = ch

        # clear messages
        async for message in ch.history(limit=200):
            await message.delete()

        if len(self.tournaments) == 0:
            await ch.send("There are no open tournaments. You can register a new tournament by sending me a DM with `!register_tournament`.")
        else:
            await ch.send("There are {0} open tournaments. Register for them by reacting with an emoji of your choice!".format(len(self.tournaments)))

    async def update_open_tournament_top_message(self):
        m = (await self.open_tournament_channel.history(limit=1, oldest_first=True).flatten())[0]

        if len(self.tournaments) == 0:
            await m.edit(content="There are no open tournaments. You can register a new tournament by sending me a DM with `!register_tournament`.")
        else:
            await m.edit(content="There are {0} open tournaments. Register for them by reacting with an emoji of your choice!".format(len(self.tournaments)))

    async def add_tournament(self, t):
        self.tournaments.append(t)
        await self.announcement_channel.send("A new tournament was registered:\n{0}".format(t.description()))
        t.message = await self.open_tournament_channel.send(t.description())
        await self.update_open_tournament_top_message()

    @commands.command(name='update')
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

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        t = next(filter(lambda x: x.message.id == reaction.message.id, self.tournaments), None)

        if not t:
            logging.error("Could not find tournament connected to this message: %s", reaction.message.content)
            return

        t.participants.append(user)
        await t.message.edit(content=t.description())
        logging.info("%s joined tournament '%s'", user, t.title)

    @commands.Cog.listener()
    async def on_reaction_remove(self, reaction, user):
        t = next(filter(lambda x: x.message.id == reaction.message.id, self.tournaments), None)

        if not t:
            logging.error("Could not find tournament connected to this message: %s", reaction.message.content)
            return

        p = next(filter(lambda x: x.id == user.id, t.participants), None)

        if not p:
            logging.error("Could not find player %s in tournament '%s'", user, t.title)
            return

        t.participants.remove(p)

        await t.message.edit(content=t.description())
        logging.info("%s left tournament '%s'", user, t.title)


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
