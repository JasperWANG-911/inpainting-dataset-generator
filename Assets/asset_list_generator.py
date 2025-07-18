import csv
import os
from pathlib import Path
from typing import List, Tuple

def scan_blend_files(assets_dir: str) -> List[Tuple[str, str, str]]:
    """scan all files in the assets directory"""
    models = []
    assets_path = Path(assets_dir)

    # iterate through all files in the assets directory
    for blend_file in assets_path.rglob('*.blend'):
        file_name = blend_file.name
        file_path = str(blend_file)

        # get the relative path
        relative_path = blend_file.relative_to(assets_path)
        file_label = relative_path.parts[0].lower()
        models.append((file_name, file_path, file_label))
    
    return models

def create_model_csv(csv_path: str, assets_dir: str = None, manual_data: List[Tuple] = None):
    """return a csv file in the format: file_name, file_path, file_label"""
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['file name', 'file path', 'file label'])
        
        if assets_dir and os.path.exists(assets_dir):
            # scan the assets directory
            print(f"Scanning {assets_dir} for .blend files...")
            models = scan_blend_files(assets_dir)
            writer.writerows(models)
            print(f"Found {len(models)} .blend files")
    
    print(f"CSV file saved to: {csv_path}")

# example usage
if __name__ == "__main__":
    create_model_csv('model_catalog.csv', assets_dir='/Users/wangyinghao/Desktop/inpainting-dataset-generator/Assets')
    