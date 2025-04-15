from datetime import datetime
from sqlalchemy import and_, or_, func
from app import db
from models import User, Game, GameParticipant, Transaction
from config import BET_AMOUNT_DEFAULT, PLATFORM_FEE_PERCENT, LOGGER


class RPSGame:
    """Rock, Paper, Scissors game logic"""
    
    @staticmethod
    def create_game(bet_amount=BET_AMOUNT_DEFAULT):
        """Create a new game"""
        game = Game(
            status='waiting',
            bet_amount=bet_amount
        )
        db.session.add(game)
        db.session.commit()
        return game
    
    @staticmethod
    def get_active_game():
        """Get a game that is waiting for players"""
        return Game.query.filter_by(status='waiting').first()
    
    @staticmethod
    def join_game(game_id, user_id):
        """Add a user to a game"""
        try:
            # Use session locking to prevent race conditions
            game = db.session.query(Game).filter_by(id=game_id).with_for_update().first()
            
            # Check if user is already in this game
            existing = GameParticipant.query.filter_by(
                game_id=game_id,
                user_id=user_id
            ).first()
            
            if existing:
                return False, "You have already joined this game."
            
            # Check if game is full
            if not game:
                return False, "Game not found."
            
            if game.status != 'waiting':
                return False, "This game has already started or has ended."
            
            participant_count = GameParticipant.query.filter_by(game_id=game_id).count()
            if participant_count >= 3:
                return False, "This game is already full."
            
            # Check if user has enough balance
            user = User.query.get(user_id)
            if user.balance < game.bet_amount:
                return False, f"You don't have enough balance. Required: {game.bet_amount}, Your balance: {user.balance}"
            
            # Deduct bet amount from user balance
            user.balance -= game.bet_amount
            
            # Create transaction record
            transaction = Transaction(
                user_id=user_id,
                amount=-game.bet_amount,
                transaction_type='bet',
                status='completed',
                reference_id=str(game_id),
                completed_at=datetime.utcnow()
            )
            db.session.add(transaction)
            
            # Add user to game
            participant = GameParticipant(
                game_id=game_id,
                user_id=user_id
            )
            db.session.add(participant)
            
            # Check if game is full after adding this player
            new_count = participant_count + 1
            if new_count >= 3:
                game.status = 'active'
            
            db.session.commit()
            
            return True, "You have successfully joined the game."
        except Exception as e:
            db.session.rollback()
            LOGGER.error(f"Error joining game: {e}")
            return False, "Could not join the game. Please try again."
    
    @staticmethod
    def make_choice(game_id, user_id, choice):
        """Record a player's choice"""
        if choice not in ['rock', 'paper', 'scissors']:
            return False, "Invalid choice. Please choose rock, paper, or scissors."
        
        game = Game.query.get(game_id)
        if not game:
            return False, "Game not found."
        
        if game.status != 'active':
            return False, "This game is not active."
        
        participant = GameParticipant.query.filter_by(
            game_id=game_id,
            user_id=user_id
        ).first()
        
        if not participant:
            return False, "You are not participating in this game."
        
        if participant.choice:
            return False, "You have already made your choice."
        
        participant.choice = choice
        db.session.commit()
        
        # Check if all players have made their choices
        all_chosen = GameParticipant.query.filter_by(
            game_id=game_id, 
            choice=None
        ).count() == 0
        
        if all_chosen:
            # Determine winner
            RPSGame.determine_winner(game_id)
        
        return True, f"You have chosen {choice}."
    
    @staticmethod
    def determine_winner(game_id):
        """Determine the winner of the game"""
        game = Game.query.get(game_id)
        if not game or game.status != 'active':
            return
        
        participants = GameParticipant.query.filter_by(game_id=game_id).all()
        if len(participants) != 3 or any(p.choice is None for p in participants):
            return  # Game not ready for winner determination
        
        # Extract choices
        choices = [(p.user_id, p.choice) for p in participants]
        
        # Count each choice
        choice_counts = {'rock': 0, 'paper': 0, 'scissors': 0}
        for _, choice in choices:
            choice_counts[choice] += 1
        
        # Determine winner based on classic RPS rules with 3 players
        # If all three made different choices, no one wins
        if choice_counts['rock'] == 1 and choice_counts['paper'] == 1 and choice_counts['scissors'] == 1:
            winner_id = None  # It's a draw
        
        # If all three made the same choice, no one wins
        elif choice_counts['rock'] == 3 or choice_counts['paper'] == 3 or choice_counts['scissors'] == 3:
            winner_id = None  # It's a draw
        
        # If two players chose the same and one different
        else:
            # Find the winning choice
            if choice_counts['rock'] == 2 and choice_counts['scissors'] == 1:
                winning_choice = 'rock'  # Rock beats scissors
            elif choice_counts['paper'] == 2 and choice_counts['rock'] == 1:
                winning_choice = 'paper'  # Paper beats rock
            elif choice_counts['scissors'] == 2 and choice_counts['paper'] == 1:
                winning_choice = 'scissors'  # Scissors beats paper
            else:
                winning_choice = None  # This shouldn't happen but just in case
            
            # Find user with winning choice
            winner_id = next((user_id for user_id, choice in choices if choice == winning_choice), None)
        
        # Update game
        game.status = 'completed'
        game.winner_id = winner_id
        game.completed_at = datetime.utcnow()
        
        # Process winnings
        if winner_id:
            # Winner gets total pot minus platform fee
            total_pot = game.bet_amount * len(participants)
            platform_fee = total_pot * (PLATFORM_FEE_PERCENT / 100)
            winnings = total_pot - platform_fee
            
            winner = User.query.get(winner_id)
            winner.balance += winnings
            winner.games_won += 1
            
            # Create transaction record
            transaction = Transaction(
                user_id=winner_id,
                amount=winnings,
                transaction_type='win',
                status='completed',
                reference_id=str(game_id),
                completed_at=datetime.utcnow()
            )
            db.session.add(transaction)
        else:
            # Refund all players if it's a draw
            for p in participants:
                user = User.query.get(p.user_id)
                user.balance += game.bet_amount
                
                # Create refund transaction
                transaction = Transaction(
                    user_id=p.user_id,
                    amount=game.bet_amount,
                    transaction_type='refund',
                    status='completed',
                    reference_id=str(game_id),
                    completed_at=datetime.utcnow()
                )
                db.session.add(transaction)
        
        # Update games_played for all participants
        for p in participants:
            user = User.query.get(p.user_id)
            user.games_played += 1
        
        db.session.commit()
        
        return game
    
    @staticmethod
    def get_user_games(user_id, limit=10):
        """Get recent games for a user"""
        games = db.session.query(Game).join(
            GameParticipant, Game.id == GameParticipant.game_id
        ).filter(
            GameParticipant.user_id == user_id
        ).order_by(
            Game.created_at.desc()
        ).limit(limit).all()
        
        return games
    
    @staticmethod
    def get_game_details(game_id):
        """Get details for a specific game"""
        game = Game.query.get(game_id)
        if not game:
            return None
        
        participants = GameParticipant.query.filter_by(game_id=game_id).all()
        participant_details = []
        
        for p in participants:
            user = User.query.get(p.user_id)
            participant_details.append({
                'user_id': p.user_id,
                'username': user.username,
                'choice': p.choice,
                'is_winner': game.winner_id == p.user_id if game.winner_id else False
            })
        
        return {
            'game_id': game.id,
            'status': game.status,
            'bet_amount': game.bet_amount,
            'created_at': game.created_at,
            'completed_at': game.completed_at,
            'participants': participant_details,
            'winner_id': game.winner_id
        }
    
    @staticmethod
    def clean_stale_games(max_age_minutes=30):
        """Clean up games that have been waiting too long"""
        from datetime import datetime, timedelta
        cutoff_time = datetime.utcnow() - timedelta(minutes=max_age_minutes)
        
        stale_games = Game.query.filter(
            Game.status == 'waiting',
            Game.created_at < cutoff_time
        ).all()
        
        for game in stale_games:
            # Refund all participants
            for participant in game.participants:
                user = User.query.get(participant.user_id)
                if user:
                    user.balance += game.bet_amount
                    
                    # Create refund transaction
                    transaction = Transaction(
                        user_id=user.id,
                        amount=game.bet_amount,
                        transaction_type='refund',
                        status='completed',
                        reference_id=f"timeout_{game.id}",
                        completed_at=datetime.utcnow()
                    )
                    db.session.add(transaction)
            
            # Mark game as cancelled
            game.status = 'cancelled'
            game.completed_at = datetime.utcnow()
        
        db.session.commit()
        return len(stale_games)
    
    @staticmethod
    def check_for_waiting_games(minimum_wait_minutes=5):
        """Check for games that have been waiting for a while and might need to start with fewer players"""
        from datetime import datetime, timedelta
        cutoff_time = datetime.utcnow() - timedelta(minutes=minimum_wait_minutes)
        
        # Find games with exactly 2 players waiting for a while
        waiting_games = db.session.query(Game).filter(
            Game.status == 'waiting',
            Game.created_at < cutoff_time
        ).all()
        
        for game in waiting_games:
            participant_count = GameParticipant.query.filter_by(game_id=game.id).count()
            
            # If we have exactly 2 players waiting for at least 5 minutes, start the game
            if participant_count == 2:
                game.status = 'active'
                db.session.commit()
                
                # Return the game ID so we can notify players
                return game.id
        
        return None

    @staticmethod
    def find_or_create_game(user_id, bet_amount=BET_AMOUNT_DEFAULT):
        """Find an existing game or create a new one with proper locking to avoid race conditions"""
        user = User.query.get(user_id)
        if not user:
            return None, "User not found."
        
        if user.balance < bet_amount:
            return None, f"Insufficient balance. You need ${bet_amount:.2f} to play."
        
        try:
            # First try to find an existing game with the same bet amount
            available_games = Game.query.filter_by(status='waiting', bet_amount=bet_amount).all()
            
            # Find games that aren't full
            joinable_games = []
            for game in available_games:
                # Count participants with a separate query to avoid race conditions
                participant_count = db.session.query(func.count(GameParticipant.id)).filter_by(game_id=game.id).scalar()
                if participant_count < 3:
                    joinable_games.append((game, participant_count))
            
            if joinable_games:
                # Sort by most filled games first to fill games faster
                joinable_games.sort(key=lambda x: x[1], reverse=True)
                return joinable_games[0][0], "Found existing game"
            
            # If no game with matching bet, try any game the user can afford
            if bet_amount == BET_AMOUNT_DEFAULT:  # Only auto-join if user is using default bet
                available_games = Game.query.filter(
                    Game.status == 'waiting',
                    Game.bet_amount <= user.balance
                ).all()
                
                joinable_games = []
                for game in available_games:
                    participant_count = db.session.query(func.count(GameParticipant.id)).filter_by(game_id=game.id).scalar()
                    if participant_count < 3:
                        joinable_games.append((game, participant_count))
                
                if joinable_games:
                    # Sort by most filled games first
                    joinable_games.sort(key=lambda x: x[1], reverse=True)
                    return joinable_games[0][0], "Found existing game with different bet"
            
            # No suitable game found, create a new one
            new_game = RPSGame.create_game(bet_amount)
            return new_game, "Created new game"
        
        except Exception as e:
            db.session.rollback()
            LOGGER.error(f"Error finding/creating game: {e}")
            return None, "Error finding or creating game. Please try again."
