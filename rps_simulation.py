#!/usr/bin/env python3
"""
Rock Paper Scissors Simulation for Telegram Bot
Generates a GIF animation of a Rock-Paper-Scissors battle
"""

import pygame
import random
import math
import os
import imageio
import tempfile
from datetime import datetime
from typing import Tuple, List
import numpy as np
from PIL import Image
from models import User, Game, GameParticipant, Transaction
from app import db
from decimal import Decimal

class Element:
    def __init__(self, x: float, y: float, element_type: str):
        self.x = x
        self.y = y
        self.element_type = element_type
        self.dx = random.uniform(-1, 1)
        self.dy = random.uniform(-1, 1)
        self.size = 10
        self.alive = True

    def move(self, width: int, height: int):
        """Move the element and bounce off walls"""
        self.x += self.dx
        self.y += self.dy

        # Bounce off walls
        if self.x < 0 or self.x > width:
            self.dx *= -1
        if self.y < 0 or self.y > height:
            self.dy *= -1

    def interact(self, other: 'Element') -> bool:
        """Check interaction with another element"""
        distance = math.sqrt((self.x - other.x)**2 + (self.y - other.y)**2)
        if distance < self.size * 2:
            if self.beats(other.element_type):
                other.alive = False
                return True
        return False

    def beats(self, other_type: str) -> bool:
        """Check if this element beats the other type"""
        return (
            (self.element_type == 'rock' and other_type == 'scissors') or
            (self.element_type == 'paper' and other_type == 'rock') or
            (self.element_type == 'scissors' and other_type == 'paper')
        )

def create_rps_simulation(rock_count: int, paper_count: int, scissors_count: int) -> Tuple[str, str, List[int]]:
    """Create a Rock-Paper-Scissors simulation and save as GIF"""
    # Initialize Pygame
    pygame.init()
    width, height = 400, 400
    screen = pygame.Surface((width, height))

    # Colors
    WHITE = (255, 255, 255)
    GRAY = (128, 128, 128)
    CREAM = (255, 253, 208)
    RED = (255, 0, 0)
    
    # Create elements
    elements = []
    for _ in range(rock_count):
        elements.append(Element(
            random.randint(0, width),
            random.randint(0, height),
            'rock'
        ))
    for _ in range(paper_count):
        elements.append(Element(
            random.randint(0, width),
            random.randint(0, height),
            'paper'
        ))
    for _ in range(scissors_count):
        elements.append(Element(
            random.randint(0, width),
            random.randint(0, height),
            'scissors'
        ))

    # Create frames for GIF
    frames = []
    max_frames = 200
    
    for frame in range(max_frames):
        # Fill background
        screen.fill(WHITE)
        
        # Move and draw elements
        for element in elements:
            if not element.alive:
                continue
                
            element.move(width, height)
            
            # Draw different shapes based on element type
            if element.element_type == 'rock':
                pygame.draw.circle(
                    screen,
                    GRAY,
                    (int(element.x), int(element.y)),
                    element.size
                )
            elif element.element_type == 'paper':
                pygame.draw.rect(
                    screen,
                    CREAM,
                    (int(element.x - element.size),
                     int(element.y - element.size),
                     element.size * 2,
                     element.size * 2)
                )
            else:  # scissors
                size = element.size
                center = (int(element.x), int(element.y))
                points = [
                    (center[0] - size, center[1] - size),
                    (center[0] + size, center[1] + size),
                    (center[0] + size, center[1] - size),
                    (center[0] - size, center[1] + size)
                ]
                pygame.draw.line(screen, RED, points[0], points[1], 3)
                pygame.draw.line(screen, RED, points[2], points[3], 3)

        # Check interactions
        for i, elem1 in enumerate(elements):
            if not elem1.alive:
                continue
            for elem2 in elements[i+1:]:
                if not elem2.alive:
                    continue
                elem1.interact(elem2)
                elem2.interact(elem1)

        # Convert Pygame surface to PIL Image
        string_image = pygame.image.tostring(screen, 'RGB')
        temp_surface = Image.frombytes('RGB', (width, height), string_image)
        frames.append(temp_surface)

        # Count surviving elements
        rock_alive = sum(1 for e in elements if e.alive and e.element_type == 'rock')
        paper_alive = sum(1 for e in elements if e.alive and e.element_type == 'paper')
        scissors_alive = sum(1 for e in elements if e.alive and e.element_type == 'scissors')

        # Check if simulation should end
        if rock_alive == 0 and paper_alive == 0 or \
           paper_alive == 0 and scissors_alive == 0 or \
           scissors_alive == 0 and rock_alive == 0:
            break

    # Save as GIF
    gif_path = 'rps_simulation.gif'
    frames[0].save(
        gif_path,
        save_all=True,
        append_images=frames[1:],
        duration=50,
        loop=0
    )

    # Determine winner
    rock_count = sum(1 for e in elements if e.alive and e.element_type == 'rock')
    paper_count = sum(1 for e in elements if e.alive and e.element_type == 'paper')
    scissors_count = sum(1 for e in elements if e.alive and e.element_type == 'scissors')

    if rock_count > paper_count and rock_count > scissors_count:
        winner = "rock"
    elif paper_count > rock_count and paper_count > scissors_count:
        winner = "paper"
    elif scissors_count > rock_count and scissors_count > paper_count:
        winner = "scissors"
    else:
        winner = "draw"

    # Clean up
    pygame.quit()

    return gif_path, winner, [rock_count, paper_count, scissors_count]

