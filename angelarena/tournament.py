import logging

import uuid

from angelarena.wizard import *
from angelarena.handler import *

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
        self.handler = None

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


