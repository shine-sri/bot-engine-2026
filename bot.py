'''
V4 (Fold Master) — Pokerbot for Sneak Peek Hold'em.
'''

from pkbot.actions import ActionFold, ActionCall, ActionCheck, ActionRaise, ActionBid
from pkbot.states import GameInfo, PokerState
from pkbot.base import BaseBot
from pkbot.runner import parse_args, run_bot

import random
from bisect import bisect_right
from itertools import combinations, islice

# ── Module-level constants ─────────────────────────────────────────────────────
_RANK_MAP = {'2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7,
             '8': 8, '9': 9, 'T': 10, 'J': 11, 'Q': 12, 'K': 13, 'A': 14}
_SUIT_MAP = {'h': 0, 'd': 1, 'c': 2, 's': 3}

_CARD_RANKS = [i // 4 + 2 for i in range(52)]
_CARD_SUITS = [i % 4 for i in range(52)]

_FULL_DECK_INTS = tuple((_RANK_MAP[r] - 2) * 4 + _SUIT_MAP[s] for r in '23456789TJQKA' for s in 'hdcs')
_C2I = {r + s: (_RANK_MAP[r] - 2) * 4 + _SUIT_MAP[s] for r in '23456789TJQKA' for s in 'hdcs'}
_I2C = {v: k for k, v in _C2I.items()}

# ── OPT 5: Partial-state builder ───────────────────────────────────────────────
def _make_partial(cards):
    rc = [0] * 13; sc = [0] * 4; mask = 0; fmasks = [0, 0, 0, 0]
    for c in cards:
        r = _CARD_RANKS[c]; s = _CARD_SUITS[c]
        rc[r - 2] += 1; sc[s] += 1; mask |= (1 << r); fmasks[s] |= (1 << r)
    return rc, sc, mask, fmasks

# ── OPT 5b, 6 & 7: Allocation-Free Bitmask Evaluator ──────────────────────────
def _rank_fast(prc, psc, pmask, pfmasks, new_cards):
    rc = prc[:]; sc = psc[:]; mask = pmask; fmasks = pfmasks[:]

    for c in new_cards:
        r = _CARD_RANKS[c]; s = _CARD_SUITS[c]
        rc[r - 2] += 1; sc[s] += 1; mask |= (1 << r); fmasks[s] |= (1 << r)

    flush_suit = -1
    if sc[0] >= 5: flush_suit = 0
    elif sc[1] >= 5: flush_suit = 1
    elif sc[2] >= 5: flush_suit = 2
    elif sc[3] >= 5: flush_suit = 3

    ace_low = mask | (2 if mask & (1 << 14) else 0)

    if flush_suit >= 0:
        fm = fmasks[flush_suit]
        fm_al = fm | (2 if fm & (1 << 14) else 0)
        for h in range(14, 4, -1):
            if (fm_al >> (h - 4)) & 0x1F == 0x1F: return (8, h)

    quads = trips = pair1 = pair2 = -1
    for i in range(12, -1, -1):
        v = rc[i]; r = i + 2
        if v >= 4 and quads < 0: quads = r
        elif v == 3 and trips < 0: trips = r
        elif v >= 2:
            if pair1 < 0: pair1 = r
            elif pair2 < 0: pair2 = r

    if quads >= 0: return (7, quads, next(i + 2 for i in range(12, -1, -1) if rc[i] > 0 and i + 2 != quads))
    if trips >= 0 and pair1 >= 0: return (6, trips, pair1)

    if flush_suit >= 0:
        fm = fmasks[flush_suit]
        t1=t2=t3=t4=t5=-1
        for h in range(14, 1, -1):
            if fm & (1 << h):
                if t1 < 0: t1 = h
                elif t2 < 0: t2 = h
                elif t3 < 0: t3 = h
                elif t4 < 0: t4 = h
                elif t5 < 0: t5 = h; break
        return (5, t1, t2, t3, t4, t5)

    for h in range(14, 4, -1):
        if (ace_low >> (h - 4)) & 0x1F == 0x1F: return (4, h)

    if trips >= 0:
        k1 = k2 = -1
        for i in range(12, -1, -1):
            if rc[i] > 0 and (i + 2) != trips:
                if k1 < 0: k1 = i + 2
                else: k2 = i + 2; break
        return (3, trips, k1, k2)

    if pair1 >= 0 and pair2 >= 0:
        return (2, pair1, pair2, next(i + 2 for i in range(12, -1, -1) if rc[i] > 0 and i + 2 not in (pair1, pair2)))

    if pair1 >= 0:
        k1 = k2 = k3 = -1
        for i in range(12, -1, -1):
            if rc[i] > 0 and (i + 2) != pair1:
                if k1 < 0: k1 = i + 2
                elif k2 < 0: k2 = i + 2
                else: k3 = i + 2; break
        return (1, pair1, k1, k2, k3)

    t1=t2=t3=t4=t5=-1
    for i in range(12, -1, -1):
        if rc[i] > 0:
            if t1 < 0: t1 = i + 2
            elif t2 < 0: t2 = i + 2
            elif t3 < 0: t3 = i + 2
            elif t4 < 0: t4 = i + 2
            elif t5 < 0: t5 = i + 2; break
    return (0, t1, t2, t3, t4, t5)

class Player(BaseBot):
    def __init__(self) -> None:
        self.hands_played = 0

        # Adaptive Trackers
        self.opp_vpip_count = 0
        self.opp_vpip = 0.50
        self.opp_total_bets = 0
        self.opp_overbet_count = 0
        self.opp_overbet_freq = 0.15

        self.pre_auction_pot = 0
        self.auction_history_pct = []
        self.opp_avg_bid_pct = 0.10

        self.raised_this_hand = False
        self._river_cache: dict = {}

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
            '43s': 0.380, '42s': 0.363, '32s': 0.351,
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
            '43o': 0.344, '42o': 0.325, '32o': 0.312,
        }
        self.sorted_equities = sorted(self.preflop_equities.values())
        self._auction_upgrade_ev = self._precompute_auction_upgrade_ev()

    def _precompute_auction_upgrade_ev(self) -> dict:
        table = {}
        for key, eq in self.preflop_equities.items():
            peak, spread = 0.40, 0.18
            table[key] = 0.12 * max(0.0, 1.0 - ((eq - peak) / spread) ** 2)
        return table

    def on_hand_start(self, game_info: GameInfo, current_state: PokerState) -> None:
        self.hands_played += 1
        self.pre_auction_pot = 0
        self.raised_this_hand = False

    def on_hand_end(self, game_info: GameInfo, current_state: PokerState) -> None:
        pass

    def _get_hand_key(self, hand) -> str:
        r1, r2 = hand[0][0], hand[1][0]
        s1, s2 = hand[0][1], hand[1][1]
        if _RANK_MAP[r1] < _RANK_MAP[r2]: r1, r2 = r2, r1
        if r1 == r2: return r1 + r2
        elif s1 == s2: return r1 + r2 + 's'
        return r1 + r2 + 'o'

    def _get_hand_chunk(self, eq: float) -> float:
        return bisect_right(self.sorted_equities, eq) / len(self.sorted_equities)

    def _board_relative_bucket(self, opp_hand_i: tuple, board_i: tuple, board_partial, board_paired: bool, flush_possible: bool) -> str:
        if not board_i:
            eq = self.preflop_equities.get(self._get_hand_key((_I2C[opp_hand_i[0]], _I2C[opp_hand_i[1]])), 0.5)
            if eq >= 0.72: return 'nut'
            elif eq >= 0.58: return 'strong'
            elif eq >= 0.47: return 'medium'
            elif eq >= 0.38: return 'weak'
            return 'draw'

        rank_val = _rank_fast(*board_partial, opp_hand_i)[0]
        if rank_val >= 7: return 'nut'
        elif rank_val == 6: return 'nut'
        elif rank_val == 5: return 'strong' if flush_possible else 'nut'
        elif rank_val == 4: return 'strong'
        elif rank_val == 3: return 'nut' if not board_paired else 'strong'
        elif rank_val == 2: return 'medium'
        elif rank_val == 1: return 'weak'
        return 'draw'

    def _range_weight(self, opp_hand_i: tuple, board_i: tuple, board_partial, signal: str, board_paired: bool, flush_possible: bool) -> float:
        bucket = self._board_relative_bucket(opp_hand_i, board_i, board_partial, board_paired, flush_possible)
        if signal == 'polar': return 1.0 if bucket in ('nut', 'draw') else 0.08
        elif signal == 'linear': return 1.0 if bucket in ('nut', 'strong', 'medium') else 0.15
        else: return 1.0 if bucket in ('medium', 'weak', 'draw') else 0.35

    def _get_action_signal(self, bet_ratio: float) -> str:
        if bet_ratio == 0: return 'passive'
        if bet_ratio > 0.75: return 'polar'
        return 'linear'

    def _monte_carlo_rollout(self, my_hand_i: tuple, board_i: tuple, opp_revealed_i: tuple, signal: str, iterations: int) -> float:
        if not board_i:
            return self.preflop_equities.get(self._get_hand_key((_I2C[my_hand_i[0]], _I2C[my_hand_i[1]])), 0.500)

        dead = set(my_hand_i + board_i)
        if opp_revealed_i: dead.update(opp_revealed_i)
        deck = tuple(c for c in _FULL_DECK_INTS if c not in dead)
        dl = len(deck)
        cards_needed = 5 - len(board_i)

        my_partial = _make_partial(my_hand_i + board_i)
        board_partial = _make_partial(board_i)

        board_paired = any(c >= 2 for c in board_partial[0])
        flush_possible = any(c >= 3 for c in board_partial[1])

        rand_range = random.randrange
        rand_random = random.random

        weighted_wins = 0.0
        total_weight = 0.0
        weight_cache = {}

        for _ in range(iterations):
            if opp_revealed_i:
                oi2 = rand_range(dl)
                opp_i = (opp_revealed_i[0], deck[oi2])
                skip1 = oi2
                skip2 = -1
            else:
                oi1 = rand_range(dl)
                oi2 = rand_range(dl - 1)
                if oi2 >= oi1: oi2 += 1
                opp_i = (deck[oi1], deck[oi2])
                skip1, skip2 = (oi1, oi2) if oi1 < oi2 else (oi2, oi1)

            opp_key = opp_i if opp_i[0] < opp_i[1] else (opp_i[1], opp_i[0])
            if opp_key in weight_cache:
                weight = weight_cache[opp_key]
            else:
                weight = self._range_weight(opp_i, board_i, board_partial, signal, board_paired, flush_possible)
                weight_cache[opp_key] = weight

            if weight < 0.12 and rand_random() > 0.15: continue

            if cards_needed == 1:
                if skip2 == -1:
                    j = rand_range(dl - 1)
                    if j >= skip1: j += 1
                else:
                    j = rand_range(dl - 2)
                    if j >= skip1: j += 1
                    if j >= skip2: j += 1
                sim = (deck[j],)
            elif cards_needed == 2:
                if skip2 == -1:
                    j1 = rand_range(dl - 1); j2 = rand_range(dl - 2)
                    if j2 >= j1: j2 += 1
                    r1 = j1 + (1 if j1 >= skip1 else 0); r2 = j2 + (1 if j2 >= skip1 else 0)
                else:
                    j1 = rand_range(dl - 2); j2 = rand_range(dl - 3)
                    if j2 >= j1: j2 += 1
                    r1 = j1 + (1 if j1 >= skip1 else 0); r1 += (1 if r1 >= skip2 else 0)
                    r2 = j2 + (1 if j2 >= skip1 else 0); r2 += (1 if r2 >= skip2 else 0)
                sim = (deck[r1], deck[r2])

            mr = _rank_fast(*my_partial, sim)
            or_ = _rank_fast(*board_partial, opp_i + sim)

            if mr > or_: weighted_wins += weight
            elif mr == or_: weighted_wins += weight * 0.5
            total_weight += weight

        return weighted_wins / total_weight if total_weight > 0 else 0.5

    def _exact_river_enumeration(self, my_hand_i: tuple, board_i: tuple, opp_revealed_i: tuple, signal: str, step: int) -> float:
        cache_key = (my_hand_i[0], my_hand_i[1], board_i[0], board_i[1], board_i[2], board_i[3], board_i[4], signal, step)
        if cache_key in self._river_cache: return self._river_cache[cache_key]

        dead = set(my_hand_i + board_i)
        if opp_revealed_i: dead.update(opp_revealed_i)
        deck = tuple(c for c in _FULL_DECK_INTS if c not in dead)

        if opp_revealed_i: combos = ((opp_revealed_i[0], c) for c in deck)
        else: combos = islice(combinations(deck, 2), 0, None, step)

        my_partial = _make_partial(my_hand_i + board_i)
        my_rank = _rank_fast(*my_partial, ())
        board_partial = _make_partial(board_i)

        board_paired = any(c >= 2 for c in board_partial[0])
        flush_possible = any(c >= 3 for c in board_partial[1])

        weighted_wins = 0.0
        total_weight = 0.0
        weight_cache = {}

        for opp_hand_i in combos:
            opp_key = opp_hand_i if opp_hand_i[0] < opp_hand_i[1] else (opp_hand_i[1], opp_hand_i[0])
            if opp_key in weight_cache:
                weight = weight_cache[opp_key]
            else:
                weight = self._range_weight(opp_hand_i, board_i, board_partial, signal, board_paired, flush_possible)
                weight_cache[opp_key] = weight

            opp_rank = _rank_fast(*board_partial, opp_hand_i)
            if my_rank > opp_rank: weighted_wins += weight
            elif my_rank == opp_rank: weighted_wins += weight * 0.5
            total_weight += weight

        result = weighted_wins / total_weight if total_weight > 0 else 0.5
        self._river_cache[cache_key] = result
        return result

    def get_move(self, game_info: GameInfo, current_state: PokerState) -> ActionFold | ActionCall | ActionCheck | ActionRaise | ActionBid:
        street = current_state.street
        pot = current_state.pot
        cost = current_state.cost_to_call
        my_chips = current_state.my_chips

        my_hand_i = tuple(_C2I[c] for c in current_state.my_hand)
        board_i = tuple(_C2I[c] for c in current_state.board)
        opp_rev_i = tuple(_C2I[c] for c in current_state.opp_revealed_cards) if current_state.opp_revealed_cards else ()

        # --- Dynamic Tracking ---
        if street == 'preflop' and current_state.opp_wager > 20:
            self.opp_vpip_count += 1
        if self.hands_played > 10:
            self.opp_vpip = self.opp_vpip_count / self.hands_played

        bet_ratio = cost / pot if pot > 0 else 0
        if cost > 0 and street not in ('preflop', 'auction'):
            self.opp_total_bets += 1
            if bet_ratio > 0.75: self.opp_overbet_count += 1
            if self.opp_total_bets > 10: self.opp_overbet_freq = self.opp_overbet_count / self.opp_total_bets

        if self.pre_auction_pot > 0 and street != 'auction':
            paid = pot - self.pre_auction_pot
            if paid > 0:
                self.auction_history_pct.append(paid / self.pre_auction_pot)
                recent = self.auction_history_pct[-15:]
                self.opp_avg_bid_pct = sum(recent) / len(recent)
            self.pre_auction_pot = 0

        signal = self._get_action_signal(bet_ratio)

        # ── COMPUTE ALLOCATION ──
        leverage = pot / max(1, my_chips + pot)
        if leverage > 0.40 or pot > 200:
            mc_iters = 250; river_step = 2
        elif leverage > 0.15 or pot > 80:
            mc_iters = 120; river_step = 5
        else:
            mc_iters = 60; river_step = 10

        if street == 'river':
            equity = self._exact_river_enumeration(my_hand_i, board_i, opp_rev_i, signal, river_step)
        else:
            equity = self._monte_carlo_rollout(my_hand_i, board_i, opp_rev_i, signal, mc_iters)

        required_equity = cost / (pot + cost) if (pot + cost) > 0 else 0.0
        buffer = 0.06 if street == 'flop' else 0.04 if street == 'turn' else 0.06
        safe_equity = equity - buffer

        if bet_ratio > 0.90:
            overbet_penalty = max(1.0, 1.15 - (self.opp_overbet_freq * 0.25))
            required_equity *= overbet_penalty

        hand_chunk = self._get_hand_chunk(equity)

        # ── AUCTION EDGE ──
        if street == 'auction':
            self.pre_auction_pot = pot
            hand_key = self._get_hand_key(current_state.my_hand)
            upgrade_ev = self._auction_upgrade_ev.get(hand_key, 0.06)
            distance = abs(equity - 0.50)
            ev_scaler = max(0.3, 1.0 - distance * 2.0)
            expected_eq_after = min(0.88, equity + upgrade_ev * ev_scaler)
            ev_gain = (expected_eq_after - equity) * (pot * 2.0)

            base_pct = max(0.10, min(0.18, self.opp_avg_bid_pct + 0.02))
            market_bid = pot * base_pct

            # Boosted EV multiplier for prime information zone (Fix C)
            if 0.48 <= equity <= 0.55: ev_multiplier = 0.90
            elif 0.45 <= equity <= 0.60: ev_multiplier = 0.85
            else: ev_multiplier = 0.70

            bid = min(ev_gain * ev_multiplier, market_bid) * random.uniform(0.88, 1.12)
            bid = min(bid, pot * 0.20, 0.20 * my_chips)
            if ev_gain < pot * 0.025 or equity < 0.28: bid = 0
            return ActionBid(int(max(0, bid)))

        # ── RELAXED FOLD THRESHOLD ──
        dynamic_fold_base = 0.32 + (0.50 - self.opp_vpip) * 0.15
        fold_threshold = dynamic_fold_base + random.uniform(-0.04, 0.04)

        # Only hard-fold against genuine aggression, allowing math to handle medium bets (Fix #4)
        if hand_chunk < fold_threshold and bet_ratio > 0.65:
            return ActionFold()

        # ── APEX PREDATOR RAISING LOGIC ──
        if current_state.can_act(ActionRaise):
            min_raise, max_raise = current_state.raise_bounds
            raise_eq_threshold = 0.65 + (0.50 - self.opp_vpip) * 0.10

            # EXPLOSIVE EV: River Overbet with Nuts (Option B)
            if street == 'river' and equity > 0.82 and self.opp_vpip > 0.50 and pot > 120:
                target = int(pot * 1.20) + cost
                valid_raise = max(min_raise, min(target, max_raise))
                self.raised_this_hand = True
                return ActionRaise(valid_raise)

            # INCREASED VALUE AGGRESSION (Fix #2: Buffer reduced to 0.10)
            if safe_equity > raise_eq_threshold and safe_equity > required_equity + 0.10:
                scale = 0.50 + (safe_equity - raise_eq_threshold) * 2.0
                target = int(pot * random.uniform(scale - 0.1, scale + 0.1)) + cost
                valid_raise = max(min_raise, min(target, max_raise))
                self.raised_this_hand = True
                return ActionRaise(valid_raise)

            # STANDARD NUTS RAISE
            if equity > 0.70 and cost == 0:
                target = min(max_raise, int(pot * 0.75) + cost)
                valid_raise = max(min_raise, target)
                self.raised_this_hand = True
                return ActionRaise(valid_raise)

            # DELAYED TURN PRESSURE (Fix #2: Strengthened to require both absolute and relative strength)
            if street == 'turn' and cost == 0 and signal == 'passive' and pot > 40 and equity > 0.55 and hand_chunk > 0.65:
                target = int(pot * random.uniform(0.55, 0.65))
                valid_raise = max(min_raise, min(target, max_raise))
                self.raised_this_hand = True
                return ActionRaise(valid_raise)

            # TIGHTENED RIVER THIN VALUE (Fix #1: Narrowed to 0.64 - 0.74)
            if street == 'river' and cost == 0 and 0.64 <= equity <= 0.74 and self.opp_vpip > 0.55:
                target = int(pot * 0.50)
                valid_raise = max(min_raise, min(target, max_raise))
                self.raised_this_hand = True
                return ActionRaise(valid_raise)

            # CONTROLLED RIVER BLUFFING (Fix #3: Allowed against capped lines via signal != 'polar')
            if street == 'river' and cost == 0 and 0.30 <= equity <= 0.48 and signal != 'polar':
                board_partial = _make_partial(board_i)
                board_paired = any(c >= 2 for c in board_partial[0])
                flush_possible = any(c >= 3 for c in board_partial[1])

                # 7% frequency on scary boards
                if (board_paired or flush_possible) and random.random() < 0.07:
                    target = int(pot * random.uniform(0.60, 0.75))
                    valid_raise = max(min_raise, min(target, max_raise))
                    self.raised_this_hand = True
                    return ActionRaise(valid_raise)

        # ── DEFENSE ──
        if safe_equity >= required_equity:
            if cost == 0 and current_state.can_act(ActionCheck): return ActionCheck()
            if current_state.can_act(ActionCall): return ActionCall()

        if current_state.can_act(ActionCheck) and cost == 0: return ActionCheck()
        if current_state.can_act(ActionFold): return ActionFold()

        return ActionCheck()

if __name__ == '__main__':
    run_bot(Player(), parse_args())
