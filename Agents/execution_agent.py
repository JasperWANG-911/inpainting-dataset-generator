import socket
import json
import logging

class ExecutionAgent:
    """
    ExecutionAgent, to execute code in Blender.
    """
    
    def __init__(self, host='localhost', port=8089, timeout=10):
        """
        initialize the ExecutionAgent. Need to run blender_server.py first.
        """
        self.host = host
        self.port = port
        self.timeout = timeout
        self.logger = self._setup_logger()
    
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
            client.send(code.encode('utf-8'))

            # Receive response
            self.logger.info("Waiting for Blender response...")
            response = client.recv(4096).decode('utf-8')

            # Parse JSON response
            result = json.loads(response)
            self.logger.info("Code execution successful")
            return result
            
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON decoding failed: {e}")
            self.logger.error(f"Raw response: {response}")
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


# demo use
if __name__ == "__main__":
    # create an instance of ExecutionAgent
    agent = ExecutionAgent()

    # test connection
    if agent.test_connection():
        print("✓ Blender connection test successful")

        # execute custom code
        custom_code = """
import bpy
import json

# Get scene information
scene = bpy.context.scene
result = {
    'status': 'success',
    'scene_name': scene.name,
    'object_count': len(scene.objects),
    'frame_current': scene.frame_current
}

print(json.dumps(result))
"""
        
        result = agent.execute_code(custom_code)
        if result:
            print(f"Execution result: {result}")
        else:
            print("Code execution failed")
    else:
        print("Blender connection test failed")