def determine_winner(choices: List[str]) -> Tuple[int, str]:
    """
    Determine the winner from a list of choices.
    Returns tuple of (winner_index, reason)
    """
    if len(set(choices)) == 1:
        return -1, "It's a tie!"
    
    winning_combinations = {
        'rock': 'scissors',
        'paper': 'rock',
        'scissors': 'paper'
    }
    
    for i, choice in enumerate(choices):
        if all(choice == 'rock' and other == 'scissors' or
               choice == 'paper' and other == 'rock' or
               choice == 'scissors' and other == 'paper'
               for j, other in enumerate(choices) if i != j):
            return i, f"{choice.capitalize()} beats {winning_combinations[choice]}"
    
    # If no clear winner, return first winning matchup
    for i, choice in enumerate(choices):
        next_choice = choices[(i + 1) % len(choices)]
        if winning_combinations[choice] == next_choice:
            return i, f"{choice.capitalize()} beats {next_choice}"
    
    return -1, "No winner determined"

def simulate_game(update, context, bet_amount: float = 10.0) -> None:
    """
    Simulate a game with AI players
    """
    try:
        # Get or create the user
        user = User.query.filter_by(telegram_id=update.effective_user.id).first()
        if not user:
            update.message.reply_text(
                "You need to create an account first! Use /create_account"
            )
            return

        # Check user balance
        if user.balance < Decimal(str(bet_amount)):
            update.message.reply_text(
                f"Insufficient balance! You need ETB {bet_amount:.2f} to play."
            )
            return

        # Create AI players
        ai_names = ["🤖 Bot-Alpha", "🤖 Bot-Beta"]
        ai_users = []
        
        for name in ai_names:
            ai_user = User(
                username=name,
                telegram_id=None,
                balance=Decimal('1000.00'),
                is_bot=True,
                created_at=datetime.utcnow()
            )
            db.session.add(ai_user)
            ai_users.append(ai_user)
        
        # Create game
        game = Game(
            bet_amount=bet_amount,
            status='active',
            created_at=datetime.utcnow()
        )
        db.session.add(game)
        
        # Add participants
        participants = [user] + ai_users
        choices = ['rock', 'paper', 'scissors']
        
        for p in participants:
            # Deduct bet amount
            p.balance -= Decimal(str(bet_amount))
            
            # Add to game
            participant = GameParticipant(
                game_id=game.id,
                user_id=p.id,
                choice=random.choice(choices) if p.is_bot else None,
                joined_at=datetime.utcnow()
            )
            db.session.add(participant)
        
        db.session.commit()

        # Send initial message
        update.message.reply_text(
            f"🎮 Simulation started!\n\n"
            f"Game #{game.id}\n"
            f"Bet amount: ETB {bet_amount:.2f}\n\n"
            f"Players:\n"
            f"👤 You\n"
            f"🤖 {ai_names[0]}\n"
            f"🤖 {ai_names[1]}\n\n"
            f"Make your choice!"
        )

        return game.id

    except Exception as e:
        db.session.rollback()
        update.message.reply_text(
            "❌ Error starting simulation. Please try again."
        )
        raise e

def process_simulation_result(game_id: int, user_choice: str) -> Tuple[bool, str]:
    """
    Process the result of a simulated game after user makes their choice
    Returns (success, message)
    """
    try:
        game = Game.query.get(game_id)
        if not game or game.status != 'active':
            return False, "Game not found or already completed"

        # Update user's choice
        participants = GameParticipant.query.filter_by(game_id=game_id).all()
        human_participant = next(p for p in participants if not User.query.get(p.user_id).is_bot)
        human_participant.choice = user_choice
        
        # Get all choices
        choices = [p.choice for p in sorted(participants, key=lambda x: x.joined_at)]
        player_names = [
            "You" if not User.query.get(p.user_id).is_bot else User.query.get(p.user_id).username
            for p in sorted(participants, key=lambda x: x.joined_at)
        ]

        # Determine winner
        winner_idx, reason = determine_winner(choices)
        
        # Update game status
        game.status = 'completed'
        game.completed_at = datetime.utcnow()
        
        if winner_idx >= 0:
            # Winner takes all
            winner = sorted(participants, key=lambda x: x.joined_at)[winner_idx]
            winner_user = User.query.get(winner.user_id)
            pot = Decimal(str(game.bet_amount * 3))  # Total pot from all players
            winner_user.balance += pot
            
            # Record transaction
            transaction = Transaction(
                user_id=winner_user.id,
                amount=float(pot),
                transaction_type='win',
                status='completed',
                created_at=datetime.utcnow(),
                completed_at=datetime.utcnow()
            )
            db.session.add(transaction)
        
        db.session.commit()

        # Create result message
        choices_display = {
            'rock': '🗿',
            'paper': '📄',
            'scissors': '✂️'
        }
        
        result_message = "🎮 Game Results!\n\n"
        for i, (name, choice) in enumerate(zip(player_names, choices)):
            result_message += f"{name}: {choices_display[choice]} {choice.capitalize()}\n"
        
        result_message += f"\n{reason}\n"
        
        if winner_idx >= 0:
            winner_name = player_names[winner_idx]
            result_message += f"\n🎉 {winner_name} won ETB {float(pot):.2f}!"
        else:
            result_message += "\n🤝 It's a tie! Bets have been refunded."
            # Refund all players
            for p in participants:
                user = User.query.get(p.user_id)
                user.balance += Decimal(str(game.bet_amount))
        
        return True, result_message

    except Exception as e:
        db.session.rollback()
        return False, f"Error processing game result: {str(e)}"

if __name__ == "__main__":
    # Test the simulation
    gif_path, winner, final_counts = create_rps_simulation(33, 35, 31)
    print(f"Simulation complete! Winner: {winner}")
    print(f"Final counts - Rock: {final_counts[0]}, Paper: {final_counts[1]}, Scissors: {final_counts[2]}")
