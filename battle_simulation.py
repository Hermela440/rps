import pygame
import random
import math
import sys
from game import RPSGame

class VisualBattleSimulation:
    def __init__(self, width=800, height=600):
        pygame.init()
        self.width = width
        self.height = height
        self.screen = pygame.display.set_mode((width, height))
        pygame.display.set_caption("Rock vs Paper vs Scissors!")
        
        # Colors
        self.BLACK = (0, 0, 0)
        self.WHITE = (255, 255, 255)
        self.GRAY = (150, 150, 150)
        self.RED = (255, 0, 0)
        
        # Element properties
        self.elements = []
        self.initial_counts = {
            'rock': 67,
            'paper': 27,
            'scissors': 5
        }
        
        # Initialize elements
        self.initialize_elements()
        
        # Stats display
        self.font = pygame.font.Font(None, 36)
        
    def initialize_elements(self):
        for element_type, count in self.initial_counts.items():
            for _ in range(count):
                x = random.randint(50, self.width-50)
                y = random.randint(50, self.height-50)
                dx = random.uniform(-2, 2)
                dy = random.uniform(-2, 2)
                self.elements.append({
                    'type': element_type,
                    'x': x,
                    'y': y,
                    'dx': dx,
                    'dy': dy,
                    'size': 10
                })
    
    def draw_element(self, element):
        x, y = int(element['x']), int(element['y'])
        size = element['size']
        
        if element['type'] == 'rock':
            pygame.draw.circle(self.screen, self.GRAY, (x, y), size)
        elif element['type'] == 'paper':
            pygame.draw.rect(self.screen, self.WHITE, 
                           (x-size, y-size, size*2, size*2))
        else:  # scissors
            # Draw X shape
            pygame.draw.line(self.screen, self.RED, 
                           (x-size, y-size), (x+size, y+size), 2)
            pygame.draw.line(self.screen, self.RED, 
                           (x+size, y-size), (x-size, y+size), 2)
    
    def update_positions(self):
        for element in self.elements:
            # Update position
            element['x'] += element['dx']
            element['y'] += element['dy']
            
            # Bounce off walls
            if element['x'] < 0 or element['x'] > self.width:
                element['dx'] *= -1
            if element['y'] < 0 or element['y'] > self.height:
                element['dy'] *= -1
                
            # Keep within bounds
            element['x'] = max(0, min(self.width, element['x']))
            element['y'] = max(0, min(self.height, element['y']))
    
    def check_collisions(self):
        for i, elem1 in enumerate(self.elements):
            for j, elem2 in enumerate(self.elements[i+1:], i+1):
                dx = elem1['x'] - elem2['x']
                dy = elem1['y'] - elem2['y']
                distance = math.sqrt(dx*dx + dy*dy)
                
                if distance < elem1['size'] + elem2['size']:
                    # Determine winner
                    winner = self.determine_winner(elem1['type'], elem2['type'])
                    if winner == elem1['type']:
                        self.elements[j]['type'] = elem1['type']
                    elif winner == elem2['type']:
                        self.elements[i]['type'] = elem2['type']
    
    def determine_winner(self, type1, type2):
        if type1 == type2:
            return type1
        elif ((type1 == 'rock' and type2 == 'scissors') or
              (type1 == 'paper' and type2 == 'rock') or
              (type1 == 'scissors' and type2 == 'paper')):
            return type1
        else:
            return type2
    
    def draw_stats(self):
        counts = {'rock': 0, 'paper': 0, 'scissors': 0}
        for element in self.elements:
            counts[element['type']] += 1
            
        # Draw counts at the top
        rock_text = self.font.render(f"🪨 {counts['rock']}", True, self.GRAY)
        paper_text = self.font.render(f"📄 {counts['paper']}", True, self.WHITE)
        scissors_text = self.font.render(f"✂️ {counts['scissors']}", True, self.RED)
        
        self.screen.blit(rock_text, (20, 20))
        self.screen.blit(paper_text, (150, 20))
        self.screen.blit(scissors_text, (280, 20))
    
    def run(self):
        clock = pygame.time.Clock()
        running = True
        
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                    
            # Clear screen
            self.screen.fill(self.BLACK)
            
            # Update simulation
            self.update_positions()
            self.check_collisions()
            
            # Draw elements
            for element in self.elements:
                self.draw_element(element)
                
            # Draw stats
            self.draw_stats()
            
            # Update display
            pygame.display.flip()
            
            # Cap at 60 FPS
            clock.tick(60)
        
        pygame.quit()

def run_visual_simulation():
    simulation = VisualBattleSimulation()
    simulation.run()

if __name__ == "__main__":
    run_visual_simulation()