'''
V1 Algorithmic Pokerbot for Sneak Peek Hold'em.
Powered by O(1) Pre-Flop Lookups, Pot Odds Calculation, and EV Auction Bidding.
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
        
        # EXACT HEADS-UP PRE-FLOP EQUITIES (169 Hands - 100% complete)
        self.preflop_equities = {
            # POCKET PAIRS
            'AA': 0.853, 'KK': 0.824, 'QQ': 0.799, 'JJ': 0.775, 'TT': 0.751, 
            '99': 0.721, '88': 0.691, '77': 0.662, '66': 0.633, '55': 0.603, 
            '44': 0.570, '33': 0.537, '22': 0.503,

            # SUITED HANDS
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

            # OFFSUIT HANDS
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
        '''Called when a new round starts.'''
        pass

    def on_hand_end(self, game_info: GameInfo, current_state: PokerState) -> None:
        '''Called when a round ends.'''
        pass

    def _get_hand_key(self, hand) -> str:
        '''Translates ['Ah', 'Kd'] into 'AKo' for O(1) table lookup.'''
        rank_order = '23456789TJQKA'
        r1, r2 = hand[0][0], hand[1][0]
        s1, s2 = hand[0][1], hand[1][1]
        
        # Ensure higher card is first
        if rank_order.index(r1) < rank_order.index(r2):
            r1, r2 = r2, r1
            
        if r1 == r2: return r1 + r2
        elif s1 == s2: return r1 + r2 + 's'
        else: return r1 + r2 + 'o'

    def _estimate_equity(self, my_hand, board) -> float:
        '''O(1) fast heuristic evaluator. Returns estimated win prob (0.0 to 1.0).'''
        
        # 1. PRE-FLOP LOGIC (Instant Lookup)
        if not board:
            hand_key = self._get_hand_key(my_hand)
            # Default to 0.5 (coinflip) if hand isn't in dictionary yet
            return self.preflop_equities.get(hand_key, 0.500)

        # 2. POST-FLOP LOGIC (Heuristics)
        all_cards = my_hand + board
        ranks = [self.rank_map[c[0]] for c in all_cards]
        suits = [c[1] for c in all_cards]
        
        rank_counts = {r: ranks.count(r) for r in set(ranks)}
        suit_counts = {s: suits.count(s) for s in set(suits)}
        
        max_kind = max(rank_counts.values()) if rank_counts else 1
        max_suit = max(suit_counts.values()) if suit_counts else 1
        
        equity = 0.20 # Baseline postflop
        
        # Pairs & Sets
        if max_kind == 4: return 0.98  # Quads
        if max_kind == 3: equity = 0.75 # Set/Trips
        if max_kind == 2:
            hole_ranks = [self.rank_map[c[0]] for c in my_hand]
            if rank_counts[hole_ranks[0]] == 2 or rank_counts[hole_ranks[1]] == 2:
                equity = max(equity, 0.55) # We hit a pair
            else:
                equity = max(equity, 0.35) # Board is paired

        # Flushes
        if max_suit >= 5: return 0.90 # Made Flush
        if max_suit == 4 and len(board) < 5: 
            equity = max(equity, 0.45) # Flush draw

        return min(0.99, equity)

    def get_move(self, game_info: GameInfo, current_state: PokerState) -> ActionFold | ActionCall | ActionCheck | ActionRaise | ActionBid:
        '''The core quantitative engine.'''
        
        equity = self._estimate_equity(current_state.my_hand, current_state.board)
        
        # Adjust equity if we won the auction and saw a threatening card
        if current_state.opp_revealed_cards:
            for card in current_state.opp_revealed_cards:
                if card[0] in [c[0] for c in current_state.board]:
                    equity *= 0.8  
                    
        # ==========================================
        # AUCTION PHASE: The EV Delta Strategy
        # ==========================================
        if current_state.street == 'auction':
            pot = current_state.pot
            
            # Trash (< 45% win probability): Don't pay for info on a dead hand.
            if equity < 0.45:
                return ActionBid(0)
            
            # Marginal/Draws (45% - 60%): Info helps flip these. Bid 15-25% of pot.
            elif 0.45 <= equity < 0.60:
                bid_amt = int(pot * random.uniform(0.15, 0.25))
                return ActionBid(min(bid_amt, current_state.my_chips))
            
            # Strong/Monsters (> 60%): Trap bid. Inflate the pot for them to pay.
            else:
                trap_bid = int(pot * 0.30)
                return ActionBid(min(trap_bid, current_state.my_chips))

        # ==========================================
        # BETTING PHASE: Pot Odds & Kelly Criterion
        # ==========================================
        pot = current_state.pot
        cost = current_state.cost_to_call
        
        # Calculate Required Equity (Pot Odds)
        required_equity = cost / (pot + cost) if (pot + cost) > 0 else 0.0

        # ACTION: RAISE (Value Betting)
        # We raise if our hand is in the green (> 0.60) AND beats the pot odds
        if equity > 0.60 and equity > required_equity + 0.15:
            if current_state.can_act(ActionRaise):
                min_raise, max_raise = current_state.raise_bounds
                
                # Standard value bet: half the pot
                target_raise = int(pot * 0.5) + cost
                
                # Premium hands (> 0.70): Push harder (1.5x pot) to extract max value
                if equity > 0.70:
                    target_raise = int(pot * 1.5) + cost 
                    
                valid_raise = max(min_raise, min(target_raise, max_raise))
                return ActionRaise(valid_raise)

        # ACTION: CHECK / CALL (Defensive / Floating)
        if equity >= required_equity:
            if cost == 0 and current_state.can_act(ActionCheck):
                return ActionCheck()
            if current_state.can_act(ActionCall):
                return ActionCall()

        # ACTION: FOLD (Negative EV)
        # Always check instead of folding if it's free!
        if current_state.can_act(ActionCheck) and cost == 0:
            return ActionCheck()
            
        if current_state.can_act(ActionFold):
            return ActionFold()
            
        return ActionCheck() # Fallback

if __name__ == '__main__':
    run_bot(Player(), parse_args())
