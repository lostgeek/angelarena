class Player(object):
    def __init__(self, discord_member):
        self.member = discord_member
        self.corp = ''
        self.runner = ''

class Deck(object):
    pass

class TournamentHandler(object):
    def __init__(self):
        self.players = []
        self.rounds = []

    def populate(self, members):
        self.players = [Player(m) for m in members]

    def get_player(self, member):
        return next(filter(lambda p: p.member == member, self.players), None)

    def register_deck(self, member, corp, runner):
        p = self.get_player(member)
        p.corp = corp
        p.runner = runner

    def pair_round(self):
        pass

class SSSHandler(TournamentHandler):
    def __init__(self):
        self.players = []
