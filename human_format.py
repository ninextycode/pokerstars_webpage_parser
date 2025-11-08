class ToHumanFormat:
    def __init__(self, game_data):
        self.game_data = game_data
        self.attrs = game_data['data']['attributes']
        self.bb = self.attrs['bb']
        self.sb = self.attrs['sb']
        self.players = self.attrs['players']
        self.button = self.attrs['button']
        self.seats = self.attrs['seats']
        self.hero_seat = self._get_hero_seat()
        self.position_map = self._create_position_map()
    
    def to_bb_string(self, value):
        """Convert a chip/cash value to BB and format as string"""
        bb_value = value / self.bb
        return f"{bb_value:.2f}".rstrip('0').rstrip('.') + " bb"
        
    def _get_hero_seat(self):
        """Find the hero's seat number"""
        for player in self.players:
            if player.get('hero', False):
                return player['seat']
        return None
    
    def _create_position_map(self):
        """Map seat numbers to positions (SB, BB, UTG, MP, CO, BTN)"""
        seats_for_num_players = {
            2: ["BB", "BTN/SB"],
            3: ["SB", "BB", "BTN"],
            4: ["SB", "BB", "UTG", "BTN"],
            5: ["SB", "BB", "UTG", "CO", "BTN"],
            6: ["SB", "BB", "UTG", "MP", "CO", "BTN"]
        }
        num_players = len(self.players)
        
        seats_from_btn = seats_for_num_players[num_players]

        position_map = {}
        
        # Find positions relative to button
        for player in self.players:
            seat = player['seat']
            position_after_btn = (seat - self.button - 1) % (num_players)
            position_map[seat] = seats_from_btn[position_after_btn]
            if seat == self.hero_seat:
                position_map[seat] += "(me)"
        return position_map
    

    def _format_card(self, card):
        """Format a single card"""
        if card['rank'] == 'x':
            return 'xx'
        return f"{card['rank']}{card['suit']}"
    
    def _format_hand(self, cards):
        """Format a hand of cards"""
        return " ".join([self._format_card(c) for c in cards])
    
    def _get_stack_bb(self, seat):
        """Get stack size in BB for a seat"""
        for player in self.players:
            if player['seat'] == seat:
                return player['stack'] / self.bb
        return 0
    
    def _calculate_pot_after_actions(self, actions):
        """Calculate pot size from actions"""
        pot = 0
        for action in actions:
            if action['action'] in ['post', 'call', 'raise', 'bet']:
                if isinstance(action['value'], (int, float)):
                    pot += action['value']
                elif action['value'] == "SB":
                    pot += self.sb
                elif action['value'] == "BB":
                    pot += self.bb

            elif action['action'] == 'return_uncalled':
                pot -= action['value']
        return pot
    
    def _calculate_investment_for_seat(self, seat, streets_to_include):
        """Calculate total investment for a seat up to certain streets"""
        investment = 0
        streets = self.attrs.get('streets', {})
        
        for street_name in streets_to_include:
            if street_name in streets:
                actions = streets[street_name].get('actions', [])
                for action in actions:
                    if action['seat'] == seat and action['action'] in ['call', 'raise', 'bet', 'post']:
                        if isinstance(action.get('value'), (int, float)):
                            investment += action['value']
                    elif action['seat'] == seat and action['action'] == 'return_uncalled':
                        if isinstance(action.get('value'), (int, float)):
                            investment -= action['value']
        
        return investment
    
    def _has_player_folded(self, seat, streets_to_include):
        """Check if a player has folded in the streets completed so far"""
        streets = self.attrs.get('streets', {})
        
        for street_name in streets_to_include:
            if street_name in streets:
                actions = streets[street_name].get('actions', [])
                for action in actions:
                    if action['seat'] == seat and action['action'] == 'fold':
                        return True
        return False
    
    def _format_stacks_for_street(self, streets_completed):
        """Format stack information for a street"""
        lines = []
        lines.append("Stacks:")
        
        n_can_bet = 0
        for player in sorted(self.players, key=lambda p: p['seat']):
            seat = player['seat']
            position = self.position_map.get(seat, f"Seat{seat}")
            
            # Calculate investment up to this point
            investment = self._calculate_investment_for_seat(seat, streets_completed)
            remaining_bb = (player['stack'] - investment) / self.bb
            
            hero_marker = " (Hero)" if player.get('hero', False) else ""
            
            # Only show stack if player hasn't folded and has chips remaining
            if remaining_bb > 0 and not self._has_player_folded(seat, streets_completed):
                lines.append(f"  {position}: {remaining_bb:.1f}bb{hero_marker}")
                n_can_bet += 1
        if n_can_bet < 2:
            return []
        else:
            return lines
    
    def _format_action(self, action, street='preflop'):
        """Format a single action"""
        seat = action['seat']
        position = self.position_map.get(seat, f"Seat{seat}")
        action_type = action['action']
        
        if action_type in ['dealt', 'post']:
            return None
        
        # Mark if it's hero
        prefix = position
        
        if action_type == 'fold':
            return f"{prefix} fold"
        elif action_type == 'check':
            return f"{prefix} check"
        elif action_type == 'call':
            all_in = " allin" if action.get('all_in', False) else ""
            return f"{prefix}{all_in} call {self.to_bb_string(action['value'])}"
        elif action_type == 'bet':
            all_in = " allin" if action.get('all_in', False) else ""
            return f"{prefix}{all_in} bet {self.to_bb_string(action['value'])}"
        elif action_type == 'raise':
            all_in = " allin" if action.get('all_in', False) else ""
            return f"{prefix}{all_in} raise to {self.to_bb_string(action['value'])}"
        elif action_type == 'return_uncalled':
            return f"{prefix} got {self.to_bb_string(action['value'])} returned uncalled"
        
        return None
    
    def _get_board_cards_for_street(self, street_name, streets):
        """Get accumulated board cards up to and including the given street"""
        all_cards = []
        
        street_order = ['flop', 'turn', 'river']
        for s in street_order:
            if s not in streets:
                break
            if 'deal' in streets[s]:
                all_cards.extend(streets[s]['deal']['cards'])
            if s == street_name:
                break
        
        return all_cards
    
    def _calculate_pot_up_to_street(self, streets_to_include, streets):
        """Calculate total pot from actions up to (but not including) current street"""
        total_pot = 0
        for street_name in streets_to_include:
            if street_name in streets:
                actions = streets[street_name].get('actions', [])
                total_pot += self._calculate_pot_after_actions(actions)
        return total_pot
    
    def _format_postflop_street(self, street_name, street_data, previous_streets, streets):
        """Format a postflop street (flop, turn, or river)"""
        lines = []
        
        # Header
        lines.append(f"=== {street_name.capitalize()} ===")
        
        # Board cards
        if 'deal' in street_data:
            all_cards = self._get_board_cards_for_street(street_name, streets)
            lines.append(f"Board: {self._format_hand(all_cards)}")
        
        # Pot before current street actions
        pot = self._calculate_pot_up_to_street(previous_streets, streets)
        lines.append(f"Pot: {self.to_bb_string(pot)}")
        
        # Stacks
        stack_lines = self._format_stacks_for_street(previous_streets)
        lines.extend(stack_lines)
        
        lines.append("")
        
        # Actions
        for action in street_data.get('actions', []):
            formatted = self._format_action(action, street_name)
            if formatted:
                lines.append(formatted)
        
        if len(street_data.get('actions', [])) > 0:
            lines.append("")
        
        return lines

    def human_readable_lines(self):
        """Generate human-readable lines for the poker hand"""
        lines = []
        
        # Stacks in BB
        lines.append("=== Initial Stacks (in BB) ===")
        for player in sorted(self.players, key=lambda p: p['seat']):
            seat = player['seat']
            position = self.position_map.get(seat, f"Seat{seat}")
            hero_marker = " (Hero)" if player.get('hero', False) else ""
            lines.append(f"{position}: {self.to_bb_string(player['stack'])}{hero_marker}")
        
        lines.append("")
        
        # Cards
        lines.append("=== Cards ===")
        hero_cards = self.attrs.get('hero_cards', [])
        if hero_cards:
            lines.append(f"Hero: {self._format_hand(hero_cards)}")
        lines.append("")
        
        # Streets
        streets = self.attrs.get('streets', {})
        
        # Preflop
        if 'preflop' in streets:
            lines.append("=== Preflop ===")
            for action in streets['preflop']['actions']:
                formatted = self._format_action(action, 'preflop')
                if formatted:
                    lines.append(formatted)
            lines.append("")
        
        # Flop
        if 'flop' in streets:
            flop_lines = self._format_postflop_street('flop', streets['flop'], ['preflop'], streets)
            lines.extend(flop_lines)
        
        # Turn
        if 'turn' in streets:
            turn_lines = self._format_postflop_street('turn', streets['turn'], ['preflop', 'flop'], streets)
            lines.extend(turn_lines)
        
        # River
        if 'river' in streets:
            river_lines = self._format_postflop_street('river', streets['river'], ['preflop', 'flop', 'turn'], streets)
            lines.extend(river_lines)
        
        # Results
        results = self.attrs.get('results', {})
        if results:
            lines.append("=== Results ===")
            hero_profit = self.attrs.get('hero_profit', 0)
            lines.append(f"Hero profit: {self.to_bb_string(hero_profit)}")
            
            for seat_str, seat_result in results.get('seats', {}).items():
                seat = int(seat_str)
                position = self.position_map.get(seat, f"Seat{seat}")
                
                status_line = f"{position}: "

                if 'hand' in seat_result:
                    hand = self._format_hand(seat_result['hand'])
                    final_hand = seat_result.get('final_hand', ['muck'])[0]
                    status_line += f"{hand} ({final_hand})"
                else:
                    status_line += "didn't show cards"    
                lines.append(status_line)
                
                if 'collected' in seat_result:
                    for pot_dict in seat_result['collected']:
                        for pot_id, amount in pot_dict.items():
                            if pot_id == "main":
                                pot_name = "main pot"
                            else:
                                pot_name = "side pot " + pot_id.split("_")[-1]
                            lines.append(f"  Collected {self.to_bb_string(amount)} from {pot_name}")
        
        return '\n'.join(lines)