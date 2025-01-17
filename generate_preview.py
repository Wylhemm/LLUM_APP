from pdf2image import convert_from_path
import os

def generate_preview():
    # Create files directory if it doesn't exist
    if not os.path.exists('files'):
        os.makedirs('files')
    
    # Convert first page of PDF to image
    try:
        images = convert_from_path('files/The-Maze-of-Narcissism.pdf', first_page=1, last_page=1)
        if images:
            # Save the first page as preview
            images[0].save('files/preview.png', 'PNG')
            print("Preview generated successfully!")
        else:
            print("No pages found in PDF")
    except Exception as e:
        print(f"Error generating preview: {e}")

if __name__ == "__main__":
    generate_preview()
