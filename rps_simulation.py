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

class RPSSimulation:
    """Rock Paper Scissors simulation that generates a GIF animation"""
    
    def __init__(self, num_rock=33, num_paper=35, num_scissors=31, frames=180, size=(500, 500)):
        """Initialize the simulation"""
        self.num_rock = num_rock
        self.num_paper = num_paper
        self.num_scissors = num_scissors
        self.frames = frames
        self.width, self.height = size
        self.temp_dir = tempfile.mkdtemp()
        
        # Colors
        self.BLACK = (0, 0, 0)
        self.GRAY = (150, 150, 150)
        self.CREAM = (255, 253, 208)
        self.RED = (255, 0, 0)
        self.WHITE = (255, 255, 255)
        
        # Simulation parameters
        self.SPEED = 1.0
        self.RADIUS = 8
        self.INTERACTION_DISTANCE = 15
    
    def create_elements(self):
        """Create the initial elements"""
        elements = []
        for _ in range(self.num_rock):
            elements.append(self._create_element("rock"))
        for _ in range(self.num_paper):
            elements.append(self._create_element("paper"))
        for _ in range(self.num_scissors):
            elements.append(self._create_element("scissors"))
        return elements
    
    def _create_element(self, element_type):
        """Create a single element"""
        return {
            "type": element_type,
            "x": random.randint(self.RADIUS, self.width - self.RADIUS),
            "y": random.randint(self.RADIUS + 100, self.height - self.RADIUS),
            "vx": random.uniform(-self.SPEED, self.SPEED),
            "vy": random.uniform(-self.SPEED, self.SPEED)
        }
    
    def move_element(self, elem):
        """Move an element based on its velocity"""
        elem["x"] += elem["vx"]
        elem["y"] += elem["vy"]
        
        # Bounce off walls
        if elem["x"] <= self.RADIUS or elem["x"] >= self.width - self.RADIUS:
            elem["vx"] *= -1
        if elem["y"] <= self.RADIUS + 100 or elem["y"] >= self.height - self.RADIUS:
            elem["vy"] *= -1
    
    def interact(self, elem1, elem2):
        """Handle interaction between two elements"""
        # Calculate distance
        dx = elem1["x"] - elem2["x"]
        dy = elem1["y"] - elem2["y"]
        distance = math.sqrt(dx**2 + dy**2)
        
        if distance < self.INTERACTION_DISTANCE:
            # Apply RPS rules
            if (elem1["type"] == "rock" and elem2["type"] == "scissors") or \
               (elem1["type"] == "scissors" and elem2["type"] == "paper") or \
               (elem1["type"] == "paper" and elem2["type"] == "rock"):
                # elem1 wins, convert elem2
                elem2["type"] = elem1["type"]
                
                # Give slight push
                if distance > 0:
                    push = 0.1
                    elem1["vx"] += dx / distance * push
                    elem1["vy"] += dy / distance * push
                    elem2["vx"] -= dx / distance * push
                    elem2["vy"] -= dy / distance * push
    
    def draw_element(self, screen, elem):
        """Draw a single element on the screen"""
        if elem["type"] == "rock":
            pygame.draw.circle(screen, self.GRAY, (int(elem["x"]), int(elem["y"])), self.RADIUS)
        elif elem["type"] == "paper":
            rect = pygame.Rect(elem["x"] - self.RADIUS, elem["y"] - self.RADIUS, self.RADIUS*2, self.RADIUS*2)
            pygame.draw.rect(screen, self.CREAM, rect)
        elif elem["type"] == "scissors":
            # Draw an X
            line1_start = (elem["x"] - self.RADIUS*0.7, elem["y"] - self.RADIUS*0.7)
            line1_end = (elem["x"] + self.RADIUS*0.7, elem["y"] + self.RADIUS*0.7)
            line2_start = (elem["x"] + self.RADIUS*0.7, elem["y"] - self.RADIUS*0.7)
            line2_end = (elem["x"] - self.RADIUS*0.7, elem["y"] + self.RADIUS*0.7)
            pygame.draw.line(screen, self.RED, line1_start, line1_end, 2)
            pygame.draw.line(screen, self.RED, line2_start, line2_end, 2)
    
    def render_frame(self, elements, frame_num):
        """Render a single frame of the simulation"""
        frame_path = os.path.join(self.temp_dir, f"frame_{frame_num:04d}.png")
        
        # Create a Pygame surface
        screen = pygame.Surface((self.width, self.height))
        screen.fill(self.BLACK)
        
        # Draw border
        pygame.draw.rect(screen, self.WHITE, pygame.Rect(30, 100, self.width - 60, self.height - 130), 2)
        
        # Draw title
        font = pygame.font.SysFont('Arial', 30)
        title = font.render("‼️Rock vs Paper vs Scissors‼️", True, self.WHITE)
        screen.blit(title, (self.width//2 - title.get_width()//2, 40))
        
        # Count elements of each type
        rock_count = sum(1 for elem in elements if elem["type"] == "rock")
        paper_count = sum(1 for elem in elements if elem["type"] == "paper")
        scissors_count = sum(1 for elem in elements if elem["type"] == "scissors")
        
        # Draw counts
        count_font = pygame.font.SysFont('Arial', 24)
        rock_text = count_font.render(f"🪨 {rock_count}", True, self.GRAY)
        paper_text = count_font.render(f"📄 {paper_count}", True, self.CREAM)
        scissors_text = count_font.render(f"✂️ {scissors_count}", True, self.RED)
        
        screen.blit(rock_text, (self.width // 4 - 30, 75))
        screen.blit(paper_text, (self.width // 2 - 30, 75))
        screen.blit(scissors_text, (3 * self.width // 4 - 30, 75))
        
        # Draw elements
        for elem in elements:
            self.draw_element(screen, elem)
        
        # Save frame
        pygame.image.save(screen, frame_path)
        return frame_path, (rock_count, paper_count, scissors_count)
    
    def run_simulation(self):
        """Run the full simulation and create a GIF"""
        # Initialize Pygame
        pygame.init()
        pygame.font.init()
        
        # Create elements
        elements = self.create_elements()
        
        # List to store frame paths
        frame_paths = []
        frame_stats = []
        
        # Generate frames
        for frame in range(self.frames):
            # Move elements
            for elem in elements:
                self.move_element(elem)
            
            # Handle interactions
            for i in range(len(elements)):
                for j in range(i+1, len(elements)):
                    self.interact(elements[i], elements[j])
            
            # Every 2 frames, render and save
            if frame % 2 == 0:
                path, stats = self.render_frame(elements, frame // 2)
                frame_paths.append(path)
                frame_stats.append(stats)
        
        # Create GIF
        output_path = f'rps_simulation_{datetime.now().strftime("%Y%m%d_%H%M%S")}.gif'
        with imageio.get_writer(output_path, mode='I', duration=0.08) as writer:
            for frame_path in frame_paths:
                image = imageio.imread(frame_path)
                writer.append_data(image)
        
        # Clean up
        for path in frame_paths:
            if os.path.exists(path):
                os.remove(path)
        
        # Find the winner
        final_stats = frame_stats[-1]
        rock_count, paper_count, scissors_count = final_stats
        
        winner = "draw"
        if rock_count > paper_count and rock_count > scissors_count:
            winner = "rock"
        elif paper_count > rock_count and paper_count > scissors_count:
            winner = "paper"
        elif scissors_count > rock_count and scissors_count > paper_count:
            winner = "scissors"
        
        return output_path, winner, final_stats
        
# Function to run the simulation from outside
def create_rps_simulation(num_rock=33, num_paper=35, num_scissors=31):
    """Create an RPS simulation GIF with the given parameters"""
    simulation = RPSSimulation(num_rock, num_paper, num_scissors)
    return simulation.run_simulation()

if __name__ == "__main__":
    # Test the simulation
    output_path, winner, stats = create_rps_simulation()
    print(f"Simulation completed! GIF saved to: {output_path}")
    print(f"Winner: {winner}")
    print(f"Final stats - Rock: {stats[0]}, Paper: {stats[1]}, Scissors: {stats[2]}")
