from flask import render_template, redirect, url_for, request, flash, jsonify, session
from sqlalchemy import func
from models import User, Game, GameParticipant, Transaction, WithdrawalRequest
from app import db
from utils import get_leaderboard
from admin import AdminService
import logging

def register_routes(app):
    @app.route('/')
    def index():
        """Home page with game statistics"""
        # Get basic stats
        total_users = User.query.count()
        total_games = Game.query.count()
        games_completed = Game.query.filter_by(status='completed').count()
        
        # Get recent games
        recent_games = Game.query.filter_by(status='completed').order_by(
            Game.completed_at.desc()
        ).limit(5).all()
        
        # Get top players
        top_players = get_leaderboard(5)
        
        return render_template(
            'index.html', 
            total_users=total_users,
            total_games=total_games,
            games_completed=games_completed,
            recent_games=recent_games,
            top_players=top_players
        )
    
    @app.route('/dashboard')
    def dashboard():
        """Admin dashboard"""
        # Check if user is admin
        user_id = session.get('user_id')
        if not user_id:
            flash('You must be logged in to access the dashboard.', 'danger')
            return redirect(url_for('index'))
        
        user = User.query.get(user_id)
        if not user or not user.is_admin:
            flash('You do not have permission to access the dashboard.', 'danger')
            return redirect(url_for('index'))
        
        # Get admin stats
        stats = AdminService.get_system_stats()
        
        # Get pending withdrawals
        pending_withdrawals = WithdrawalRequest.query.filter_by(
            status='pending'
        ).order_by(
            WithdrawalRequest.created_at.asc()
        ).all()
        
        # Get recent users
        recent_users = AdminService.get_recent_users(5)
        
        # Get recent games
        recent_games = AdminService.get_recent_games(5)
        
        return render_template(
            'dashboard.html',
            stats=stats,
            pending_withdrawals=pending_withdrawals,
            recent_users=recent_users,
            recent_games=recent_games
        )
    
    @app.route('/leaderboard')
    def leaderboard():
        """Leaderboard page"""
        # Get top players
        top_players = get_leaderboard(20)
        
        return render_template('leaderboard.html', top_players=top_players)
    
    @app.route('/admin')
    def admin():
        """Admin page"""
        # Check if user is admin
        user_id = session.get('user_id')
        if not user_id:
            flash('You must be logged in to access the admin panel.', 'danger')
            return redirect(url_for('index'))
        
        user = User.query.get(user_id)
        if not user or not user.is_admin:
            flash('You do not have permission to access the admin panel.', 'danger')
            return redirect(url_for('index'))
        
        return render_template('admin.html')
    
    # API endpoints for admin actions
    @app.route('/api/approve_withdrawal/<int:withdrawal_id>', methods=['POST'])
    def approve_withdrawal(withdrawal_id):
        """API endpoint to approve a withdrawal"""
        # Check if user is admin
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'success': False, 'message': 'Not authorized'}), 401
        
        user = User.query.get(user_id)
        if not user or not user.is_admin:
            return jsonify({'success': False, 'message': 'Not authorized'}), 401
        
        success, message = AdminService.approve_withdrawal(withdrawal_id, user.id)
        
        return jsonify({'success': success, 'message': message})
    
    @app.route('/api/reject_withdrawal/<int:withdrawal_id>', methods=['POST'])
    def reject_withdrawal(withdrawal_id):
        """API endpoint to reject a withdrawal"""
        # Check if user is admin
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'success': False, 'message': 'Not authorized'}), 401
        
        user = User.query.get(user_id)
        if not user or not user.is_admin:
            return jsonify({'success': False, 'message': 'Not authorized'}), 401
        
        success, message = AdminService.reject_withdrawal(withdrawal_id, user.id)
        
        return jsonify({'success': success, 'message': message})
    
    @app.route('/api/search_user', methods=['GET'])
    def search_user():
        """API endpoint to search for users"""
        # Check if user is admin
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'success': False, 'message': 'Not authorized'}), 401
        
        user = User.query.get(user_id)
        if not user or not user.is_admin:
            return jsonify({'success': False, 'message': 'Not authorized'}), 401
        
        query = request.args.get('q', '')
        if not query:
            return jsonify({'success': False, 'message': 'Search query required'}), 400
        
        users = AdminService.search_user(query)
        
        # Format results
        results = []
        for u in users:
            win_rate = (u.games_won / u.games_played * 100) if u.games_played > 0 else 0
            results.append({
                'id': u.id,
                'username': u.username,
                'balance': u.balance,
                'games_played': u.games_played,
                'games_won': u.games_won,
                'win_rate': win_rate,
                'created_at': u.created_at.strftime('%Y-%m-%d %H:%M'),
                'is_admin': u.is_admin
            })
        
        return jsonify({'success': True, 'users': results})
        
    @app.route('/game/<int:game_id>/result')
    def game_result(game_id):
        """Show the result of a completed game with animations"""
        game = Game.query.get_or_404(game_id)
        
        # Ensure the game is completed
        if game.status != 'completed':
            flash('This game is not completed yet.', 'warning')
            return redirect(url_for('index'))
            
        # Fetch all participants with their choices
        participants = GameParticipant.query.filter_by(game_id=game_id).all()
        
        # If less than 3 participants, redirect to home
        if len(participants) < 3:
            flash('This game does not have enough participants.', 'warning')
            return redirect(url_for('index'))
            
        return render_template('game_result.html', game=game)
        
    # Payment routes
    @app.route('/deposit', methods=['GET', 'POST'])
    def deposit():
        """Handle deposits using Capa Wallet"""
        # Check if user is logged in
        user_id = session.get('user_id')
        if not user_id:
            flash('You must be logged in to make a deposit.', 'danger')
            return redirect(url_for('index'))
        
        if request.method == 'POST':
            try:
                amount = float(request.form.get('amount', 0))
            except ValueError:
                flash('Invalid amount.', 'danger')
                return redirect(url_for('deposit'))
                
            from payments import PaymentSystem
            
            success, result = PaymentSystem.deposit(user_id, amount)
            
            if not success:
                flash(result, 'danger')
                return redirect(url_for('deposit'))
                
            # If result is a string, it's an error message
            if isinstance(result, str):
                flash(result, 'danger')
                return redirect(url_for('deposit'))
                
            # For successful payment, redirect to payment page
            payment_url = result.get('payment_url', '')
            payment_id = result.get('payment_id', '')
            expires_at = result.get('expires_at', '')
            
            # Convert timestamp to readable format
            from datetime import datetime
            expires_at_formatted = datetime.fromtimestamp(expires_at).strftime('%Y-%m-%d %H:%M:%S') if expires_at else ''
            
            return render_template(
                'payment.html',
                amount=amount,
                payment_status='pending',
                wallet_address='capa_wallet_deposit_address',
                payment_id=payment_id,
                payment_url=payment_url,
                expires_at_formatted=expires_at_formatted
            )
            
        # GET request - show deposit form
        user = User.query.get(user_id)
        return render_template('deposit.html', user=user)
        
    @app.route('/withdraw', methods=['GET', 'POST'])
    def withdraw():
        """Handle withdrawals using Capa Wallet"""
        # Check if user is logged in
        user_id = session.get('user_id')
        if not user_id:
            flash('You must be logged in to make a withdrawal.', 'danger')
            return redirect(url_for('index'))
            
        if request.method == 'POST':
            try:
                amount = float(request.form.get('amount', 0))
            except ValueError:
                flash('Invalid amount.', 'danger')
                return redirect(url_for('withdraw'))
                
            wallet_address = request.form.get('wallet_address', '')
            if not wallet_address:
                flash('Wallet address is required.', 'danger')
                return redirect(url_for('withdraw'))
                
            from payments import PaymentSystem
            
            success, result = PaymentSystem.request_withdrawal(user_id, amount)
            
            if not success:
                flash(result, 'danger')
                return redirect(url_for('withdraw'))
                
            # If result is a dictionary, it contains transaction info
            if isinstance(result, dict):
                message = result.get('message', 'Withdrawal request submitted successfully.')
                flash(message, 'success')
            else:
                flash(result, 'success')
                
            return redirect(url_for('dashboard'))
            
        # GET request - show withdrawal form
        user = User.query.get(user_id)
        return render_template('withdraw.html', user=user)
        
    @app.route('/payment/status/<payment_id>')
    def payment_status(payment_id):
        """Check the status of a payment"""
        from capa_wallet import CapaWallet
        
        success, is_paid, data = CapaWallet.verify_payment(payment_id)
        
        if not success:
            return jsonify({'success': False, 'message': 'Failed to verify payment'})
            
        return jsonify({
            'success': True,
            'status': 'completed' if is_paid else 'pending',
            'payment_data': data
        })
        
    @app.route('/payment/success')
    def payment_success():
        """Payment success redirect from Capa Wallet"""
        payment_id = request.args.get('payment_id', '')
        
        if not payment_id:
            flash('Invalid payment reference.', 'danger')
            return redirect(url_for('dashboard'))
            
        # Verify the payment
        from capa_wallet import CapaWallet
        
        success, is_paid, data = CapaWallet.verify_payment(payment_id)
        
        if not success or not is_paid:
            flash('Payment verification failed.', 'danger')
            return redirect(url_for('dashboard'))
            
        flash('Payment completed successfully!', 'success')
        return redirect(url_for('dashboard'))
        
    @app.route('/payment/cancel')
    def payment_cancel():
        """Payment cancellation redirect from Capa Wallet"""
        flash('Payment was cancelled.', 'warning')
        return redirect(url_for('dashboard'))
        
    @app.route('/api/payment/webhook', methods=['POST'])
    def payment_webhook():
        """Webhook endpoint for Capa Wallet payment updates"""
        # Verify the webhook signature
        from capa_wallet import CapaWallet
        
        signature = request.headers.get('X-Capa-Signature', '')
        payload = request.get_data(as_text=True)
        
        if not CapaWallet.verify_webhook_signature(payload, signature):
            return jsonify({'success': False, 'message': 'Invalid signature'}), 400
            
        # Process the webhook payload
        data = request.json
        event_type = data.get('event_type', '')
        payment_id = data.get('payment_id', '')
        
        if not payment_id:
            return jsonify({'success': False, 'message': 'Invalid payment ID'}), 400
            
        # Find the transaction
        transaction = Transaction.query.filter_by(reference_id=payment_id).first()
        
        if not transaction:
            return jsonify({'success': False, 'message': 'Transaction not found'}), 404
            
        # Update transaction status based on event type
        if event_type == 'payment.completed':
            # Process the payment
            from payments import PaymentSystem
            PaymentSystem._process_successful_payment(transaction.id)
            
        elif event_type == 'payment.failed':
            # Mark as failed
            transaction.status = 'failed'
            db.session.commit()
            
        return jsonify({'success': True})
