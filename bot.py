'''
V3 "Fold Master" Pokerbot for Sneak Peek Hold'em.
Features: Rational-Capped Auction, Polarized MC Rollouts, Board Texture Rejection, and Capped Range Exploitation.
'''
from pkbot.actions import ActionFold, ActionCall, ActionCheck, ActionRaise, ActionBid
from pkbot.states import GameInfo, PokerState
from pkbot.base import BaseBot
from pkbot.runner import parse_args, run_bot

import random

class Player(BaseBot):
    def __init__(self) -> None:
        self.rank_map = {'2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9, 'T': 10, 'J': 11, 'Q': 12, 'K': 13, 'A': 14}
        self.full_deck = [r+s for r in '23456789TJQKA' for s in 'hdcs']

        # Engine Trackers
        self.hands_played = 0
        self.opp_vpip_count = 0
        self.opp_vpip = 0.50

        # Dynamic Auction Market Trackers
        self.pre_auction_pot = 0
        self.auction_history_pct = []
        self.opp_avg_bid_pct = 0.10 # Assume a rational 10% pot baseline for the field

        # EXACT HEADS-UP PRE-FLOP EQUITIES (O(1) Lookup)
        self.preflop_equities = {
            'AA': 0.853, 'KK': 0.824, 'QQ': 0.799, 'JJ': 0.775, 'TT': 0.751,
            '99': 0.721, '88': 0.691, '77': 0.662, '66': 0.633, '55': 0.603,
            '44': 0.570, '33': 0.537, '22': 0.503,
            'AKs': 0.670, 'AQs': 0.661, 'AJs': 0.654, 'ATs': 0.647, 'A9s': 0.630,
            'A8s': 0.621, 'A7s': 0.611, 'A6s': 0.600, 'A5s': 0.599, 'A4s': 0.589,
            'A3s': 0.580, 'A2s': 0.570,
            'KQs': 0.634, 'KJs': 0.626, 'KTs': 0.619, 'K9s': 0.600, 'K8s': 0.585,
            'K7s': 0.578, 'K6s': 0.568, 'K5s': 0.558, 'K4s': 0.547, 'K3s': 0.538,
            'K2s': 0.529,
            'QJs': 0.603, 'QTs': 0.595, 'Q9s': 0.579, 'Q8s': 0.562, 'Q7s': 0.545,
            'Q6s': 0.538, 'Q5s': 0.529, 'Q4s': 0.517, 'Q3s': 0.507, 'Q2s': 0.499,
            'JTs': 0.575, 'J9s': 0.558, 'J8s': 0.542, 'J7s': 0.524, 'J6s': 0.508,
            'J5s': 0.500, 'J4s': 0.490, 'J3s': 0.479, 'J2s': 0.471,
            'T9s': 0.543, 'T8s': 0.526, 'T7s': 0.510, 'T6s': 0.492, 'T5s': 0.472,
            'T4s': 0.464, 'T3s': 0.455, 'T2s': 0.447,
            '98s': 0.511, '97s': 0.495, '96s': 0.477, '95s': 0.459, '94s': 0.438,
            '93s': 0.432, '92s': 0.423,
            '87s': 0.482, '86s': 0.465, '85s': 0.448, '84s': 0.427, '83s': 0.408,
            '82s': 0.403,
            '76s': 0.457, '75s': 0.438, '74s': 0.418, '73s': 0.400, '72s': 0.381,
            '65s': 0.432, '64s': 0.414, '63s': 0.394, '62s': 0.375,
            '54s': 0.411, '53s': 0.393, '52s': 0.375,
            '43s': 0.380, '42s': 0.363,
            '32s': 0.351,
            'AKo': 0.654, 'AQo': 0.645, 'AJo': 0.636, 'ATo': 0.629, 'A9o': 0.609,
            'A8o': 0.601, 'A7o': 0.591, 'A6o': 0.578, 'A5o': 0.577, 'A4o': 0.564,
            'A3o': 0.556, 'A2o': 0.546,
            'KQo': 0.614, 'KJo': 0.606, 'KTo': 0.599, 'K9o': 0.580, 'K8o': 0.563,
            'K7o': 0.554, 'K6o': 0.543, 'K5o': 0.533, 'K4o': 0.521, 'K3o': 0.512,
            'K2o': 0.502,
            'QJo': 0.582, 'QTo': 0.574, 'Q9o': 0.555, 'Q8o': 0.538, 'Q7o': 0.519,
            'Q6o': 0.511, 'Q5o': 0.502, 'Q4o': 0.490, 'Q3o': 0.479, 'Q2o': 0.470,
            'JTo': 0.554, 'J9o': 0.534, 'J8o': 0.517, 'J7o': 0.499, 'J6o': 0.479,
            'J5o': 0.471, 'J4o': 0.461, 'J3o': 0.450, 'J2o': 0.440,
            'T9o': 0.517, 'T8o': 0.500, 'T7o': 0.482, 'T6o': 0.463, 'T5o': 0.442,
            'T4o': 0.434, 'T3o': 0.424, 'T2o': 0.415,
            '98o': 0.484, '97o': 0.467, '96o': 0.449, '95o': 0.429, '94o': 0.407,
            '93o': 0.399, '92o': 0.389,
            '87o': 0.455, '86o': 0.436, '85o': 0.417, '84o': 0.396, '83o': 0.375,
            '82o': 0.368,
            '76o': 0.427, '75o': 0.408, '74o': 0.386, '73o': 0.366, '72o': 0.346,
            '65o': 0.401, '64o': 0.380, '63o': 0.359, '62o': 0.340,
            '54o': 0.379, '53o': 0.358, '52o': 0.339,
            '43o': 0.344, '42o': 0.325,
            '32o': 0.312
        }

        # Build percentiles for range filtering
        sorted_hands = sorted(self.preflop_equities.values(), reverse=True)
        self.equity_percentiles = {
            p / 100.0: sorted_hands[int((len(sorted_hands)-1) * (p / 100.0))]
            for p in range(5, 105, 5)
        }

    def on_hand_start(self, game_info: GameInfo, current_state: PokerState) -> None:
        self.hands_played += 1
        self.pre_auction_pot = 0

    def on_hand_end(self, game_info: GameInfo, current_state: PokerState) -> None:
        pass

    def _get_hand_key(self, hand) -> str:
        r1, r2 = hand[0][0], hand[1][0]
        s1, s2 = hand[0][1], hand[1][1]
        if self.rank_map[r1] < self.rank_map[r2]: r1, r2 = r2, r1
        if r1 == r2: return r1 + r2
        elif s1 == s2: return r1 + r2 + 's'
        return r1 + r2 + 'o'

    def _get_hand_rank(self, cards) -> tuple:
        '''O(1) Exact Tuple Evaluator for Showdown Logic'''
        ranks = sorted([self.rank_map[c[0]] for c in cards], reverse=True)
        suits = [c[1] for c in cards]

        suit_counts = {}
        for s in suits: suit_counts[s] = suit_counts.get(s, 0) + 1
        flush_suit = next((s for s, c in suit_counts.items() if c >= 5), None)

        flush_cards = []
        if flush_suit:
            flush_cards = sorted([self.rank_map[c[0]] for c in cards if c[1] == flush_suit], reverse=True)

        rank_counts = {}
        for r in ranks: rank_counts[r] = rank_counts.get(r, 0) + 1
        freq_sorted = sorted(rank_counts.items(), key=lambda x: (x[1], x[0]), reverse=True)

        def get_straight_high(r_list):
            unique_r = sorted(list(set(r_list)), reverse=True)
            if 14 in unique_r: unique_r.append(1)
            consec = 1
            for i in range(len(unique_r) - 1):
                if unique_r[i] == unique_r[i+1] + 1:
                    consec += 1
                    if consec == 5: return unique_r[i-3]
                else: consec = 1
            return None

        if flush_cards:
            sf_high = get_straight_high(flush_cards)
            if sf_high: return (8, sf_high)
        if freq_sorted[0][1] == 4:
            kicker = max([r for r in ranks if r != freq_sorted[0][0]])
            return (7, freq_sorted[0][0], kicker)
        if freq_sorted[0][1] == 3 and len(freq_sorted) > 1 and freq_sorted[1][1] >= 2:
            return (6, freq_sorted[0][0], freq_sorted[1][0])
        if flush_cards: return tuple([5] + flush_cards[:5])

        st_high = get_straight_high(ranks)
        if st_high: return (4, st_high)

        if freq_sorted[0][1] == 3:
            kickers = sorted([r for r in ranks if r != freq_sorted[0][0]], reverse=True)[:2]
            return tuple([3, freq_sorted[0][0]] + kickers)
        if freq_sorted[0][1] == 2 and len(freq_sorted) > 1 and freq_sorted[1][1] >= 2:
            kicker = max([r for r in ranks if r != freq_sorted[0][0] and r != freq_sorted[1][0]])
            return (2, freq_sorted[0][0], freq_sorted[1][0], kicker)
        if freq_sorted[0][1] == 2:
            kickers = sorted([r for r in ranks if r != freq_sorted[0][0]], reverse=True)[:3]
            return tuple([1, freq_sorted[0][0]] + kickers)
        return tuple([0] + ranks[:5])

    def _monte_carlo_rollout(self, my_hand, board, opp_vpip, opp_revealed, bet_ratio, is_capped) -> float:
        '''Range-Weighted, Board-Aware, and Action-Polarized Monte Carlo'''
        if not board: return self.preflop_equities.get(self._get_hand_key(my_hand), 0.500)

        # Base Threshold
        vpip_percentile = max(5, 5 * round(min(max(int(opp_vpip * 100), 5), 100) / 5))
        vpip_eq = self.equity_percentiles[vpip_percentile / 100.0]

        # Polarization Dynamics
        is_polarized = bet_ratio > 0.75
        top_15_eq = self.equity_percentiles[0.15]
        bottom_30_eq = self.equity_percentiles[0.70]
        top_25_eq = self.equity_percentiles[0.25]

        # Board Texture (Bayesian Rejection Proxy)
        board_suits = [c[1] for c in board]
        suit_counts = {s: board_suits.count(s) for s in set(board_suits)}
        flush_threat_suit = next((s for s, count in suit_counts.items() if count >= 3), None)

        dead_cards = set(my_hand + board)
        if opp_revealed: dead_cards.update(opp_revealed)
        available_deck = [c for c in self.full_deck if c not in dead_cards]

        wins, samples = 0, 0
        target_samples = 250

        for _ in range(target_samples * 5):
            if samples >= target_samples: break

            if opp_revealed: opp_hand = [opp_revealed[0], random.choice(available_deck)]
            else: opp_hand = random.sample(available_deck, 2)

            opp_key = self._get_hand_key(opp_hand)
            preflop_eq = self.preflop_equities.get(opp_key, 0.5)

            # Action-Conditioned Range Filtering
            if is_polarized:
                # If they overbet, they represent the nuts OR air. Reject medium hands.
                if not (preflop_eq >= top_15_eq or preflop_eq <= bottom_30_eq): continue
            elif is_capped:
                # If they checked/bet tiny, they don't have the nuts. Reject top hands.
                if preflop_eq >= top_25_eq: continue
            else:
                if preflop_eq < vpip_eq: continue

            # Board-Aware Weighting
            if flush_threat_suit:
                has_threat_suit = opp_hand[0][1] == flush_threat_suit or opp_hand[1][1] == flush_threat_suit
                if not has_threat_suit and random.random() < 0.40: continue

            cards_needed = 5 - len(board)
            if cards_needed > 0:
                temp_deck = [c for c in available_deck if c not in opp_hand]
                sim_board = board + random.sample(temp_deck, cards_needed)
            else: sim_board = board

            my_rank = self._get_hand_rank(my_hand + sim_board)
            opp_rank = self._get_hand_rank(opp_hand + sim_board)

            if my_rank > opp_rank: wins += 1
            elif my_rank == opp_rank: wins += 0.5
            samples += 1

        if samples == 0: return 0.5
        return wins / samples

    def get_move(self, game_info: GameInfo, current_state: PokerState) -> ActionFold | ActionCall | ActionCheck | ActionRaise | ActionBid:
        street = current_state.street
        pot = current_state.pot
        cost = current_state.cost_to_call
        my_chips = current_state.my_chips

        # --------------------------------------------------
        # TRACKING: VPIP and Rational Market Pricing
        # --------------------------------------------------
        if street == 'preflop' and current_state.opp_wager > 20:
            self.opp_vpip_count += 1
        if self.hands_played > 10:
            self.opp_vpip = self.opp_vpip_count / self.hands_played

        # Track the actual cost of information paid into the pot
        if self.pre_auction_pot > 0 and street != 'auction':
            paid_into_pot = pot - self.pre_auction_pot
            if paid_into_pot > 0:
                pct_paid = paid_into_pot / self.pre_auction_pot
                self.auction_history_pct.append(pct_paid)
                recent = self.auction_history_pct[-15:]
                self.opp_avg_bid_pct = sum(recent) / len(recent)
            self.pre_auction_pot = 0

        bet_ratio = cost / pot if pot > 0 else 0

        is_capped = False
        if street in ['turn', 'river'] and bet_ratio < 0.25:
            is_capped = True

        equity = self._monte_carlo_rollout(
            current_state.my_hand,
            current_state.board,
            self.opp_vpip,
            current_state.opp_revealed_cards,
            bet_ratio,
            is_capped
        )

        required_equity = cost / (pot + cost) if (pot + cost) > 0 else 0.0

        # Dynamic Confidence Buffer
        buffer = 0.06 if street == 'flop' else 0.04 if street == 'turn' else 0.02
        safe_equity = equity - buffer

        # --------------------------------------------------
        # V17 AUCTION: Rational Field GTO Logic
        # --------------------------------------------------
        if street == 'auction':
            self.pre_auction_pot = pot

            # Start at a 10% baseline, flex up to 18% if opponent fights rationally.
            base_pct = max(0.10, min(0.18, self.opp_avg_bid_pct + 0.02))

            # Flattened Quadratic Uncertainty: Info is most valuable at 0.50 equity.
            distance = abs(equity - 0.50) / 0.50
            uncertainty = max(0.0, 1.0 - (distance ** 2))

            # Leverage Multiplier
            leverage = min(1.2, (my_chips / pot) / 10.0) if pot > 0 else 1.0

            # Formulate Bids
            bid = pot * base_pct * uncertainty * leverage
            bid *= random.uniform(0.9, 1.1)

            # THE RATIONALITY CAP: Never pay more than 20% of the pot for 1 card.
            # This crushes maniacs by letting them overpay, while dominating GTO bots in the 10-18% range.
            bid = min(bid, pot * 0.20)
            bid = min(bid, 0.20 * my_chips) # Anti-suicide safety

            return ActionBid(int(bid))

        # --------------------------------------------------
        # V17 BETTING PHASE: Exploitative Action
        # --------------------------------------------------
        in_position = (street != 'preflop' and not current_state.is_bb)

        if current_state.can_act(ActionRaise):
            min_raise, max_raise = current_state.raise_bounds

            # Value Raise
            if safe_equity > 0.65 and safe_equity > required_equity + 0.10:
                scale = 0.5 + (safe_equity - 0.65) * 2.0
                target_raise = int(pot * random.uniform(scale - 0.1, scale + 0.1)) + cost
                valid_raise = max(min_raise, min(target_raise, max_raise))
                return ActionRaise(valid_raise)

            # CAPPED RANGE ATTACK (Fold Equity Injection)
            if is_capped and in_position and cost == 0:
                fold_freq_est = 0.60
                test_bet = int(pot * 0.6)
                ev_bluff = (fold_freq_est * pot) + ((1 - fold_freq_est) * (equity * (pot + test_bet*2) - test_bet))

                # If EV is positive, FIRE THE BLUFF exactly on the margin.
                if ev_bluff > 0 and equity < 0.50:
                    valid_raise = max(min_raise, min(test_bet, max_raise))
                    return ActionRaise(valid_raise)

        # Defense
        if safe_equity >= required_equity:
            if cost == 0 and current_state.can_act(ActionCheck): return ActionCheck()
            if current_state.can_act(ActionCall): return ActionCall()

        if current_state.can_act(ActionCheck) and cost == 0: return ActionCheck()
        if current_state.can_act(ActionFold): return ActionFold()
        return ActionCheck()

if __name__ == '__main__':
    run_bot(Player(), parse_args())
