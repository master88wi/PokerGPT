import discord
from discord import ButtonStyle, Interaction
from discord.ui import InputText, View
from bot.card_display import get_cards
from bot.gpt_player import GPTPlayer
from config.log_config import logger
from db.db_utils import DatabaseManager
from game.poker import PokerGameManager


class DiscordPokerManager:
    def __init__(self, ctx, pokerGame: PokerGameManager, db_manager: DatabaseManager, small_cards: bool, timeout: float,
                 model_name: str = "gpt-3.5-turbo", memory: bool = False):
        self.ctx = ctx
        self.pokerGame = pokerGame
        self.db_manager = db_manager
        self.small_cards = small_cards
        self.timeout = timeout
        self.model_name = model_name
        self.memory = memory

        db_manager.initialize_game(pokerGame.small_blind, pokerGame.big_blind, pokerGame.starting_stack)

    async def play_round(self):
        self.pokerGame.new_round()
        self.gpt_action = GPTPlayer(self.db_manager, model_name=self.model_name, memory=self.memory)
        self.db_manager.initialize_hand(self.pokerGame.return_player_hand_str(0), self.pokerGame.return_player_hand_str(1), self.pokerGame.return_player_stack(0))
        logger.info(f"{self.ctx.author.name} - Starting a new round.")
        logger.info(f"{self.ctx.author.name} - Player has {self.pokerGame.return_player_stack(0)} chips, PokerGPT has {self.pokerGame.return_player_stack(1)} chips.")
        await self.pre_flop()

    async def pre_flop(self):
        logger.info(f"{self.ctx.author.name} - Pre-flop")
        self.pokerGame.round = "pre-flop"
        self.pokerGame.reset_betting()
        await self.ctx.send("**Your Cards:**")
        await self.ctx.send(get_cards(self.pokerGame.return_player_hand(0), self.small_cards))
        logger.info(f"{self.ctx.author.name} - Player has {self.pokerGame.return_player_hand_str(0)}, PokerGPT has {self.pokerGame.return_player_hand_str(1)}")
        if self.pokerGame.button == 0:
            # Player can't cover small blind
            if self.pokerGame.return_player_stack(0) < self.pokerGame.small_blind:
                logger.info(f"{self.ctx.author.name} - Player can't cover small blind and is all-in for {self.pokerGame.return_player_stack(0)} chips.")
                await self.ctx.send(f"{self.pokerGame.players[0].player_name} can not cover small blind and is __All-in for {self.pokerGame.return_player_stack(0)} chips.__")
                self.pokerGame.player_raise(0, self.pokerGame.return_player_stack(0))
                self.pokerGame.player_call(1)
                return

            # PokerGPT can't cover big blind
            if self.pokerGame.return_player_stack(1) < self.pokerGame.big_blind:
                await self.ctx.send(f"{self.pokerGame.players[0].player_name} places small blind of {self.pokerGame.small_blind} chips.")
                await self.ctx.send(f"PokerGPT is __All-in for {self.pokerGame.return_player_stack(1)} chips.__")
                self.pokerGame.player_raise(0, self.pokerGame.small_blind)
                self.pokerGame.player_raise(1, self.pokerGame.return_player_stack(1))
                view = self.allInCallView(self)
                await self.ctx.send(f"What do you want to do? You are in for {self.pokerGame.players[0].round_pot_commitment} chips, it costs {self.pokerGame.players[1].round_pot_commitment - self.pokerGame.players[0].round_pot_commitment} more to call.", view=view)
                return

            # Player can cover small blind but not big blind
            if self.pokerGame.return_player_stack(0) < self.pokerGame.big_blind:
                await self.ctx.send(f"PokerGPT places big blind of {self.pokerGame.big_blind} chips, and {self.pokerGame.players[0].player_name} places small blind of {self.pokerGame.small_blind} chips.")
                self.pokerGame.player_raise(0, self.pokerGame.small_blind)
                self.pokerGame.player_raise(1, self.pokerGame.big_blind)
                view = self.allInCallView(self)
                await self.ctx.send(f"You have {self.pokerGame.return_player_stack(0)} chips.")
                await self.ctx.send(f"What do you want to do? You are in for {self.pokerGame.players[0].round_pot_commitment}", view=view)
                return

            # Regular scenario, both players can cover blinds
            await self.ctx.send(f"PokerGPT places big blind of {self.pokerGame.big_blind} chips, and {self.pokerGame.players[0].player_name} places small blind of {self.pokerGame.small_blind} chips.")
            self.pokerGame.player_raise(0, self.pokerGame.small_blind)
            self.pokerGame.player_raise(1, self.pokerGame.big_blind)

            view = self.callView(self)
            await self.ctx.send(f"You have {self.pokerGame.return_player_stack(0)} chips.")
            await self.ctx.send(f"What do you want to do? You are in for {self.pokerGame.players[0].round_pot_commitment}", view=view)

        elif self.pokerGame.button == 1:
            # Check if ChatGPT can cover the small blind
            if self.pokerGame.return_player_stack(1) < self.pokerGame.small_blind:
                await self.ctx.send(f"PokerGPT can not cover the small blind and is __All-in for {self.pokerGame.return_player_stack(1)} chips.__")
                self.pokerGame.player_raise(1, self.pokerGame.return_player_stack(1))
                self.pokerGame.player_call(0)
                return

            # Check if the player can cover the big blind
            if self.pokerGame.return_player_stack(0) < self.pokerGame.big_blind:
                await self.ctx.send(f"PokerGPT places the small blind of {self.pokerGame.small_blind} chips.")
                await self.ctx.send(f"{self.pokerGame.players[0].player_name} is __All-in for {self.pokerGame.return_player_stack(0)} chips.__")
                self.pokerGame.player_raise(1, self.pokerGame.small_blind)
                self.pokerGame.player_raise(0, self.pokerGame.return_player_stack(0))
                self.pokerGame.player_call(1)
                await self.ctx.send("PokerGPT __Calls.__")
                return

            # Check if ChatGPT can cover the big blind but not the player
            if self.pokerGame.return_player_stack(1) < self.pokerGame.big_blind:
                await self.ctx.send(f"{self.pokerGame.players[0].player_name} places the big blind of {self.pokerGame.big_blind} chips, and ChatGPT places the small blind of {self.pokerGame.small_blind} chips.")
                self.pokerGame.player_raise(1, self.pokerGame.small_blind)
                self.pokerGame.player_raise(0, self.pokerGame.big_blind)
                await self.ctx.send(f"{self.pokerGame.players[0].player_name} is __All-in for {self.pokerGame.return_player_stack(0) + self.pokerGame.players[0].round_pot_commitment} chips.__")
                view = self.allInCallView(self)
                await self.ctx.send(f"What do you want to do? You are in for {self.pokerGame.players[0].round_pot_commitment} chips, and it will cost you {self.pokerGame.players[1].round_pot_commitment - self.pokerGame.players[0].round_pot_commitment} more chips to call.", view=view)
                return

            # Regular scenario, both players can cover blinds
            await self.ctx.send(f"{self.pokerGame.players[0].player_name} places big blind of {self.pokerGame.big_blind} chips, and ChatGPT places small blind of {self.pokerGame.small_blind} chips.")
            self.pokerGame.player_raise(1, self.pokerGame.small_blind)
            self.pokerGame.player_raise(0, self.pokerGame.big_blind)

            action, raise_amount = self.gpt_action.pre_flop_small_blind(self.pokerGame)
            if action == "Call":
                logger.info(f"{self.ctx.author.name} - PokerGPT Calls.")
                await self.ctx.send("PokerGPT __Calls.__")
                self.pokerGame.player_call(1)
                await self.next_action()
            elif action == "All-in":
                await self.pokerGPT_all_in()
            elif action == "Fold":
                await self.pokerGPT_fold()
            elif action == "Raise":
                await self.pokerGPT_raise(raise_amount)
            else:
                logger.warning(f"{self.ctx.author.name} - Error move given: {action}, {raise_amount}, doing Default move of: Fold")
                await self.pokerGPT_fold()

    async def deal_community_cards(self, round_name: str):
        # Set the current round and deal the community cards
        self.pokerGame.round = round_name
        self.pokerGame.reset_betting()
        if round_name == "flop":
            self.pokerGame.deal_board(3)
        elif round_name == "turn":
            self.pokerGame.deal_board(4)
        elif round_name == "river":
            self.pokerGame.deal_board(5)

        # Announce the community cards
        logger.info(f"{self.ctx.author.name} - {round_name.capitalize()} {self.pokerGame.return_community_cards()}")
        await self.ctx.send(f"**Community Cards ({round_name.capitalize()}):**")
        await self.ctx.send(get_cards(self.pokerGame.board, self.small_cards))

        # Announce the current pot and player stacks
        await self.ctx.send(f"**Main pot:** {self.pokerGame.current_pot} chips.")
        await self.ctx.send(f"**{self.pokerGame.players[0].player_name} stack:** {self.pokerGame.return_player_stack(0)} chips.")
        await self.ctx.send(f"**PokerGPT stack:** {self.pokerGame.return_player_stack(1)} chips.")

        # Determine who is first to act and prompt them for their move
        if self.pokerGame.button == 0:
            await self.pokerGPT_acts_first()
        elif self.pokerGame.button == 1:
            await self.user_acts_first()

    async def showdown(self):
        await self.ctx.send("***Showdown!!***")
        self.pokerGame.round = "showdown"
        
        # Deal and Display the community cards
        self.pokerGame.deal_board(5)
        await self.ctx.send("**Community Cards:**")
        await self.ctx.send(get_cards(self.pokerGame.board, self.small_cards))
        logger.info(f"{self.ctx.author.name} - Showdown {self.pokerGame.return_community_cards()}")
        
        # Evaluate each player's hand
        self.pokerGame.evaluate_hands()

        # Display each player's hand and hand rank
        for player in self.pokerGame.players:
            await self.ctx.send(f"{player.player_name} has:")
            await self.ctx.send(get_cards(player.return_hand(), self.small_cards))

            await self.ctx.send(f"**{player.hand_rank}**")
            await self.ctx.send(get_cards(player.hand_played, self.small_cards))
            logger.info(f"{self.ctx.author.name} - {player.player_name} has {player.hand_rank}")

        # Determine the winner(s) and handle the pot
        winner = self.pokerGame.determine_winner()
        if isinstance(winner, list):
            # Split pot
            logger.info(f"{self.ctx.author.name} - Split pot")
            await self.ctx.send("**Split pot!!!**")
            split_pot = self.pokerGame.current_pot // 2
            self.pokerGame.player_win(winner)
            await self.ctx.send(f"{self.pokerGame.players[0].player_name} wins {split_pot} chips and has {self.pokerGame.return_player_stack(0)} chips.")
            await self.ctx.send(f"PokerGPT wins {split_pot} chips and has {self.pokerGame.return_player_stack(1)} chips.")
            
        else:
            # Single winner
            pot = self.pokerGame.current_pot
            self.pokerGame.player_win(winner)
            logger.info(f"{self.ctx.author.name} - {winner.player_name} wins {pot} chips")
            await self.ctx.send(f"{winner.player_name} wins **{pot} chips** and has {winner.stack} chips.")

        # Check if either player is out of chips
        self.db_manager.update_community_cards(self.pokerGame.return_community_cards())
        self.db_manager.end_hand(self.pokerGame.return_player_stack(0), "showdown")
        embed = self.result_embed()
        if self.pokerGame.return_player_stack(0) == 0:
            await self.ctx.send(f"{self.pokerGame.players[1].player_name} wins the game! {self.pokerGame.players[0].player_name} is out of chips.", embeds=[embed])
            self.db_manager.end_game(self.pokerGame.return_player_stack(0))
        elif self.pokerGame.return_player_stack(1) == 0:
            await self.ctx.send(f"{self.pokerGame.players[0].player_name} wins the game! {self.pokerGame.players[1].player_name} is out of chips.", embeds=[embed])
            self.db_manager.end_game(self.pokerGame.return_player_stack(0))
        else:
            # Prompt to play another round
            await self.ctx.respond("Play another round?")
            await self.ctx.send("", view=self.newRoundView(self))

    async def user_acts_first(self):
        view = self.checkView(self)
        await self.ctx.send(f"What do you want to do?", view=view)

    async def pokerGPT_acts_first(self):
        action, raise_amount = self.gpt_action.first_to_act(self.pokerGame)

        if action == "Check":
            logger.info(f"{self.ctx.author.name} - PokerGPT Checks.")
            await self.ctx.send("PokerGPT __Checks.__")
            await self.next_action()
        elif action == "All-in":
            await self.pokerGPT_all_in()
        elif action == "Raise":
            await self.pokerGPT_raise(raise_amount)
        else:
            logger.warning(f"{self.ctx.author.name} - Error move given: {action}, {raise_amount}, doing Default move of: Check")
            await self.ctx.send("PokerGPT __Checks.__")
            await self.next_action()

    async def user_raise(self, amount: int):
        logger.info(f"{self.ctx.author.name} - User raises to {amount} chips")
        # Raise the player's bet
        self.pokerGame.player_raise(0, amount)

        # Get GPT's move and handle it
        action, raise_amount = self.gpt_action.player_raise(self.pokerGame)

        if action == "Call":
            logger.info(f"{self.ctx.author.name} - PokerGPT Calls.")
            await self.ctx.send("PokerGPT __Calls Raise.__")
            self.pokerGame.player_call(1)
            await self.next_action()
        elif action == "Fold":
            await self.pokerGPT_fold()
        elif action == "All-in":
            await self.pokerGPT_all_in()
        elif action == "Raise":
            await self.pokerGPT_raise(raise_amount)
        else:
            logger.warning(f"{self.ctx.author.name} - Error move given: {action}, {raise_amount}, doing Default move of: Fold")
            await self.pokerGPT_fold()

    async def pokerGPT_raise(self, amount: int):
        logger.info(f"{self.ctx.author.name} - PokerGPT raises to {amount} chips")
        # Raise the bet and announce it
        await self.ctx.send(f"PokerGPT __Raises to {amount} chips.__")
        self.pokerGame.player_raise(1, amount)
        await self.ctx.send(f"**Main pot:** {self.pokerGame.current_pot} chips")

        # Check if the player needs to go all-in
        if (self.pokerGame.return_player_stack(0) + self.pokerGame.players[0].round_pot_commitment <= self.pokerGame.current_bet):
            await self.ctx.send(f"PokerGPT puts you __All-In for {self.pokerGame.return_player_stack(0) + self.pokerGame.players[0].round_pot_commitment} chips.__")
            view = self.allInCallView(self)
        else:
            view = self.callView(self)

        # Prompt the player for their action
        await self.ctx.send(f"What do you want to do? You are in for {self.pokerGame.players[0].round_pot_commitment} chips, it costs __{self.pokerGame.current_bet - self.pokerGame.players[0].round_pot_commitment} more to call.__", view=view)

    async def user_all_in(self):
        logger.info(f"{self.ctx.author.name} - User goes All-in")
        self.pokerGame.player_all_in_raise(0)
        action, raise_amount = self.gpt_action.player_all_in(self.pokerGame)

        if action == "Call":
            logger.info(f"{self.ctx.author.name} - PokerGPT Calls All-in.")
            await self.ctx.send(f"PokerGPT __Calls All-in.__")
            self.pokerGame.player_call(1)
            await self.showdown()
        elif action == "Fold":
            await self.pokerGPT_fold()
        else:
            logger.warning(f"{self.ctx.author.name} - Error move given: {action}, {raise_amount}, doing Default move of: Fold")
            await self.pokerGPT_fold()

    async def pokerGPT_all_in(self):
        logger.info(f"{self.ctx.author.name} - PokerGPT goes All-in")
        await self.ctx.send(f"PokerGPT is __All-in for {self.pokerGame.return_player_stack(1) + self.pokerGame.players[1].round_pot_commitment} chips.__")
        self.pokerGame.player_all_in_raise(1)
        view = self.allInCallView(self)
        await self.ctx.send(f"What do you want to do? You are in for {self.pokerGame.players[0].round_pot_commitment} chips, it is {self.pokerGame.current_bet - self.pokerGame.players[0].round_pot_commitment} more to call", view=view)

    async def user_fold(self):
        logger.info(f"{self.ctx.author.name} - User Folds.")
        await self.ctx.send(f"PokerGPT wins __{self.pokerGame.current_pot} chips.__")
        self.pokerGame.player_win(1)
        await self.ctx.send(f"You have {self.pokerGame.return_player_stack(0)} chips.")
        await self.ctx.send(f"PokerGPT has {self.pokerGame.return_player_stack(1)} chips.")
        await self.new_round_prompt()

    async def pokerGPT_fold(self):
        logger.info(f"{self.ctx.author.name} - PokerGPT Folds.")
        await self.ctx.send("PokerGPT Folds.")
        await self.ctx.send(f"You win __{self.pokerGame.current_pot} chips.__")
        self.pokerGame.player_win(0)
        await self.ctx.send(f"You have {self.pokerGame.return_player_stack(0)} chips.")
        await self.ctx.send(f"PokerGPT has {self.pokerGame.return_player_stack(1)} chips.")
        await self.new_round_prompt()

    async def new_round_prompt(self):
        self.db_manager.update_community_cards(self.pokerGame.return_community_cards())
        self.db_manager.end_hand(self.pokerGame.return_player_stack(0), self.pokerGame.round)
        await self.ctx.respond("Play another round?")
        await self.ctx.send("", view=self.newRoundView(self))

    async def move_to_next_betting_round(self):
        self.pokerGame.current_action = self.pokerGame.button
        if self.pokerGame.round == "pre-flop":
            await self.deal_community_cards("flop")
        elif self.pokerGame.round == "flop":
            await self.deal_community_cards("turn")
        elif self.pokerGame.round == "turn":
            await self.deal_community_cards("river")
        elif self.pokerGame.round == "river":
            await self.showdown()

    async def next_action(self):
        self.pokerGame.current_action = (self.pokerGame.current_action + 1) % 2
        if self.pokerGame.round == "pre-flop":
            if self.pokerGame.current_bet > self.pokerGame.big_blind:
                await self.move_to_next_betting_round()
                return
            if self.pokerGame.button == 0:
                action, raise_amount = self.gpt_action.pre_flop_big_blind(self.pokerGame)
                
                if action == "Check":
                    logger.info(f"{self.ctx.author.name} - PokerGPT Checks.")
                    await self.ctx.send("PokerGPT __Checks.__")
                    await self.move_to_next_betting_round()
                    return
                elif action == "All-in":
                    await self.pokerGPT_all_in()
                    return
                elif action == "Raise":
                    await self.pokerGPT_raise(raise_amount)
                    return
                else:
                    logger.warning(f"{self.ctx.author.name} - Error move given: {action}, {raise_amount}, doing Default move of: Check")
                    await self.ctx.send("PokerGPT __Checks.__")
                    await self.move_to_next_betting_round()
                    return

            if self.pokerGame.button == 1:
                if self.pokerGame.current_action == 0:
                    view = self.checkView(self)
                    await self.ctx.send(f"What do you want to do?", view=view)
                    return
                elif self.pokerGame.current_action == 1:
                    await self.move_to_next_betting_round()
        else:
            if self.pokerGame.current_bet > 0:
                await self.move_to_next_betting_round()
                return
            if self.pokerGame.button == 0:
                if self.pokerGame.current_action == 1:
                    view = self.checkView(self)
                    await self.ctx.send(f"What do you want to do?", view=view)
                    return
                elif self.pokerGame.current_action == 0:
                    await self.move_to_next_betting_round()
            elif self.pokerGame.button == 1:
                action, raise_amount = self.gpt_action.player_check(self.pokerGame)

                if action == "Check":
                    logger.info(f"{self.ctx.author.name} - PokerGPT Checks.")
                    await self.ctx.send("PokerGPT __Checks.__")
                    await self.move_to_next_betting_round()
                    return
                elif action == "All-in":
                    await self.pokerGPT_all_in()
                    return
                elif action == "Raise":
                    await self.pokerGPT_raise(raise_amount)
                    return
                else:
                    logger.warning(f"{self.ctx.author.name} - Error move given: {action}, {raise_amount}, doing Default move of: Check")
                    await self.ctx.send("PokerGPT __Checks.__")
                    await self.move_to_next_betting_round()
                    return

    def result_embed(self):
        logger.info(f"{self.ctx.author.name} - Game Results Player Stack: {self.pokerGame.return_player_stack(0)} chips, PokerGPT Stack: {self.pokerGame.return_player_stack(1)} chips.")
        embed = discord.Embed(title="Results")
        embed.add_field(name="PokerGPT", value=str(self.pokerGame.return_player_stack(1)))
        embed.add_field(name=self.ctx.author.name, value=str(self.pokerGame.return_player_stack(0)))
        return embed

    class raiseModal(discord.ui.Modal):
        def __init__(self, pokerManager):
            super().__init__(title="Raise", timeout=pokerManager.timeout)
            self.ctx = pokerManager.ctx
            self.pokerGame = pokerManager.pokerGame
            self.db_manager = pokerManager.db_manager
            self.pokerManager = pokerManager

            self.add_item(InputText(label="Amount", value="", placeholder="Enter amount"))

        async def callback(self, interaction: discord.Interaction):
            if self.children[0]:
                amount_raised = self.children[0].value
                if not amount_raised.isdigit():
                    await interaction.response.send_message("Please enter a valid number.")
                    return
                amount_raised = int(amount_raised)
                if (amount_raised == self.pokerGame.return_player_stack(0) + self.pokerGame.players[0].round_pot_commitment):
                    await interaction.response.send_message("You are __All-in.__")
                    await self.pokerManager.user_all_in()
                    return
                if (amount_raised > self.pokerGame.return_player_stack(0) + self.pokerGame.players[0].round_pot_commitment):
                    await interaction.response.send_message("You do not have enough chips.")
                    return
                if amount_raised < self.pokerGame.big_blind:
                    await interaction.response.send_message("Raise must be at least the big blind.")
                    return
                if amount_raised < 2 * self.pokerGame.current_bet:
                    await interaction.response.send_message("You must raise to at least double the current bet.")
                    return
                if (amount_raised >= self.pokerGame.return_player_stack(1) + self.pokerGame.players[1].round_pot_commitment):
                    opponent_stack = (self.pokerGame.return_player_stack(1) + self.pokerGame.players[1].round_pot_commitment)
                    await interaction.response.edit_message(content=f"You put chat gpt __All-in for {opponent_stack} chips.__", view=None)
                    await self.pokerManager.user_all_in()

                await interaction.response.edit_message(content=f"You __Raise to {amount_raised} chips.__", view=None)
                await self.pokerManager.user_raise(amount_raised)

    class callView(View):
        def __init__(self, pokerManager):
            super().__init__(timeout=pokerManager.timeout)
            self.responded = False
            self.ctx = pokerManager.ctx
            self.pokerGame = pokerManager.pokerGame
            self.db_manager = pokerManager.db_manager
            self.pokerManager = pokerManager

        async def on_timeout(self):
            if not self.responded:
                if self.message:
                    await self.message.edit(content="You took too long! You __Fold.__", view=None)
                await self.pokerManager.user_fold()

        async def check(self, interaction: discord.Interaction):
            if interaction.user:
                return interaction.user.id == self.ctx.author.id

        @discord.ui.button(label="Call", style=ButtonStyle.blurple)
        async def call_button_callback(self, button, interaction):
            if await self.check(interaction):
                logger.info(f"{self.ctx.author.name} - User Calls.")
                self.responded = True
                self.pokerGame.player_call(0)
                if self.message:
                    await self.message.edit(content="You __Call.__", view=None)
                await self.pokerManager.next_action()

        @discord.ui.button(label="Raise", style=ButtonStyle.green)
        async def raise_button_callback(self, button, interaction):
            if await self.check(interaction):
                self.responded = True
                await interaction.response.send_modal(self.pokerManager.raiseModal(self.pokerManager))

        @discord.ui.button(label="All-in", style=ButtonStyle.green)
        async def all_in_button_callback(self, button, interaction):
            if await self.check(interaction):
                self.responded = True
                if self.message:
                    await self.message.edit(
                        content=f"You are __All In for {self.pokerGame.return_player_stack(0) + self.pokerGame.players[0].round_pot_commitment} chips.__", view=None)
                await self.pokerManager.user_all_in()

        @discord.ui.button(label="Fold", style=ButtonStyle.red)
        async def fold_button_callback(self, button, interaction):
            if await self.check(interaction):
                self.responded = True
                if self.message:
                    await self.message.edit(content="You __Fold.__", view=None)
                await self.pokerManager.user_fold()

    class checkView(View):
        def __init__(self, pokerManager):
            super().__init__(timeout=pokerManager.timeout)
            self.responded = False
            self.ctx = pokerManager.ctx
            self.pokerGame = pokerManager.pokerGame
            self.db_manager = pokerManager.db_manager
            self.pokerManager = pokerManager

        async def on_timeout(self):
            if not self.responded:
                logger.info(f"{self.ctx.author.name} - User Checks.")
                if self.message:
                    await self.message.edit(content="You took too long! You __Check.__", view=None)
                await self.pokerManager.next_action()

        async def check(self, interaction: discord.Interaction):
            if interaction.user:
                return interaction.user.id == self.ctx.author.id

        @discord.ui.button(label="Check", style=ButtonStyle.blurple)
        async def call_button_callback(self, button, interaction):
            if await self.check(interaction):
                logger.info(f"{self.ctx.author.name} - User Checks.")
                self.responded = True
                if self.message:
                    await self.message.edit(content="You __Check.__", view=None)
                await self.pokerManager.next_action()

        @discord.ui.button(label="Raise", style=ButtonStyle.green)
        async def raise_button_callback(self, button, interaction):
            if await self.check(interaction):
                self.responded = True
                await interaction.response.send_modal(self.pokerManager.raiseModal(self.pokerManager))

        @discord.ui.button(label="All-in", style=ButtonStyle.green)
        async def all_in_button_callback(self, button, interaction):
            if await self.check(interaction):
                self.responded = True
                if self.message:
                    await self.message.edit(content=f"You are __All-in for {self.pokerGame.return_player_stack(0) + self.pokerGame.players[0].round_pot_commitment} chips.__", view=None)
                await self.pokerManager.user_all_in()

    class allInCallView(View):
        def __init__(self, pokerManager):
            super().__init__(timeout=pokerManager.timeout)
            self.responded = False
            self.ctx = pokerManager.ctx
            self.pokerGame = pokerManager.pokerGame
            self.db_manager = pokerManager.db_manager
            self.pokerManager = pokerManager

        async def on_timeout(self):
            if self.responded == False:
                if self.message:
                    await self.message.edit(content="You took too long! You __Fold__.", view=None)
                await self.pokerManager.user_fold()

        async def check(self, interaction: discord.Interaction):
            if interaction.user:
                return interaction.user.id == self.ctx.author.id

        @discord.ui.button(label="Call All-in", style=ButtonStyle.blurple)
        async def call_button_callback(self, button, interaction):
            if await self.check(interaction):
                logger.info(f"{self.ctx.author.name} - User Calls All-in.")
                self.responded = True
                if self.message:
                    await self.message.edit(content="You __Call the All-in.__", view=None)
                self.pokerGame.player_call(0)
                await self.pokerManager.showdown()

        @discord.ui.button(label="Fold", style=ButtonStyle.red)
        async def fold_button_callback(self, button, interaction):
            if await self.check(interaction):
                self.responded = True
                if self.message:
                    await self.message.edit(content="You __Fold.__", view=None)
                await self.pokerManager.user_fold()

    class newRoundView(View):
        def __init__(self, pokerManager):
            super().__init__(timeout=pokerManager.timeout)
            self.responded = False
            self.ctx = pokerManager.ctx
            self.pokerGame = pokerManager.pokerGame
            self.db_manager = pokerManager.db_manager
            self.pokerManager = pokerManager

        async def on_timeout(self):
            if self.responded == False:
                self.db_manager.end_game(self.pokerGame.return_player_stack(0))
                embed = self.pokerManager.result_embed()
                if self.message:
                    await self.message.edit(content="*Game Ended*", view=None, embeds=[embed])

        async def check(self, interaction: Interaction):
            if interaction.user:
                return interaction.user.id == self.ctx.author.id

        @discord.ui.button(label="New Round", style=ButtonStyle.blurple)
        async def new_round_button_callback(self, button, interaction):
            if await self.check(interaction):
                self.responded = True
                if self.message:
                    await self.message.edit(content="*Starting a new round.*", view=None)
                await self.pokerManager.play_round()

        @discord.ui.button(label="End Game", style=ButtonStyle.red)
        async def end_game_button_callback(self, button, interaction):
            if await self.check(interaction):
                self.responded = True
                self.db_manager.end_game(self.pokerGame.return_player_stack(0))
                embed = self.pokerManager.result_embed()
                if self.message:
                    await self.message.edit(content="*Game Ended*", view=None, embeds=[embed])
