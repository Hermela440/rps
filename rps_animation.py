import pygame
import random
import io
from PIL import Image

class Entity:
    SIZE = 8
    SPEED = 2

    def __init__(self, kind, x, y):
        self.kind = kind
        self.x = x
        self.y = y
        self.dx = random.choice([-1, 1]) * Entity.SPEED
        self.dy = random.choice([-1, 1]) * Entity.SPEED
        self.won = False
        self.lost = False

    def move(self, width, height):
        self.x += self.dx
        self.y += self.dy

        # Bounce off edges
        if self.x <= 0 or self.x >= width:
            self.dx *= -1
            self.x = max(0, min(self.x, width))
        if self.y <= 0 or self.y >= height:
            self.dy *= -1
            self.y = max(0, min(self.y, height))

    def draw(self, surface, colors):
        color = colors[self.kind]
        if self.won:
            # Draw with golden border for winner
            pygame.draw.rect(surface, (255, 215, 0), 
                           (self.x-1, self.y-1, Entity.SIZE+2, Entity.SIZE+2))
        elif self.lost:
            # Draw with red border for loser
            pygame.draw.rect(surface, (255, 0, 0), 
                           (self.x-1, self.y-1, Entity.SIZE+2, Entity.SIZE+2))
        pygame.draw.rect(surface, color, (self.x, self.y, Entity.SIZE, Entity.SIZE))

    def beats(self, other):
        return (
            (self.kind == 'rock' and other.kind == 'scissors') or
            (self.kind == 'paper' and other.kind == 'rock') or
            (self.kind == 'scissors' and other.kind == 'paper')
        )

def create_battle_animation(choices):
    """Create a battle animation for the given choices."""
    # Initialize Pygame
    pygame.init()
    WIDTH, HEIGHT = 400, 300
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    clock = pygame.time.Clock()

    # Colors
    COLORS = {
        'rock': (150, 150, 150),      # Gray
        'paper': (255, 255, 255),     # White
        'scissors': (255, 0, 100)      # Pink
    }
    BLACK = (0, 0, 0)

    # Create entities based on choices
    entities = []
    positions = [
        (WIDTH//4, HEIGHT//2),        # Left
        (WIDTH//2, HEIGHT//4),        # Top
        (3*WIDTH//4, HEIGHT//2)       # Right
    ]
    
    for choice, pos in zip(choices, positions):
        entities.append(Entity(choice, pos[0], pos[1]))

    # Animation frames
    frames = []
    font = pygame.font.SysFont(None, 24)
    
    # Determine winner
    winner = None
    for i, e1 in enumerate(entities):
        wins = 0
        for j, e2 in enumerate(entities):
            if i != j and e1.beats(e2):
                wins += 1
        if wins == 2:  # Beats both others
            winner = e1
            e1.won = True
            for e2 in entities:
                if e2 != e1:
                    e2.lost = True
            break

    # Animation loop
    for frame in range(180):  # 3 seconds at 60 FPS
        screen.fill(BLACK)
        
        # Move and draw entities
        for entity in entities:
            entity.move(WIDTH, HEIGHT)
            entity.draw(screen, COLORS)
        
        # Draw player labels
        for i, (entity, choice) in enumerate(zip(entities, choices)):
            text = font.render(f"Player {i+1}: {choice.capitalize()}", 
                             True, COLORS[choice])
            screen.blit(text, (10, 10 + i*25))
        
        # Draw winner announcement in last second
        if frame >= 120:
            if winner:
                text = font.render(f"Winner: {winner.kind.capitalize()}!", 
                                 True, (255, 215, 0))
            else:
                text = font.render("Draw!", True, (255, 255, 255))
            text_rect = text.get_rect(center=(WIDTH//2, HEIGHT-30))
            screen.blit(text, text_rect)
        
        # Capture frame
        string_image = pygame.image.tostring(screen, 'RGB')
        temp_surf = Image.frombytes('RGB', (WIDTH, HEIGHT), string_image)
        frames.append(temp_surf)
        
        pygame.display.flip()
        clock.tick(60)

    # Clean up
    pygame.quit()
    
    # Create animated GIF
    output = io.BytesIO()
    frames[0].save(
        output,
        format='GIF',
        append_images=frames[1:],
        save_all=True,
        duration=1000/60,  # 60 FPS
        loop=0
    )
    output.seek(0)
    
    return output

def create_battle_result_image(choices, winner=None):
    """Create a static result image."""
    # Initialize Pygame
    pygame.init()
    WIDTH, HEIGHT = 400, 200
    surface = pygame.Surface((WIDTH, HEIGHT))
    
    # Colors
    COLORS = {
        'rock': (150, 150, 150),
        'paper': (255, 255, 255),
        'scissors': (255, 0, 100)
    }
    BLACK = (0, 0, 0)
    
    # Fill background
    surface.fill(BLACK)
    
    # Draw choices
    font = pygame.font.SysFont(None, 32)
    for i, choice in enumerate(choices):
        color = COLORS[choice]
        if winner and choice == winner:
            text = font.render(f"Player {i+1}: {choice.capitalize()} 👑", 
                             True, (255, 215, 0))
        else:
            text = font.render(f"Player {i+1}: {choice.capitalize()}", 
                             True, color)
        surface.blit(text, (20, 20 + i*40))
    
    # Draw result
    if winner:
        text = font.render(f"Winner: {winner.capitalize()}!", 
                         True, (255, 215, 0))
    else:
        text = font.render("Draw!", True, (255, 255, 255))
    text_rect = text.get_rect(center=(WIDTH//2, HEIGHT-40))
    surface.blit(text, text_rect)
    
    # Convert to PNG
    output = io.BytesIO()
    string_image = pygame.image.tostring(surface, 'RGB')
    temp_surf = Image.frombytes('RGB', (WIDTH, HEIGHT), string_image)
    temp_surf.save(output, format='PNG')
    output.seek(0)
    
    # Clean up
    pygame.quit()
    
    return output 