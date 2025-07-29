import csv
import json
import random
from typing import List, Dict

def load_assets_csv(csv_path: str) -> Dict[str, List[Dict]]:
    """load assets.csv and organize by tag"""
    assets_by_tag = {}
    
    with open(csv_path, 'r', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            tag = row['tag']
            if tag not in assets_by_tag:
                assets_by_tag[tag] = []
            assets_by_tag[tag].append({
                'file_path': row['file path'],
                'file_name': row['file name']
            })
    
    return assets_by_tag

def generate_combinations(config_file: str, assets_csv_path: str, 
                        num_combinations: int = 10) -> List[Dict]:
    """
    Generate asset combinations based on the configuration and available assets.
    
    Parameters:
        config_file: Path to JSON configuration file with object requirements.
        assets_csv_path: Path to the assets.csv
        num_combinations: Number of combinations to generate (default is 10).
    """
    
    # Load configuration from JSON file
    with open(config_file, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    # Load assets
    assets_by_tag = load_assets_csv(assets_csv_path)
    
    # Verify required objects
    for obj in config['objects']:
        if obj['name'] not in assets_by_tag:
            print(f"Warning: Missing asset type '{obj['name']}'")
            return None
    
    combinations = []
    
    # Generate combinations
    for i in range(num_combinations):
        combo = {
            'combination_id': i + 1,
            'objects': []
        }
        
        for obj in config['objects']:
            available = assets_by_tag[obj['name']]
            selected = random.choices(available, k=obj['quantity'])
            
            for idx, file_info in enumerate(selected):
                combo['objects'].append({
                    'type': obj['name'],
                    'instance_id': f"{obj['name']}_{idx + 1}",
                    'file_path': file_info['file_path'],
                    'file_name': file_info['file_name']
                })
        
        combinations.append(combo)
    
    return combinations

def save_combinations(combinations: List, output_path: str):
    """save combinations to JSON"""
    output = {
        'total': len(combinations),
        'combinations': combinations
    }
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"Saved {len(combinations)} combinations to: {output_path}")

# demo usage
if __name__ == "__main__":
   
    # an example configuration(should be loaded from output of request_parser.py)
    config_example = {
        "objects": [
            {"name": "house", "quantity": 1},
            {"name": "tree", "quantity": 3}
        ]
    }
    
    # save configuration to a file
    with open('scene_config.json', 'w', encoding='utf-8') as f:
        json.dump(config_example, f, indent=2)
    
    # use the asset list generator to scan assets
    combos = generate_combinations(
        config_file='scene_config.json',
        assets_csv_path='../Assets/assets.csv',
        num_combinations=10                              # Adjust as needed
    )
    
    # save results
    if combos:
        save_combinations(combos, 'output_combinations.json')