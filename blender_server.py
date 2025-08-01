# blender_server.py
import bpy
import socket
import threading
import json
import queue

# global message queue for inter-thread communication
message_queue = queue.Queue()

class BlenderCodeServer:
    def __init__(self, port=8089):
        self.port = port
        self.server = None
        self.running = False
        
    def start_server(self):
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.settimeout(0.1)  # add a timeout to avoid blocking
        self.server.bind(('localhost', self.port))
        self.server.listen(1)
        self.running = True
        
        print(f"Blender server started on port {self.port}")
        
        while self.running:
            try:
                client, address = self.server.accept()
                data = client.recv(4096).decode('utf-8')
                
                message_queue.put({
                    'client': client,
                    'code': data
                })
                
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    print(f"Server error: {e}")

class BLENDER_OT_code_server(bpy.types.Operator):
    """running a code server in Blender"""
    bl_idname = "wm.code_server"
    bl_label = "Code Server"
    
    _timer = None
    server = None
    server_thread = None
    
    def modal(self, context, event):
        if event.type == 'TIMER':
            # process code in the queue
            while not message_queue.empty():
                try:
                    msg = message_queue.get_nowait()
                    client = msg['client']
                    code = msg['code']
                    
                    # execute code in the main thread
                    result = self.execute_code(code)
                    
                    # send result
                    client.send(json.dumps(result).encode('utf-8'))
                    client.close()
                    
                except queue.Empty:
                    break
                except Exception as e:
                    print(f"Error processing message: {e}")
        
        if event.type == 'ESC':
            self.cancel(context)
            return {'CANCELLED'}
            
        return {'PASS_THROUGH'}
    
    def execute_code(self, code):
        try:
            exec(code, {'bpy': bpy})
            return {'status': 'success', 'error': None}
        except Exception as e:
            return {'status': 'error', 'error': str(e)}
    
    def execute(self, context):
        # start the server in a separate thread
        self.server = BlenderCodeServer()
        self.server_thread = threading.Thread(target=self.server.start_server)
        self.server_thread.daemon = True
        self.server_thread.start()
        
        # add a timer to keep the modal operator running
        wm = context.window_manager
        self._timer = wm.event_timer_add(0.1, window=context.window)
        wm.modal_handler_add(self)
        
        return {'RUNNING_MODAL'}
    
    def cancel(self, context):
        wm = context.window_manager
        wm.event_timer_remove(self._timer)
        
        if self.server:
            self.server.running = False
            
        print("Server stopped")

def register():
    bpy.utils.register_class(BLENDER_OT_code_server)

def unregister():
    bpy.utils.unregister_class(BLENDER_OT_code_server)

if __name__ == "__main__":
    register()
    
    # start the server
    bpy.ops.wm.code_server()
    print("Blender Code Server is running. Press ESC in Blender to stop.")