import unittest
import random

from angelarena import system

class TestSSSSystem(unittest.TestCase):
    def test_pairing_first_round_even(self):
        """
        Basic test for pairing first round with an odd number of players
        """

        sys = system.SSSSystem(3,None)
        for i in range(10):
            sys.add_new_player(None) # Passing None as discord member

        self.assertEqual(len(sys.rounds), 0,
                "No rounds paired yet")
        self.assertEqual(len(sys.players), 10,
                "11 players added")
        self.assertEqual(len(sys.dropped), 0,
                "No players dropped yet")

        sys.pair_new_round()
        self.assertEqual(len(sys.rounds), 1,
                "One round paired")

        round = sys.rounds[0]
        self.assertEqual(len(round), 5,
                "Five matches paired")
        for player in sys.players:
            self.assertEqual(sum(1 for match in round if player in match), 1,
                    "Found only one match per player")

    def test_pairing_first_round_odd(self):
        """
        Basic test for pairing first round with an odd number of players
        """

        sys = system.SSSSystem(3,None)
        for i in range(11):
            sys.add_new_player(None) # Passing None as discord member

        self.assertEqual(len(sys.rounds), 0,
                "No rounds paired yet")
        self.assertEqual(len(sys.players), 11,
                "11 players added")
        self.assertEqual(len(sys.dropped), 0,
                "No players dropped yet")

        sys.pair_new_round()
        self.assertEqual(len(sys.rounds), 1,
                "One round paired")

        round = sys.rounds[0]
        self.assertEqual(len(round), 6,
                "Six matches paired")
        for player in sys.players:
            self.assertEqual(sum(1 for match in round if player in match), 1,
                    "Found only one match per player")

        bye = next(filter(lambda m: sys.bye_player in m, round), None)
        self.assertIsNotNone(bye,
                "Bye was given out")
        self.assertIsNot(bye.result, system.SSSResults.open,
                "Bye match is not marked as open")

    def test_full_small_tournament_elimination(self):
        """
        Simulate small elimination tournament
        """

        sys = system.SSSSystem(3,None)
        for i in range(15):
            sys.add_new_player(None) # Passing None as discord member

        for i in range(100):
            sys.pair_new_round()
            for m in sys.rounds[-1]:
                if m.result == system.SSSResults.open:
                    ran = random.randint(0, 99)
                    if ran < 48:
                        m.result = system.SSSResults.win_corp
                    elif ran < 96:
                        m.result = system.SSSResults.win_runner
                    else:
                        m.result = system.SSSResults.draw
            sys.finish_round()
            if len(sys.players) <= 1:
                break

        self.assertTrue(len(sys.rounds) < 100,
                "Tournament ended naturally")

        self.assertEqual(len(sys.players), 1,
                "Tournament ended with a winner")

    @unittest.skip("Takes long time")
    def test_full_huge_tournament(self):
        """
        Simulate huge elimination tournament
        """

        sys = system.SSSSystem(3,None)
        for i in range(512):
            sys.add_new_player(None) # Passing None as discord member

        for i in range(30):
            sys.pair_new_round()
            for m in sys.rounds[-1]:
                if m.result == system.SSSResults.open:
                    ran = random.randint(0, 99)
                    if ran < 48:
                        m.result = system.SSSResults.win_corp
                    elif ran < 96:
                        m.result = system.SSSResults.win_runner
                    else:
                        m.result = system.SSSResults.draw
            sys.finish_round()

            if len(sys.players) <= 1:
                break

            for p in sys.players:
                if random.randint(0, 200) < i:
                    sys.drop_player(p)

            print(f"{i:02d}: p: {len(sys.players)} e: {len(sys.eliminated)} d: {len(sys.dropped)}")

        self.assertTrue(len(sys.rounds) < 30,
                "Tournament ended naturally")

        self.assertEqual(len(sys.players), 1,
                "Tournament ended with a winner")

if __name__ == '__main__':
    unittest.main()
