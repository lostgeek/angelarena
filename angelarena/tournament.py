import logging

import uuid

from angelarena import wizard, system

SYSTEMS = {\
        'SSS': 'Single Sided Swiss',\
        #  'DSS': 'Double Sided Swiss (no cut)',\
        #  'DSS+Cut': 'Double Sided Swiss with a top cut',\
        }

class TournamentCreationWizard(wizard.DMWizard):
    def __init__(self, cog, person):
        self.cog = cog
        self.person = person
        self.stage = 0

        self.data = {'organizer': person.id}

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

            options = '\n'.join(["> `{0}` - {1}".format(k,v) for k,v in SYSTEMS.items()])
            await self.person.send("Tournament format is:\n> {0[format]}\n\n**Step 3**\nWhat is the tournament system? Number of rounds will be determined by the number of participants and can be adjusted prior to the tournament start.\nOptions are:\n{1}".format(self.data, options))
            self.stage += 1

        elif self.stage == 3:
            if not ctx.content in SYSTEMS:
                await self.person.send("Answer not recognized. Your options are:\n `SSS` - Single Sided Swiss\n`DSS` - Double Sided Swiss\n`DSS+Cut` - Double Sided Swiss + Top Cut")
            else:
                self.data['system'] = ctx.content

                await self.person.send("Tournament system is:\n> {1}\n\n**Step 4**\nPlease give us some additional information about your tournament.".format(self.data, SYSTEMS[self.data['system']]))
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
        if self.data['system'] == 'SSS':
            t = SSSTournament.create_from_data(self.data)
        await self.cog.add_tournament(t)

class TournamentCheckInWizard(wizard.DMWizard):
    def __init__(self, cog, tournament, person):
        self.cog = cog
        self.tournament = tournament
        self.person = person

        self.corp_deck = None
        self.runner_deck = None
        self.stage = 0

    async def on_message(self, ctx):
        if self.stage == 0:
            await self.person.send(f"Welcome to {self.tournament.title}! Please check in by sending me both your Runner and Corp decklist in the form of a NetrunnerDB link.")
            self.stage += 1
        elif self.stage == 1:
            await self.person.send(f"Doing stuff")
        else:
            await self.person.send("This should not have happened... resetting!")
            self.corp_deck = None
            self.runner_deck = None
            self.stage = 0
            await self.on_message(ctx)

class Tournament(object):
    system_text = "Undefined system"

    def __init__(self, title, organizer_id, desc, format):
        self.id = uuid.uuid4()
        self.title = title
        self.organizer_id = organizer_id
        self.desc = desc
        self.format = format

        self.message_id = None
        self.participants = []
        self.approval = False
        self.running = False

        self.category_id = None
        self.lobby_id = None
        self.results_id = None
        self.check_in_id = None
        self.bot_commands_id = None

    @staticmethod
    def create_from_data(data):
        return Tournament(data['title'], data['organizer'], data['desc'], data['format'])

    def __str__(self):
        return "{0.title} ({0.id})".format(self)

class SSSTournament(Tournament):
    system_text = "Single Sided Swiss"

    def __init__(self, title, organizer_id, desc, format):
        super().__init__(title, organizer_id, desc, format)
        self.system = system.SSSSystem(3, None)
