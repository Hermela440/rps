from datetime import datetime
from sqlalchemy import and_, or_, func
from app import db
from models import User, Game, GameParticipant, Transaction
from config import (
    BET_AMOUNT_DEFAULT, FIXED_BET_AMOUNTS,
    MIN_DEPOSIT_AMOUNT as MIN_BET_AMOUNT,
    MAX_DEPOSIT_AMOUNT as MAX_BET_AMOUNT,
    PLATFORM_FEE_PERCENT, LOGGER
)


class Game(db.Model):
    """Game model for storing game information"""
    __tablename__ = 'games'
    
    id = db.Column(db.Integer, primary_key=True)
    creator_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    bet_amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='waiting')  # waiting, in_progress, completed
    min_players = db.Column(db.Integer, default=3)
    max_players = db.Column(db.Integer, default=3)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)
    
    # Relationships
    creator = db.relationship('User', backref='created_games', foreign_keys=[creator_id])
    participants = db.relationship('GameParticipant', backref='game', lazy=True, cascade='all, delete-orphan')

class GameParticipant(db.Model):
    """Model for storing game participants and their choices"""
    __tablename__ = 'game_participants'
    
    id = db.Column(db.Integer, primary_key=True)
    game_id = db.Column(db.Integer, db.ForeignKey('games.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    choice = db.Column(db.String(10))  # rock, paper, or scissors
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref='game_participations')

class RPSGame:
    """Game service class for Rock Paper Scissors game logic"""
    
    TEST_MODE = True  # Enable test mode for free games
    
    @staticmethod
    def ensure_test_balance(user_id, minimum_required=1000):
        """Ensure user has minimum balance in test mode"""
        if not RPSGame.TEST_MODE:
            return
            
        user = User.query.get(user_id)
        if not user:
            return
            
        if user.balance < minimum_required:
            # Give user some test balance
            user.balance = minimum_required
            db.session.commit()

    @staticmethod
    def validate_bet_amount(amount):
        """Validate bet amount is within allowed range"""
        if amount < 10:
            return False, "Minimum bet amount is ETB 10"
        if amount > 1000:
            return False, "Maximum bet amount is ETB 1000"
        return True, "Valid bet amount"

    @staticmethod
    def create_game(creator_id, bet_amount, min_players=3, max_players=3):
        """Create a new game and add creator as first participant"""
        # Ensure creator has enough balance in test mode
        RPSGame.ensure_test_balance(creator_id)
        
        # Validate bet amount
        valid, message = RPSGame.validate_bet_amount(bet_amount)
        if not valid:
            return None
            
        # Get creator
        creator = User.query.get(creator_id)
        if not creator:
            return None
            
        # Create new game
        game = Game(
            creator_id=creator_id,
            bet_amount=bet_amount,
            status='waiting',
            min_players=min_players,
            max_players=max_players
        )
        db.session.add(game)
        db.session.flush()
        
        # Add creator as first participant
        participant = GameParticipant(
            game_id=game.id,
            user_id=creator_id
        )
        db.session.add(participant)
        
        # Deduct bet amount from creator's balance
        creator.balance -= bet_amount
        
        db.session.commit()
        return game

    @staticmethod
    def join_game(game_id, user_id):
        """Allow a user to join an existing game"""
        # Ensure user has enough balance in test mode
        RPSGame.ensure_test_balance(user_id)
        
        game = Game.query.get(game_id)
        if not game:
            return False
            
        if game.status != 'waiting':
            return False
            
        # Get user
        user = User.query.get(user_id)
        if not user:
            return False
            
        # Check if user is already in game
        existing = GameParticipant.query.filter_by(
            game_id=game_id, 
            user_id=user_id
        ).first()
        if existing:
            return False
            
        # Check if game is full
        current_players = GameParticipant.query.filter_by(game_id=game_id).count()
        if current_players >= game.max_players:
            return False
            
        # Add user as participant
        participant = GameParticipant(
            game_id=game_id,
            user_id=user_id
        )
        db.session.add(participant)
        
        # Deduct bet amount from user's balance
        user.balance -= game.bet_amount
        
        # Update game status if max players reached
        if current_players + 1 >= game.max_players:
            game.status = 'in_progress'
            
        db.session.commit()
        return True

    @staticmethod
    def make_choice(game_id, user_id, choice):
        """Record a player's choice in the game"""
        if choice not in ['rock', 'paper', 'scissors']:
            return False
            
        game = Game.query.get(game_id)
        if not game or game.status != 'in_progress':
            return False
            
        participant = GameParticipant.query.filter_by(
            game_id=game_id,
            user_id=user_id
        ).first()
        
        if not participant:
            return False
            
        if participant.choice:
            return False
            
        participant.choice = choice
        db.session.commit()
        
        # Check if all players have made choices
        all_participants = GameParticipant.query.filter_by(game_id=game_id).all()
        
        if all(p.choice for p in all_participants):
            RPSGame._determine_winner(game)
            
        return True

    @staticmethod
    def get_game(game_id):
        """Get game by ID with all participants"""
        return Game.query.get(game_id)

    @staticmethod
    def _determine_winner(game):
        """Determine winner based on choices"""
        participants = GameParticipant.query.filter_by(game_id=game.id).all()
        choices = {p.choice: p.user_id for p in participants}
        
        winner_id = None
        
        # Find winner using classic RPS rules
        if 'rock' in choices and 'scissors' in choices:
            winner_id = choices['rock']
        elif 'scissors' in choices and 'paper' in choices:
            winner_id = choices['scissors']
        elif 'paper' in choices and 'rock' in choices:
            winner_id = choices['paper']
            
        # Update game status
        game.status = 'completed'
        game.completed_at = datetime.utcnow()
        
        # Update winner stats if there is one
        if winner_id:
            winner = User.query.get(winner_id)
            winner.games_won += 1
            winner.balance += game.bet_amount * (len(participants) - 1)
            
        # Update all participants' games played count
        for p in participants:
            user = User.query.get(p.user_id)
            user.games_played += 1
            if p.user_id != winner_id:
                user.balance -= game.bet_amount
                
        db.session.commit()
        return winner_id

    @staticmethod
    def _is_winner(choice1, choice2):
        """Check if choice1 beats choice2"""
        return (
            (choice1 == 'rock' and choice2 == 'scissors') or
            (choice1 == 'scissors' and choice2 == 'paper') or
            (choice1 == 'paper' and choice2 == 'rock')
        )

    @staticmethod
    def is_move_taken(game_id, choice):
        """Check if a move is already taken in the game"""
        return GameParticipant.query.filter_by(
            game_id=game_id,
            choice=choice
        ).first() is not None

    @staticmethod
    def determine_winner(game_id):
        """Determine the winner of the game"""
        game = db.session.get(Game, game_id)
        if not game or game.status != 'playing':
            return None
        
        participants = GameParticipant.query.filter_by(game_id=game_id).all()
        if len(participants) != 3 or any(p.choice is None for p in participants):
            return None  # Game not ready for winner determination
        
        # Create mapping of choices to players
        choices = {p.choice: p for p in participants if p.choice}
        
        # Classic RPS rules
        if 'rock' in choices and 'scissors' in choices:
            return choices['rock']  # Rock beats Scissors
        if 'scissors' in choices and 'paper' in choices:
            return choices['scissors']  # Scissors beats Paper
        if 'paper' in choices and 'rock' in choices:
            return choices['paper']  # Paper beats Rock
            
        return None  # No clear winner (shouldn't happen with unique moves)
    
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
        # Validate bet amount first
        is_valid, message = RPSGame.validate_bet_amount(bet_amount)
        if not is_valid:
            return None, message
            
        user = User.query.get(user_id)
        if not user:
            return None, "User not found."
        
        if user.balance < bet_amount:
            return None, f"Insufficient balance. You need {bet_amount} coins to play."
        
        try:
            # First try to find an existing game with exactly the same bet amount
            available_games = Game.query.filter(
                Game.status == 'waiting',
                Game.bet_amount == bet_amount
            ).all()
            
            # Find games that aren't full
            joinable_games = []
            for game in available_games:
                participant_count = db.session.query(func.count(GameParticipant.id)).filter_by(game_id=game.id).scalar()
                if participant_count < 3:
                    joinable_games.append((game, participant_count))
            
            if joinable_games:
                # Sort by most filled games first to fill games faster
                joinable_games.sort(key=lambda x: x[1], reverse=True)
                game = joinable_games[0][0]
                success, message = RPSGame.join_game(game.id, user_id)
                if success:
                    return game, "Joined existing game"
                return None, message
            
            # No suitable game found, create a new one
            game, message = RPSGame.create_game(bet_amount, user_id)
            if game:
                return game, "Created new room"
            return None, message
        
        except Exception as e:
            db.session.rollback()
            LOGGER.error(f"Error finding/creating game: {e}")
            return False, "Error finding or creating game. Please try again."

    @staticmethod
    def get_game_status(game_id, user_id=None):
        """Get detailed game status including player choices and results"""
        game = Game.query.get(game_id)
        if not game:
            return None
        
        participants = GameParticipant.query.filter_by(game_id=game_id).all()
        total_players = len(participants)
        players_ready = len([p for p in participants if p.choice is not None])
        
        status_info = {
            'game_id': game.id,
            'status': game.status,
            'bet_amount': float(game.bet_amount),
            'total_players': total_players,
            'players_ready': players_ready,
            'is_completed': game.status == 'completed',
            'players': []
        }
        
        # Add player information
        for p in participants:
            player = User.query.get(p.user_id)
            player_info = {
                'user_id': player.id,
                'username': player.username,
                'has_chosen': p.choice is not None
            }
            
            # Only show choices if game is completed or if it's the current player
            if game.status == 'completed' or (user_id and p.user_id == user_id):
                player_info['choice'] = p.choice
            
            if game.status == 'completed':
                player_info['is_winner'] = game.winner_id == p.user_id
            
            status_info['players'].append(player_info)
        
        if game.status == 'completed':
            if game.winner_id:
                winner = User.query.get(game.winner_id)
                status_info['winner'] = {
                    'user_id': winner.id,
                    'username': winner.username,
                    'winnings': float(game.bet_amount * 3)
                }
            else:
                status_info['winner'] = None
        
        return status_info
