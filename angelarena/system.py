import uuid
import itertools
import random
from enum import Enum
import networkx as nx
import numpy as np
import pandas as pd

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
        self.side_balance = 0 # pos = more corp than runner
        self.score = 0
        self.byes = 0

    def __str__(self):
        return f"<..{str(self.id)[-3:]}: {self.score}>"

    def __repr__(self):
        return self.__str__()

class SSSByePlayer(SSSPlayer):
    def __init__(self):
        super().__init__(None)

    def __getattribute__(self, attr):
        if attr == "score":
            return -1
        elif attr == "side_balance":
            return 0
        else:
            return super().__getattribute__(attr)

    def __str__(self):
        return f"<BYE>"

    def __repr__(self):
        return self.__str__()

class Match(object):
    pass

class SSSMatch(Match):
    def __init__(self, corp, runner, round_number):
        self.corp = corp
        self.runner = runner
        self.round_number = round_number

        self.result = SSSResults.open

    def opponent(self, p):
        if p == self.corp:
            return self.runner
        elif p == self.runner:
            return self.corp
        else:
            raise Exception('Player not in match')

    def __contains__(self, p):
        return p == self.corp or p == self.runner

    def __str__(self):
        if self.result == SSSResults.win_corp:
            result = "c"
        elif self.result == SSSResults.win_runner:
            result = "r"
        elif self.result == SSSResults.draw:
            result = "d"
        elif self.result == SSSResults.bye:
            result = "b"
        elif self.result == SSSResults.open:
            result = "_"

        return f"[c:{str(self.corp)} r:{str(self.runner)} res:{result}]"

    def __repr__(self):
        return self.__str__()

class SSSResults(Enum):
    open = 0
    win_corp = 1
    win_runner = 2
    draw = 3
    bye = 4

class System(object):
    pass

class SSSSystem(System):
    bye_player = SSSByePlayer()

    def __init__(self, max_losses = 3, max_rounds = None):
        self.players = []
        self.eliminated = []
        self.dropped = []
        self.rounds = []
        self.max_losses = max_losses
        self.max_rounds = max_rounds

        self.score_factor = 1
        self.repair_penalty = 10000

    def add_new_player(self, member):
        p = SSSPlayer(member)
        self.players.append(p)

    def make_score_penalty_array(self):
        df = np.array([[player.score for player in self.players]])
        df = abs(df - df.T)*self.score_factor
        return df

    def make_side_penalty_array(self):
        df = np.array([[player.side_balance for player in self.players]])
        same_bias = ((df * df.T)> 0)
        np.fill_diagonal(same_bias,0)
        min_bias = np.minimum(abs(df), abs(df.T))
        return (8**(min_bias))*same_bias

    def make_repair_penalty_array(self):
        penalty = np.zeros((len(self.players), len(self.players)))
        for i in range(len(self.players)):
            for j in range(i, len(self.players)):
                p1 = self.players[i]
                p2 = self.players[j]
                penalty[j][i] = len(list(filter(lambda match: p2 in match, p1.matches)))
        penalty = penalty + penalty.T - np.diag(np.diag(penalty)) # fill other triangle
        np.fill_diagonal(penalty, 0)
        penalty *= self.repair_penalty
        return penalty

    def make_bye_bonus_array(self):
        df = np.array([[player.byes for player in self.players]])
        bonus = abs(df - df.T)+1
        return bonus

    def make_pairings_matrix(self):
        pairing_matrix = 20000 \
                - self.make_score_penalty_array() \
                - self.make_side_penalty_array() \
                - self.make_repair_penalty_array()
        pairing_matrix *= self.make_bye_bonus_array()
        pairing_matrix += np.random.randint(0,10,size=(len(self.players), len(self.players)))
        pairing_matrix = pd.DataFrame(pairing_matrix, \
                index = [player for player in self.players], \
                columns = [player for player in self.players])
        return pairing_matrix

    def pair_new_round(self):
        round = []
        round_number = len(self.rounds)+1

        if self.bye_player in self.players:
            self.players.remove(self.bye_player)

        if len(self.players) % 2 == 1:
            self.players.append(self.bye_player)

        pairing_matrix = self.make_pairings_matrix()
        pairing_graph = nx.convert_matrix.from_pandas_adjacency(pairing_matrix)
        pairings = nx.max_weight_matching(pairing_graph,maxcardinality=True)

        for p in pairings:
            p0corps = (p[1].side_balance-p[0].side_balance > 0)
            if p[1].side_balance-p[0].side_balance == 0:
                p0corps = bool(random.getrandbits(1))

            if p0corps:
                corp = p[0]
                runner = p[1]
            else:
                corp = p[1]
                runner = p[0]

            match = SSSMatch(corp, runner, round_number)
            round.append(match)
            corp.side_balance += 1
            corp.matches.append(match)
            runner.side_balance -= 1
            runner.matches.append(match)

            if self.bye_player in match:
                match.result = SSSResults.bye

        self.rounds.append(round)

    def finish_round(self):
        round = self.rounds[-1]

        if next(filter(lambda match: match.result == SSSResults.open, round), None):
            raise Exception("Tried to finish round with open results.")

        if self.bye_player in self.players:
            self.players.remove(self.bye_player)

        for match in round:
            if match.result == SSSResults.win_corp:
                match.corp.score += 1
            elif match.result == SSSResults.win_runner:
                match.runner.score += 1
            elif match.result == SSSResults.bye:
                player = match.opponent(self.bye_player)
                player.byes += 1
                player.score += 1

        for player in self.players:
            losses = len(self.rounds)-player.score
            if losses > self.max_losses:
                self.players.remove(player)
                self.eliminated.append(player)

    def drop_player(self, player):
        if not player in self.players:
            raise Exception("Player not in system")

        self.players.remove(player)
        self.dropped.append(player)
