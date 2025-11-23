from rembg import remove
from PIL import Image
import io
import os

def process_icons():
    source_path = 'static/images/favicon.png'
    
    if not os.path.exists(source_path):
        print(f"Error: Source file {source_path} not found.")
        return

    print(f"Processing {source_path}...")
    
    # Load image
    with open(source_path, 'rb') as i:
        input_data = i.read()
        
    # Remove background
    print("Removing background...")
    output_data = remove(input_data)
    
    # Convert to PIL Image
    img = Image.open(io.BytesIO(output_data))
    
    # Ensure RGBA
    if img.mode != 'RGBA':
        img = img.convert('RGBA')

    # Save icon-192.png
    print("Saving icon-192.png...")
    img_192 = img.resize((192, 192), Image.Resampling.LANCZOS)
    img_192.save('static/images/icon-192.png', 'PNG')
    
    # Save icon-512.png
    print("Saving icon-512.png...")
    img_512 = img.resize((512, 512), Image.Resampling.LANCZOS)
    img_512.save('static/images/icon-512.png', 'PNG')
    
    # Save favicon.png (32x32)
    print("Saving favicon.png...")
    img_32 = img.resize((32, 32), Image.Resampling.LANCZOS)
    img_32.save('static/images/favicon.png', 'PNG')
    
    # Save favicon.ico
    print("Saving favicon.ico...")
    img_32.save('static/images/favicon.ico', format='ICO', sizes=[(32, 32)])

    print("Done!")

if __name__ == '__main__':
    process_icons()
