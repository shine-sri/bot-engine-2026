'''
V2 "Fold Master" Pokerbot for Sneak Peek Hold'em.
Features: True Bayesian Updating, O(1) Bitwise Evaluator, Decoupled Auction, and Range Balancing.
'''
from pkbot.actions import ActionFold, ActionCall, ActionCheck, ActionRaise, ActionBid
from pkbot.states import GameInfo, PokerState
from pkbot.base import BaseBot
from pkbot.runner import parse_args, run_bot

import random

class Player(BaseBot):
    def __init__(self) -> None:
        '''Called exactly once when a new game starts.'''
        self.rank_map = {'2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9, 'T': 10, 'J': 11, 'Q': 12, 'K': 13, 'A': 14}
        self.bit_shifts = {'2': 0, '3': 1, '4': 2, '5': 3, '6': 4, '7': 5, '8': 6, '9': 7, 'T': 8, 'J': 9, 'Q': 10, 'K': 11, 'A': 12}

        # Tracking variables for Opponent Profiling
        self.hands_played = 0
        self.opp_vpip_count = 0
        self.opp_aggression_factor = 0.0

        # EXACT HEADS-UP PRE-FLOP EQUITIES (169 Hands)
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

    def on_hand_start(self, game_info: GameInfo, current_state: PokerState) -> None:
        self.hands_played += 1

    def on_hand_end(self, game_info: GameInfo, current_state: PokerState) -> None:
        pass

    def _get_hand_key(self, hand) -> str:
        rank_order = '23456789TJQKA'
        r1, r2 = hand[0][0], hand[1][0]
        s1, s2 = hand[0][1], hand[1][1]
        if rank_order.index(r1) < rank_order.index(r2):
            r1, r2 = r2, r1
        if r1 == r2: return r1 + r2
        elif s1 == s2: return r1 + r2 + 's'
        else: return r1 + r2 + 'o'

    def _estimate_equity(self, my_hand, board, street, opp_revealed) -> float:
        '''O(1) True Bayesian Bitwise Evaluator'''
        if not board:
            hand_key = self._get_hand_key(my_hand)
            return self.preflop_equities.get(hand_key, 0.500)

        master_mask = 0
        suit_masks = {'h': 0, 'd': 0, 'c': 0, 's': 0}
        rank_counts = {}
        all_cards = my_hand + board

        for card in all_cards:
            r, s = card[0], card[1]
            shift = self.bit_shifts[r]

            master_mask |= (1 << shift)
            suit_masks[s] |= (1 << shift)
            rank_counts[r] = rank_counts.get(r, 0) + 1

        max_suit_count = max(bin(mask).count('1') for mask in suit_masks.values())
        max_kind = max(rank_counts.values()) if rank_counts else 1

        is_straight = False
        straight_draw = False

        if (master_mask & (master_mask >> 1) & (master_mask >> 2) & (master_mask >> 3) & (master_mask >> 4)):
            is_straight = True
        elif (master_mask & 0x100F) == 0x100F: # Wheel straight
            is_straight = True
        elif (master_mask & (master_mask >> 1) & (master_mask >> 2) & (master_mask >> 3)):
            straight_draw = True

        is_boat = False
        if max_kind == 3:
            pairs = sum(1 for count in rank_counts.values() if count >= 2)
            if pairs >= 2:
                is_boat = True

        # Made Hands Base Equity
        if is_boat: equity = 0.95
        elif max_suit_count >= 5: equity = 0.90
        elif is_straight: equity = 0.85
        elif max_kind == 3: equity = 0.75
        else:
            equity = 0.20
            pairs = sum(1 for count in rank_counts.values() if count == 2)
            if pairs >= 2 and max_kind < 3:
                hole_r1, hole_r2 = my_hand[0][0], my_hand[1][0]
                if rank_counts.get(hole_r1) == 2 or rank_counts.get(hole_r2) == 2:
                    equity = 0.65
                else:
                    equity = 0.40
            elif max_kind == 2:
                hole_r1, hole_r2 = my_hand[0][0], my_hand[1][0]
                if rank_counts.get(hole_r1) == 2 or rank_counts.get(hole_r2) == 2:
                    equity = 0.55
                else:
                    equity = 0.35

        # Base Draw Outs
        outs = 0
        flush_suit = None
        if max_suit_count == 4:
            outs += 9
            for s, mask in suit_masks.items():
                if bin(mask).count('1') >= 4:
                    flush_suit = s
                    break
        if straight_draw:
            outs += 8

        # ==========================================
        # BAYESIAN UPDATING (Fixing Weakness #8)
        # ==========================================
        if opp_revealed:
            for card in opp_revealed:
                rev_r, rev_s = card[0], card[1]

                # If they paired the board, we cap our equity (unless we hold a monster)
                if rank_counts.get(rev_r, 0) > 0 and not (is_boat or max_suit_count >= 5 or is_straight):
                    equity = min(equity, 0.40)

                # If they hold a card of our flush suit, we literally have 1 less out!
                if flush_suit and rev_s == flush_suit:
                    outs = max(0, outs - 1)

        # Draw Calculations (Rule of 4 and 2 applied to Bayesian-adjusted outs)
        if not (is_boat or max_suit_count >= 5 or is_straight) and outs > 0:
            multiplier = 4.0 if street == 'flop' else 2.0
            draw_equity = min(0.50, (outs * multiplier) / 100.0)
            equity = max(equity, draw_equity)

        return equity

    def get_move(self, game_info: GameInfo, current_state: PokerState) -> ActionFold | ActionCall | ActionCheck | ActionRaise | ActionBid:
        street = current_state.street

        # Pass the revealed cards directly into the evaluator
        equity = self._estimate_equity(current_state.my_hand, current_state.board, street, current_state.opp_revealed_cards)

        # Track Aggression (VPIP)
        if current_state.opp_wager > 20:
            self.opp_vpip_count += 1
        if self.hands_played > 10:
            self.opp_aggression_factor = self.opp_vpip_count / self.hands_played

        # Positional Advantage
        if (street == 'preflop' and current_state.is_bb) or (street != 'preflop' and not current_state.is_bb):
            equity *= 1.05

        # Range Penalties
        if current_state.opp_wager > 20 and not current_state.board:
            equity *= 0.85

        # ==========================================
        # AUCTION PHASE: Decoupled Mixed Strategy
        # ==========================================
        if street == 'auction':
            pot = current_state.pot
            min_tax = random.randint(20, 60) # Information Tax (Never bid 0)

            if equity < 0.45:
                # 20% bluff bid to destroy their categorization logic
                if random.random() < 0.20:
                    bid_amt = int(pot * random.uniform(0.20, 0.40))
                else:
                    bid_amt = min_tax
                return ActionBid(min(bid_amt, current_state.my_chips))

            elif 0.45 <= equity < 0.70:
                # FIX: Ensure lower bound is always <= upper bound
                lower_bound = min_tax + 5
                upper_bound = max(lower_bound + 5, int(pot * 0.25))
                bid_amt = random.randint(lower_bound, upper_bound)
                return ActionBid(min(bid_amt, current_state.my_chips))

            else:
                # 30% of the time, disguise a monster with a tiny minimum tax bid
                if random.random() < 0.30:
                    bid_amt = min_tax
                else:
                    bid_amt = int(pot * random.uniform(0.15, 0.35))
                return ActionBid(min(bid_amt, current_state.my_chips))

        # ==========================================
        # BETTING PHASE: Exploitative Sizing
        # ==========================================
        pot = current_state.pot
        cost = current_state.cost_to_call
        required_equity = cost / (pot + cost) if (pot + cost) > 0 else 0.0

        # Adjust for Bully Opponents
        if self.opp_aggression_factor > 0.40:
            required_equity *= 0.80

        # The Bluff Catcher (Hero Call)
        if cost > pot and 0.55 <= equity < 0.70:
            if random.random() < 0.30 and current_state.can_act(ActionCall):
                return ActionCall()

        # The Balanced Bluff & Value Raise
        if current_state.can_act(ActionRaise):
            min_raise, max_raise = current_state.raise_bounds

            # Value Raise with Jitter
            if equity > 0.65 and equity > required_equity + 0.10:
                target_raise = int(pot * random.uniform(0.5, 1.2)) + cost
                if equity > 0.85 and random.random() < 0.5:
                    target_raise = int(pot * random.uniform(1.5, 2.5)) + cost
                valid_raise = max(min_raise, min(target_raise, max_raise))
                return ActionRaise(valid_raise)

            # Balanced Bluff (10% on pure trash)
            if equity < 0.40 and cost <= 20 and random.random() < 0.10:
                target_raise = int(pot * random.uniform(0.5, 0.8))
                valid_raise = max(min_raise, min(target_raise, max_raise))
                return ActionRaise(valid_raise)

        # Standard Calling / Floating
        if equity >= required_equity:
            if cost == 0 and current_state.can_act(ActionCheck): return ActionCheck()
            if current_state.can_act(ActionCall): return ActionCall()

        # Folding
        if current_state.can_act(ActionCheck) and cost == 0: return ActionCheck()
        if current_state.can_act(ActionFold): return ActionFold()
        return ActionCheck()

if __name__ == '__main__':
    run_bot(Player(), parse_args())