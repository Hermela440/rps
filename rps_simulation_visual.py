import pygame
import random
import math

# Initialize Pygame
pygame.init()

# Screen settings
WIDTH, HEIGHT = 800, 600
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Rock vs Paper vs Scissors Simulation")

# Colors
GRAY = (150, 150, 150)
CREAM = (255, 255, 200)
RED = (255, 60, 60)
BG_COLOR = (30, 30, 30)
WHITE = (255, 255, 255)

# Entity settings
ENTITY_SIZE = 10
SPEED = 2
ENTITY_TYPES = ['rock', 'paper', 'scissors']

# Font for population display
pygame.font.init()
font = pygame.font.SysFont('Arial', 24)

class Entity:
    def __init__(self, x, y, type_):
        self.x = x
        self.y = y
        self.type = type_
        self.dx = random.choice([-1, 1]) * SPEED
        self.dy = random.choice([-1, 1]) * SPEED

    def move(self):
        self.x += self.dx
        self.y += self.dy

        # Bounce off walls
        if self.x <= 0 or self.x >= WIDTH:
            self.dx *= -1
            self.x = max(0, min(self.x, WIDTH))
        if self.y <= 0 or self.y >= HEIGHT:
            self.dy *= -1
            self.y = max(0, min(self.y, HEIGHT))

    def draw(self):
        if self.type == 'rock':
            pygame.draw.circle(screen, GRAY, (int(self.x), int(self.y)), ENTITY_SIZE)
        elif self.type == 'paper':
            pygame.draw.rect(screen, CREAM, (self.x - ENTITY_SIZE, self.y - ENTITY_SIZE, ENTITY_SIZE*2, ENTITY_SIZE*2))
        elif self.type == 'scissors':
            # Draw scissors as an X
            half_size = ENTITY_SIZE
            pygame.draw.line(screen, RED, 
                           (self.x - half_size, self.y - half_size),
                           (self.x + half_size, self.y + half_size), 3)
            pygame.draw.line(screen, RED,
                           (self.x + half_size, self.y - half_size),
                           (self.x - half_size, self.y + half_size), 3)

def is_collision(e1, e2):
    distance = math.hypot(e1.x - e2.x, e1.y - e2.y)
    return distance < ENTITY_SIZE * 2

def beats(type1, type2):
    return (
        (type1 == 'rock' and type2 == 'scissors') or
        (type1 == 'scissors' and type2 == 'paper') or
        (type1 == 'paper' and type2 == 'rock')
    )

def draw_population_graph(populations, history):
    # Add current populations to history
    history.append([populations['rock'], populations['paper'], populations['scissors']])
    if len(history) > 200:  # Keep only last 200 frames
        history.pop(0)
    
    # Draw background for the graph
    graph_height = 100
    pygame.draw.rect(screen, (50, 50, 50), (0, 0, WIDTH, graph_height))
    
    # Draw population counts
    rock_text = font.render(f"Rocks: {populations['rock']}", True, GRAY)
    paper_text = font.render(f"Papers: {populations['paper']}", True, CREAM)
    scissors_text = font.render(f"Scissors: {populations['scissors']}", True, RED)
    
    screen.blit(rock_text, (10, 10))
    screen.blit(paper_text, (150, 10))
    screen.blit(scissors_text, (300, 10))
    
    # Draw graph lines
    if len(history) > 1:
        max_pop = max(max(frame) for frame in history)
        if max_pop > 0:
            for i in range(len(history) - 1):
                # Draw rock line (gray)
                pygame.draw.line(screen, GRAY,
                    (i * WIDTH / 200, graph_height - (history[i][0] / max_pop * (graph_height - 40))),
                    ((i + 1) * WIDTH / 200, graph_height - (history[i + 1][0] / max_pop * (graph_height - 40))), 2)
                
                # Draw paper line (cream)
                pygame.draw.line(screen, CREAM,
                    (i * WIDTH / 200, graph_height - (history[i][1] / max_pop * (graph_height - 40))),
                    ((i + 1) * WIDTH / 200, graph_height - (history[i + 1][1] / max_pop * (graph_height - 40))), 2)
                
                # Draw scissors line (red)
                pygame.draw.line(screen, RED,
                    (i * WIDTH / 200, graph_height - (history[i][2] / max_pop * (graph_height - 40))),
                    ((i + 1) * WIDTH / 200, graph_height - (history[i + 1][2] / max_pop * (graph_height - 40))), 2)

def main():
    # Create entities
    entities = []
    population_history = []

    def spawn_entities(count, type_):
        for _ in range(count):
            x = random.randint(ENTITY_SIZE, WIDTH - ENTITY_SIZE)
            y = random.randint(ENTITY_SIZE, HEIGHT - ENTITY_SIZE)
            entities.append(Entity(x, y, type_))

    # Initial populations
    spawn_entities(33, 'rock')
    spawn_entities(35, 'paper')
    spawn_entities(31, 'scissors')

    # Game loop
    clock = pygame.time.Clock()
    running = True

    while running:
        clock.tick(60)
        screen.fill(BG_COLOR)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:  # Reset simulation on spacebar
                    entities.clear()
                    population_history.clear()
                    spawn_entities(33, 'rock')
                    spawn_entities(35, 'paper')
                    spawn_entities(31, 'scissors')

        # Move and draw
        for entity in entities:
            entity.move()
            entity.draw()

        # Check for battles
        for i, e1 in enumerate(entities):
            for e2 in entities[i+1:]:
                if e1.type != e2.type and is_collision(e1, e2):
                    if beats(e1.type, e2.type):
                        e2.type = e1.type
                    elif beats(e2.type, e1.type):
                        e1.type = e2.type

        # Count populations
        populations = {
            'rock': sum(1 for e in entities if e.type == 'rock'),
            'paper': sum(1 for e in entities if e.type == 'paper'),
            'scissors': sum(1 for e in entities if e.type == 'scissors')
        }

        # Draw population graph
        draw_population_graph(populations, population_history)

        pygame.display.flip()

    pygame.quit()

if __name__ == "__main__":
    main() 