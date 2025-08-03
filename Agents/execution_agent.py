import socket
import json
import logging
import os

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
            
            if result['status'] == 'success':
                self.logger.info("Code execution successful")
            else:
                self.logger.error(f"Code execution error: {result.get('error', 'Unknown error')}")
                
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
    
    def execute_codes_file(self, file_path: str):
        if not os.path.isfile(file_path):
            raise FileNotFoundError(f"Script not found: {file_path}")

        with open(file_path, 'r', encoding='utf-8') as f:
            code = f.read()

        self.logger.info(f"Sending {file_path} to Blender")

        return self.execute_code(code)

# demo_usage:
if __name__ == "__main__":
    execution_agent = ExecutionAgent()

    if not execution_agent.test_connection():
        print("Cannot connect to Blender server. Please ensure it is running.")
    else:
        result = execution_agent.execute_codes_file("../execution_code.py")
        # check status of result
        print("Execution result:", result)