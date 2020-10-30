class Wizard(object):
    async def on_message(self, ctx):
        print("Wizard: ", ctx.channel)

class DMWizard(Wizard):
    async def on_message(self, ctx):
        print("DMWizard: ", ctx.channel)
