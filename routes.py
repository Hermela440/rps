from flask import render_template, redirect, url_for, request, flash, jsonify, session
from sqlalchemy import func
from extensions import db
from models import User, Game, GameParticipant, Transaction, WithdrawalRequest
from utils import get_leaderboard
from admin import AdminService
import logging

def register_routes(app):
    @app.route('/')
    def index():
        total_users = User.query.count()
        total_games = Game.query.count()
        games_completed = Game.query.filter_by(status='completed').count()

        recent_games = Game.query.filter_by(status='completed').order_by(Game.completed_at.desc()).limit(5).all()
        top_players = get_leaderboard(5)

        return render_template('index.html', total_users=total_users, total_games=total_games,
                               games_completed=games_completed, recent_games=recent_games,
                               top_players=top_players)

    @app.route('/dashboard')
    def dashboard():
        user_id = session.get('user_id')
        if not user_id:
            flash('You must be logged in to access the dashboard.', 'danger')
            return redirect(url_for('index'))

        user = User.query.get(user_id)
        if not user or not user.is_admin:
            flash('You do not have permission to access the dashboard.', 'danger')
            return redirect(url_for('index'))

        stats = AdminService.get_system_stats()
        pending_withdrawals = WithdrawalRequest.query.filter_by(status='pending').order_by(
            WithdrawalRequest.created_at.asc()).all()
        recent_users = AdminService.get_recent_users(5)
        recent_games = AdminService.get_recent_games(5)

        return render_template('dashboard.html', stats=stats, pending_withdrawals=pending_withdrawals,
                               recent_users=recent_users, recent_games=recent_games)

    @app.route('/leaderboard')
    def leaderboard():
        top_players = get_leaderboard(20)
        return render_template('leaderboard.html', top_players=top_players)

    @app.route('/admin')
    def admin():
        user_id = session.get('user_id')
        if not user_id:
            flash('You must be logged in to access the admin panel.', 'danger')
            return redirect(url_for('index'))

        user = User.query.get(user_id)
        if not user or not user.is_admin:
            flash('You do not have permission to access the admin panel.', 'danger')
            return redirect(url_for('index'))

        return render_template('admin.html')

    @app.route('/api/approve_withdrawal/<int:withdrawal_id>', methods=['POST'])
    def approve_withdrawal(withdrawal_id):
        user_id = session.get('user_id')
        user = User.query.get(user_id)
        if not user or not user.is_admin:
            return jsonify({'success': False, 'message': 'Not authorized'}), 401

        success, message = AdminService.approve_withdrawal(withdrawal_id, user.id)
        return jsonify({'success': success, 'message': message})

    @app.route('/api/reject_withdrawal/<int:withdrawal_id>', methods=['POST'])
    def reject_withdrawal(withdrawal_id):
        user_id = session.get('user_id')
        user = User.query.get(user_id)
        if not user or not user.is_admin:
            return jsonify({'success': False, 'message': 'Not authorized'}), 401

        success, message = AdminService.reject_withdrawal(withdrawal_id, user.id)
        return jsonify({'success': success, 'message': message})

    @app.route('/api/search_user', methods=['GET'])
    def search_user():
        user_id = session.get('user_id')
        user = User.query.get(user_id)
        if not user or not user.is_admin:
            return jsonify({'success': False, 'message': 'Not authorized'}), 401

        query = request.args.get('q', '')
        if not query:
            return jsonify({'success': False, 'message': 'Search query required'}), 400

        users = AdminService.search_user(query)
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
        game = Game.query.get_or_404(game_id)
        if game.status != 'completed':
            flash('This game is not completed yet.', 'warning')
            return redirect(url_for('index'))

        participants = GameParticipant.query.filter_by(game_id=game_id).all()
        if len(participants) < 3:
            flash('This game does not have enough participants.', 'warning')
            return redirect(url_for('index'))

        return render_template('game_result.html', game=game)

    @app.route('/deposit', methods=['GET', 'POST'])
    def deposit():
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

            if not success or isinstance(result, str):
                flash(result, 'danger')
                return redirect(url_for('deposit'))

            payment_url = result.get('payment_url', '')
            payment_id = result.get('payment_id', '')
            expires_at = result.get('expires_at', '')
            from datetime import datetime
            expires_at_formatted = datetime.fromtimestamp(expires_at).strftime('%Y-%m-%d %H:%M:%S') if expires_at else ''

            return render_template('payment.html', amount=amount, payment_status='pending',
                                   wallet_address='capa_wallet_deposit_address',
                                   payment_id=payment_id, payment_url=payment_url,
                                   expires_at_formatted=expires_at_formatted)

        user = User.query.get(user_id)
        return render_template('deposit.html', user=user)

    @app.route('/withdraw', methods=['GET', 'POST'])
    def withdraw():
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

            message = result.get('message', 'Withdrawal request submitted successfully.') if isinstance(result, dict) else result
            flash(message, 'success')
            return redirect(url_for('dashboard'))

        user = User.query.get(user_id)
        return render_template('withdraw.html', user=user)

    @app.route('/payment/status/<payment_id>')
    def payment_status(payment_id):
        from capa_wallet import CapaWallet
        success, is_paid, data = CapaWallet.verify_payment(payment_id)

        if not success:
            return jsonify({'success': False, 'message': 'Failed to verify payment'})

        return jsonify({'success': True, 'status': 'completed' if is_paid else 'pending', 'payment_data': data})

    @app.route('/payment/success')
    def payment_success():
        payment_id = request.args.get('payment_id', '')
        if not payment_id:
            flash('Invalid payment reference.', 'danger')
            return redirect(url_for('dashboard'))

        from capa_wallet import CapaWallet
        # Further implementation here...
