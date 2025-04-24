"""Admin panel routes and views"""
from datetime import datetime, timedelta, UTC
from functools import wraps
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from sqlalchemy import func
from app import db
from models import User, Game, GameParticipant, Transaction
from payment_service import PaymentService

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

def admin_required(f):
    """Decorator to check if user is admin"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # TODO: Implement proper admin authentication
        # For now, we'll use a simple session check
        if not request.args.get('admin'):
            return redirect(url_for('admin.login'))
        return f(*args, **kwargs)
    return decorated_function

@admin_bp.route('/login')
def login():
    """Admin login page"""
    return render_template('admin/login.html')

@admin_bp.route('/dashboard')
@admin_required
def dashboard():
    """Admin dashboard with overview"""
    # Get today's stats
    today = datetime.now(UTC).date()
    today_start = datetime.combine(today, datetime.min.time().replace(tzinfo=UTC))
    
    stats = {
        'active_rooms': Game.query.filter(Game.status.in_(['waiting', 'ready', 'playing'])).count(),
        'total_players': User.query.count(),
        'active_players': GameParticipant.query.join(Game).filter(
            Game.status.in_(['waiting', 'ready', 'playing'])
        ).distinct(GameParticipant.user_id).count(),
        'total_bets_today': db.session.query(func.sum(Game.bet_amount)).filter(
            Game.created_at >= today_start
        ).scalar() or 0,
        'pending_transactions': Transaction.query.filter_by(status='pending').count(),
        'failed_transactions': Transaction.query.filter_by(status='failed').count()
    }
    
    # Get recent games
    games = Game.query.order_by(Game.created_at.desc()).limit(10).all()
    
    # Get recent transactions
    transactions = Transaction.query.order_by(Transaction.created_at.desc()).limit(10).all()
    
    return render_template('admin/dashboard.html', stats=stats, games=games, transactions=transactions)

@admin_bp.route('/rooms')
@admin_required
def rooms():
    """Game rooms management"""
    rooms = Game.query.order_by(Game.created_at.desc()).all()
    return render_template('admin/rooms.html', rooms=rooms)

@admin_bp.route('/room/<int:room_id>')
@admin_required
def room_detail(room_id):
    """Game room details"""
    room = Game.query.get_or_404(room_id)
    return render_template('admin/room_detail.html', room=room)

@admin_bp.route('/players')
@admin_required
def players():
    """Player management"""
    players = User.query.all()
    return render_template('admin/players.html', players=players)

@admin_bp.route('/player/<int:player_id>')
@admin_required
def player_detail(player_id):
    """Player details and history"""
    player = User.query.get_or_404(player_id)
    return render_template('admin/player_detail.html', player=player)

@admin_bp.route('/transactions')
@admin_required
def transactions():
    """Transaction management"""
    transactions = Transaction.query.order_by(Transaction.created_at.desc()).all()
    return render_template('admin/transactions.html', transactions=transactions)

@admin_bp.route('/api/room/<int:room_id>/close', methods=['POST'])
@admin_required
def api_close_room(room_id):
    """API endpoint to force-close a room"""
    room = Game.query.get_or_404(room_id)
    
    # Refund all participants
    for participant in room.participants:
        user = db.session.get(User, participant.user_id)
        if user:
            user.balance += room.bet_amount
            
            # Create refund transaction
            transaction = Transaction(
                user_id=user.id,
                amount=room.bet_amount,
                transaction_type='refund',
                status='completed',
                reference_id=f"admin_close_{room.id}",
                completed_at=datetime.now(UTC)
            )
            db.session.add(transaction)
    
    room.status = 'cancelled'
    room.completed_at = datetime.now(UTC)
    db.session.commit()
    
    return jsonify({'status': 'success', 'message': 'Room closed successfully'})

@admin_bp.route('/api/player/<int:player_id>/ban', methods=['POST'])
@admin_required
def api_ban_player(player_id):
    """API endpoint to ban/unban a player"""
    player = User.query.get_or_404(player_id)
    player.is_banned = not player.is_banned
    db.session.commit()
    
    return jsonify({
        'status': 'success',
        'message': f"Player {'banned' if player.is_banned else 'unbanned'} successfully"
    })

@admin_bp.route('/api/transaction/<int:transaction_id>/verify', methods=['POST'])
@admin_required
def api_verify_transaction(transaction_id):
    """API endpoint to manually verify a transaction"""
    transaction = Transaction.query.get_or_404(transaction_id)
    
    if transaction.status == 'completed':
        return jsonify({'status': 'error', 'message': 'Transaction already completed'})
    
    success, message = PaymentService.verify_payment(transaction.reference_id)
    return jsonify({'status': 'success' if success else 'error', 'message': message}) 