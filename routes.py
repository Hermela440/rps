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
