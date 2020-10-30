import uuid
import itertools
import random
from enum import Enum

class Player(object):
    def __init__(self, member):
        self.id = uuid.uuid4()
        self.member = member
        self.matches = []

    def __str__(self):
        return f"<..{str(self.id)[-3:]}>"

class SSSPlayer(Player):
    def __init__(self, member):
        super().__init__(member)
        self.matches = []
        self.corp_games = 0
        self.runner_games = 0
        self.losses = 0

    def __str__(self):
        return f"<..{str(self.id)[-3:]}: {len(self.matches)-self.losses}-{self.losses}>"

class Match(object):
    pass

class SSSMatch(Match):
    def __init__(self, p1, p2, round, reason=None):
        self.result = SSSResults.open
        self.round = round
        self.bye = False
        self.reason = reason

        # bye
        if not p2:
            self.bye = True
            if p1.corp_games > p1.runner_games:
                self.runner = p1
                self.corp = None
                self.result = SSSResults.win_runner
            elif p1.corp_games < p1.runner_games:
                self.runner = None
                self.corp = p1
                self.result = SSSResults.win_corp
            else:
                self.reason = "Side was randomized, because of balanced record"
                if bool(random.getrandbits(1)):
                    self.runner = p1
                    self.corp = None
                    self.result = SSSResults.win_runner
                else:
                    self.runner = None
                    self.corp = p1
                    self.result = SSSResults.win_corp

        # normal match
        else:
            if p1.corp_games > p2.corp_games:
                self.runner = p1
                self.corp = p2
            elif p1.corp_games < p2.corp_games:
                self.runner = p2
                self.corp = p1
            else: # both players played the same number of corp games
                self.reason = "Sides were randomized, because both players had same record"
                if bool(random.getrandbits(1)):
                    self.runner = p1
                    self.corp = p2
                else:
                    self.runner = p2
                    self.corp = p1

    def __contains__(self, p):
        return p == self.corp or p == self.runner

    def __str__(self):
        if not self.corp:
            cname = "<BYE>"
        else:
            cname = str(self.corp)

        if not self.runner:
            rname = "<BYE>"
        else:
            rname = str(self.runner)

        if self.result == SSSResults.win_corp:
            result = "c"
        elif self.result == SSSResults.win_runner:
            result = "r"
        elif self.result == SSSResults.draw:
            result = "d"
        elif self.result == SSSResults.open:
            result = "_"

        reason = ""
        if self.reason:
            reason = f"rea: {reason}"

        return f"[c:{cname} r:{rname} res:{result}{reason}]"

class SSSResults(Enum):
    open = 0
    win_corp = 1
    win_runner = 2
    draw = 3

class System(object):
    pass

class SSSSystem(System):
    def __init__(self, max_losses = 3, max_rounds = None):
        self.players = []
        self.dropped = []
        self.rounds = []
        self.max_losses = max_losses
        self.max_rounds = max_rounds

    def add_new_player(self, member):
        p = SSSPlayer(member)
        self.players.append(p)

    def pair_new_round(self):
        groups = itertools.groupby(self.players, key = lambda p: p.losses)
        unpaired = {}
        for k, g in groups:
            unpaired[k] = list(g)

        # remove players with max number of losses
        if self.max_losses in unpaired:
            del unpaired[self.max_losses]

        round = []
        round_number = len(self.rounds)+1
        losses = 0 # current loss level to be paired
        while unpaired:
            # no players on loss level
            if not losses in unpaired:
                losses += 1
                continue

            # grab first player
            p1 = unpaired[losses].pop()
            if not unpaired[losses]:
                del unpaired[losses]

            # no players left to pair: give out a bye
            if not unpaired:
                match = SSSMatch(p1, None, round_number, reason="No players left to match")
                p2 = None

            # search second player
            else:
                match_losses = losses
                match_i = 0
                p2 = None
                while not p2:
                    # no other players found with this number of losses, trying to pair down
                    if not match_losses in unpaired:
                        match_losses += 1
                    else:
                        p2 = unpaired[match_losses][match_i]

                        #XXX: room for checks

                        unpaired[match_losses].pop(match_i)
                        if not unpaired[match_losses]:
                            del unpaired[match_losses]
                match = SSSMatch(p1, p2, round_number)
            round.append(match)
            p1.matches.append(match)
            if p2:
                p2.matches.append(match)


        self.rounds.append(round)
