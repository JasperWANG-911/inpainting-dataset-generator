import socket
import json
import logging
import os
from pathlib import Path

class ExecutionAgent:
    """
    ExecutionAgent, to execute code in Blender.
    """
    
    def __init__(self, host='localhost', port=8089, timeout=60):  # Increased timeout to 60 seconds
        """
        initialize the ExecutionAgent. Need to run blender_server.py first.
        """
        self.host = host
        self.port = port
        self.timeout = timeout
        self.logger = self._setup_logger()
        self.project_root = Path(__file__).parent.parent.parent  # Fixed path
    
    def _setup_logger(self):
        """Set up the logger."""
        logger = logging.getLogger('ExecutionAgent')
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        return logger
    
    def connect(self):
        """
        Establish a connection to Blender.
        """
        try:
            client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client.settimeout(self.timeout)
            client.connect((self.host, self.port))
            self.logger.info(f"Connected to: {self.host}:{self.port}")
            return client
        except Exception as e:
            self.logger.error(f"Failed to connect to Blender: {e}")
            raise ConnectionError(f"Unable to connect to Blender server: {e}")

    def execute_code(self, code):
        """
        Execute code in Blender.
        """
        client = None
        try:
            # Establish connection
            client = self.connect()

            # Send code
            self.logger.info("Sending code to Blender...")
            self.logger.debug(f"Code length: {len(code)} characters")
            client.send(code.encode('utf-8'))

            # Receive response with larger buffer
            self.logger.info("Waiting for Blender response...")
            response_parts = []
            while True:
                try:
                    part = client.recv(4096)
                    if not part:
                        break
                    response_parts.append(part.decode('utf-8'))
                    # Try to parse as JSON to see if we got complete response
                    try:
                        json.loads(''.join(response_parts))
                        break
                    except json.JSONDecodeError:
                        # Not complete yet, continue receiving
                        continue
                except socket.timeout:
                    self.logger.warning("Socket timeout while receiving response")
                    break
            
            response = ''.join(response_parts)
            
            # Parse JSON response
            result = json.loads(response)
            
            if result['status'] == 'success':
                self.logger.info("Code execution successful")
            else:
                self.logger.error(f"Code execution error: {result.get('error', 'Unknown error')}")
                
            return result
            
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON decoding failed: {e}")
            self.logger.error(f"Raw response: {response if 'response' in locals() else 'No response received'}")
            return None
            
        except socket.timeout:
            self.logger.error("Socket timeout - execution took too long")
            return None
            
        except Exception as e:
            self.logger.error(f"Code execution failed: {e}")
            return None
            
        finally:
            # Ensure connection is closed
            if client:
                try:
                    client.close()
                    self.logger.info("Connection closed")
                except:
                    pass
    
    def test_connection(self):
        """
        Test connection to Blender server.
        """
        try:
            # Simple test code
            test_code = "import bpy"
            result = self.execute_code(test_code)
            return result is not None and result.get('status') == 'success'
        except Exception as e:
            self.logger.error(f"Connection test failed: {e}")
            return False
    
    def execute_blender_script(self, script_path):
        """
        Execute a Blender script file
        """
        try:
            with open(script_path, 'r', encoding='utf-8') as f:
                code = f.read()

            self.logger.info(f"Executing script file: {script_path}")
            return self.execute_code(code)
            
        except FileNotFoundError:
            self.logger.error(f"Script file not found: {script_path}")
            return None
        except Exception as e:
            self.logger.error(f"Failed to read script file: {e}")
            return None
    
    def execute_codes_file(self, file_path: str, capture_views: bool = True):
        if not os.path.isabs(file_path):
            file_path = self.project_root / file_path
        
        if not os.path.isfile(file_path):
            raise FileNotFoundError(f"Script not found: {file_path}")

        with open(file_path, 'r', encoding='utf-8') as f:
            code = f.read()

        self.logger.info(f"Sending {file_path} to Blender")
        self.logger.info(f"Code preview (first 200 chars): {code[:200]}...")

        # Execute the main code
        result = self.execute_code(code)
        
        # After successful execution, capture scene views for reviewing (only if capture_views is True)
        if result and result.get('status') == 'success' and capture_views:
            self.logger.info("Capturing scene views for review...")
            
            # Code to capture views
            capture_code = """
    import bpy
    import math
    import os

    # Create output directory if it doesn't exist
    output_dir = r"D:\\Python Projects\\inpainting-dataset-generator\\reviewing_images"
    os.makedirs(output_dir, exist_ok=True)

    # Store original camera and create a new one for capturing
    original_camera = bpy.context.scene.camera

    # Create a new camera if none exists
    if not original_camera:
        bpy.ops.object.camera_add(location=(0, 0, 0))
        camera = bpy.context.active_object
        bpy.context.scene.camera = camera
    else:
        camera = original_camera

    # Set render resolution
    bpy.context.scene.render.resolution_x = 800
    bpy.context.scene.render.resolution_y = 600

    # Define camera positions for 5 views
    views = {
        'top': {
            'location': (0, 0, 10),
            'rotation': (0, 0, 0)
        },
        'front': {
            'location': (0, -10, 2),
            'rotation': (math.radians(80), 0, 0)
        },
        'back': {
            'location': (0, 10, 2),
            'rotation': (math.radians(80), 0, math.radians(180))
        },
        'left': {
            'location': (-10, 0, 2),
            'rotation': (math.radians(80), 0, math.radians(-90))
        },
        'right': {
            'location': (10, 0, 2),
            'rotation': (math.radians(80), 0, math.radians(90))
        }
    }

    # Capture each view
    for view_name, view_data in views.items():
        # Set camera position and rotation
        camera.location = view_data['location']
        camera.rotation_euler = view_data['rotation']
        
        # Set output path
        output_path = os.path.join(output_dir, f"{view_name}.png")
        bpy.context.scene.render.filepath = output_path
        
        # Render the image
        bpy.ops.render.render(write_still=True)
        print(f"Captured {view_name} view: {output_path}")

    # Restore original camera if we created a new one
    if not original_camera:
        bpy.data.objects.remove(camera, do_unlink=True)

    print("Scene capture completed")
    """
            
            capture_result = self.execute_code(capture_code)
            if capture_result and capture_result.get('status') == 'success':
                self.logger.info("Scene views captured successfully")
            else:
                self.logger.warning("Failed to capture scene views")
        elif not capture_views:
            self.logger.info("Scene capture skipped (review disabled for this step)")
        
        return result

# demo_usage:
if __name__ == "__main__":
    execution_agent = ExecutionAgent()

    if not execution_agent.test_connection():
        print("Cannot connect to Blender server. Please ensure it is running.")
    else:
        result = execution_agent.execute_codes_file("execution_code.py")
        # check status of result
        print("Execution result:", result)