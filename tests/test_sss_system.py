import unittest

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

        bye = next(filter(lambda m: None in m, round), None)
        self.assertIsNotNone(bye,
                "Bye was given out")
        self.assertIsNot(bye.result, system.SSSResults.open,
                "Bye match is not marked as open")

if __name__ == '__main__':
    unittest.main()
