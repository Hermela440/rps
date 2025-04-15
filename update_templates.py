import os

def update_templates():
    """Update all HTML templates to replace Replit CSS with standard Bootstrap"""
    template_dir = os.path.join(os.getcwd(), 'templates')
    
    for filename in os.listdir(template_dir):
        if filename.endswith('.html'):
            filepath = os.path.join(template_dir, filename)
            
            with open(filepath, 'r', encoding='utf-8') as file:
                content = file.read()
            
            # Replace Replit CSS with standard Bootstrap
            content = content.replace(
                'https://cdn.replit.com/agent/bootstrap-agent-dark-theme.min.css',
                'https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css'
            )
            
            with open(filepath, 'w', encoding='utf-8') as file:
                file.write(content)
                
            print(f"Updated {filename}")

if __name__ == "__main__":
    update_templates()
