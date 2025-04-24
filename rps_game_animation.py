import pygame
import os
import tempfile
from PIL import Image
import io
import math
import logging
import time

LOGGER = logging.getLogger(__name__)

class RPSGameAnimator:
    def __init__(self, width=800, height=600):
        # Initialize Pygame
        pygame.init()
        pygame.font.init()
        
        # Screen settings
        self.WIDTH = width
        self.HEIGHT = height
        self.screen = pygame.Surface((self.WIDTH, self.HEIGHT))
        
        # Colors
        self.COLORS = {
            'rock': (150, 150, 150),     # Gray
            'paper': (255, 255, 200),    # Cream
            'scissors': (255, 60, 60),    # Red
            'background': (30, 30, 30),   # Dark gray
            'text': (255, 255, 255)       # White
        }
        
        # Entity settings
        self.ENTITY_SIZE = 40
        self.font = pygame.font.SysFont('Arial', 32)

        self.animation_dir = "static/animations"
        self.image_dir = "static/images"
        
        # Ensure directories exist
        os.makedirs(self.animation_dir, exist_ok=True)
        os.makedirs(self.image_dir, exist_ok=True)
        
        # Animation paths for different scenarios
        self.animations = {
            "rock_vs_paper": "static/animations/rock_vs_paper.mp4",
            "rock_vs_scissors": "static/animations/rock_vs_scissors.mp4",
            "paper_vs_scissors": "static/animations/paper_vs_scissors.mp4",
            "rock_vs_rock": "static/animations/rock_vs_rock.mp4",
            "paper_vs_paper": "static/animations/paper_vs_paper.mp4",
            "scissors_vs_scissors": "static/animations/scissors_vs_scissors.mp4"
        }
        
        # Result animations
        self.result_animations = {
            "rock_wins": "static/animations/rock_wins.mp4",
            "paper_wins": "static/animations/paper_wins.mp4",
            "scissors_wins": "static/animations/scissors_wins.mp4",
            "draw": "static/animations/draw.mp4"
        }

    def draw_choice(self, choice, position, scale=1.0):
        size = int(self.ENTITY_SIZE * scale)
        x, y = position
        
        if choice == 'rock':
            pygame.draw.circle(self.screen, self.COLORS['rock'], (x, y), size)
        elif choice == 'paper':
            rect = pygame.Rect(x - size, y - size, size * 2, size * 2)
            pygame.draw.rect(self.screen, self.COLORS['paper'], rect)
        elif choice == 'scissors':
            pygame.draw.line(self.screen, self.COLORS['scissors'],
                           (x - size, y - size),
                           (x + size, y + size), 5)
            pygame.draw.line(self.screen, self.COLORS['scissors'],
                           (x + size, y - size),
                           (x - size, y + size), 5)

    def create_battle_animation(self, players, choices, winner=None):
        """
        Create a battle animation for the game
        
        Args:
            players (list): List of player usernames
            choices (dict): Dictionary mapping usernames to their choices
            winner (str): Username of the winner, None if draw
            
        Returns:
            str: Path to the generated animation file
        """
        try:
            # Generate unique filename for this battle
            timestamp = int(time.time())
            output_path = os.path.join(self.animation_dir, f"battle_{timestamp}.mp4")
            
            # Create the animation sequence
            # This is a placeholder - in a real implementation, you would:
            # 1. Load the player choice animations
            # 2. Combine them in sequence
            # 3. Add the result animation
            # 4. Save to output_path
            
            return output_path
            
        except Exception as e:
            LOGGER.error(f"Error creating battle animation: {e}")
            return None
    
    def cleanup(self, animation_path):
        """Remove temporary animation files"""
        try:
            if animation_path and os.path.exists(animation_path):
                os.remove(animation_path)
        except Exception as e:
            LOGGER.error(f"Error cleaning up animation file {animation_path}: {e}")
    
    def beats(self, choice1, choice2):
        """Determine if choice1 beats choice2"""
        return (
            (choice1 == "rock" and choice2 == "scissors") or
            (choice1 == "scissors" and choice2 == "paper") or
            (choice1 == "paper" and choice2 == "rock")
        )

    def get_match_animation(self, player1_choice, player2_choice):
        """Get the appropriate animation for a match between two choices"""
        choices = sorted([player1_choice, player2_choice])
        key = f"{choices[0]}_vs_{choices[1]}"
        return self.animations.get(key)
    
    def get_result_animation(self, winner_choice):
        """Get the result animation based on the winning choice"""
        if not winner_choice:
            return self.result_animations["draw"]
        return self.result_animations.get(f"{winner_choice}_wins") 