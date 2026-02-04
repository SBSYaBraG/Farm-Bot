"""
FarmBot X-Axis Control Script 

This script gives a command-line interface to control the FarmBot X-axis system.
Features:
- Automatic Arduino detection
- Emergency stop functionality with KeyboardInterrupt handling (Input Detection too ("S"))
- Case-insensitive command processing
- Improved error handling and user feedback
- Resume functionality after emergency stop ("S0")
"""

import serial
import time
import threading
import sys
import signal
import serial.tools.list_ports

class FarmBotController:
    def __init__(self):
        self.arduino = None
        self.emergency_stop_active = False
        self.running = True
        
    def find_arduino_port(self):
        """Find the Arduino port"""
        ports = serial.tools.list_ports.comports()
        for port in ports:
            if "Arduino" in port.description or "ttyACM" in port.device or "ttyUSB" in port.device:
                return port.device
        return None
    
    def open_serial_connection(self, port, baudrate=115200, timeout=2):
        """Open serial connection to Arduino"""
        try:
            connection = serial.Serial(port, baudrate, timeout=timeout)
            time.sleep(2)  #Wait for Arduino to reset
            return connection
        except serial.SerialException as e:
            print(f"Error opening serial connection: {e}")
            return None
    
    def send_command(self, command):
        """Send command to Arduino and read response"""
        if not self.arduino:
            print("No Arduino connection available")
            return False
            
        try:
            #Send command
            self.arduino.write((command + '\n').encode())
            time.sleep(0.1)  #Short delay for command processing
            
            #Read response with timeout
            start_time = time.time()
            while time.time() - start_time < 2.0:  #2 second timeout
                if self.arduino.in_waiting:
                    response = self.arduino.readline().decode().strip()
                    if response:
                        print(f"Arduino: {response}")
                        
                        #Check if emergency stop was confirmed
                        if "EMERGENCY STOP" in response:
                            self.emergency_stop_active = True
                        elif "Emergency stop cleared" in response or "operations resumed" in response:
                            self.emergency_stop_active = False
                            
                time.sleep(0.01)  #Small delay to prevent busy waiting
                
            return True
            
        except serial.SerialException as e:
            print(f"Error sending command: {e}")
            return False
        except Exception as e:
            print(f"Unexpected error: {e}")
            return False
    
    def emergency_stop(self): #Need to wait for Arduino to finish Connecting if auto-homing wants to be stopped
        #Send emergency stop command 
        print("\n*** EMERGENCY STOP ACTIVATED ***")
        if self.arduino:
            try:
                self.arduino.write(b'S\n')
                self.emergency_stop_active = True
                print("Emergency stop command sent to Arduino")
            except Exception as e:
                print(f"Error sending emergency stop: {e}")
    
    def signal_handler(self, signum, frame): #Need to wait for Arduino to finish Connecting if auto-homing wants to be stopped
        """Handle Ctrl+C signal"""
        print("\nKeyboard interrupt detected!")
        self.emergency_stop()
        self.running = False
        sys.exit(0)
    
    def print_help(self):
        """Print available commands"""
        print("\n" + "-"*50)
        print("FarmBot X-Axis Controller - Available Commands:") #Present User with Summary of Command functions
        print("="*50)
        print("Movement Commands:")
        print("  X####/Y####/Z####     - Move relative steps (e.g., X1000, X-500)") 
        print("  PX/PY/PZ   - Absolute Positioning of Desired Axis")
        print("  PX25       - Move to 25% position") #Absolute Positions (Later Changed depending on actual positional matrix of farm)
        print("  PX50       - Move to 50% position") 
        print("  PX75       - Move to 75% position")
        print()
        print("System Commands:")
        print("  Hx/Hy/Hz  - Run individual axes homing sequency")
        print("  H or HALL - Run homing sequence")
        print("  R         - Report current position and status")
        print("  S         - Emergency stop (immediate)") #Every n Steps of Motor Check for Command sent 
        print("  S0        - Resume operations after emergency stop") #After Stop Comman was sent ("S") NOTHING SHOULD HAPPEN If S0 has not been sent
        print()
        print("Control Commands:")
        print("  help      - Show this help message") #For long-term testing (I might forget what I am doing)
        print("  exit      - Exit the program")
        print("  quit      - Exit the program")
        print()
        print("Note: Commands are case-insensitive")
        print("      Use Ctrl+C for immediate emergency stop")
        print("-"*50)
    
    def command_loop(self):
        try:
            self.print_help()
            
            while self.running:
                try:
                    #Show current status in prompt
                    status = "EMERGENCY" if self.emergency_stop_active else "READY"
                    command = input(f"\nFarmBot [{status}]> ").strip()
                    
                    if not command:
                        continue
                    
                    #Convert to lowercase for comparison (Commands are case sensitive)
                    cmd_lower = command.lower()
                    
                    #Handle local commands
                    if cmd_lower in ['exit', 'quit']:
                        print("Exiting FarmBot controller...")
                        break
                    elif cmd_lower in ['help', '?']:
                        self.print_help()
                        continue
                    elif cmd_lower == 'status':
                        print(f"Connection: {'Connected' if self.arduino else 'Disconnected'}")
                        print(f"Emergency Stop: {'Active' if self.emergency_stop_active else 'Inactive'}")
                        continue
                    
                    #Send command to Arduino
                    success = self.send_command(command)
                    
                    if not success:
                        print("Failed to send command. Check connection.")
                        
                except KeyboardInterrupt:
                    print("\nKeyboard interrupt detected!")
                    self.emergency_stop()
                    
                    #Ask if user wants to continue
                    try:
                        response = input("\nContinue? (y/n): ").strip().lower()
                        if response in ['n', 'no']:
                            break
                    except KeyboardInterrupt:
                        break
                        
                except EOFError:
                    print("\nEOF detected. Exiting...")
                    break
                    
        except Exception as e:
            print(f"Error in command loop: {e}")
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Clean up resources"""
        if self.arduino:
            try:
                self.arduino.close()
                print("Arduino connection closed.")
            except Exception as e:
                print(f"Error closing Arduino connection: {e}")
    
    def run(self):
        """MAIN RUN FUNCTION"""
        #Set up signal handler for Ctrl+C
        signal.signal(signal.SIGINT, self.signal_handler)
        
        print("FarmBot X-Axis Controller Starting...") #First Thing to see at start-up
        print("Searching for Arduino...")
        
        #Find Arduino port
        port = self.find_arduino_port()
        if not port:
            print("Arduino not found!")
            print("\nAvailable ports:")
            ports = serial.tools.list_ports.comports()
            if ports:
                for p in ports:
                    print(f"  - {p.device} ({p.description})")
            else:
                print("  No serial ports found")
            return False
        
        print(f"Arduino found on port: {port}")
        
        #Open connection
        self.arduino = self.open_serial_connection(port)
        if not self.arduino:
            print("Failed to connect to Arduino")
            return False
        
        print(f"Connected to Arduino on {port}")
        print("Waiting for Arduino to initialize...") #End of Main run print, Available Commands should be shown in Terminal 
        time.sleep(2)
        
        #Start command loop
        self.command_loop()
        
        return True

def main():
    """MAIN ENTRY"""
    controller = FarmBotController()
    
    try:
        success = controller.run()
        if not success:
            sys.exit(1)
    except KeyboardInterrupt:
        print("\nProgram interrupted by user")
        controller.emergency_stop()
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)
    finally:
        controller.cleanup()

if __name__ == "__main__":
    main()